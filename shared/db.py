"""Schema e CRUD SQLite. Unica fonte di verità, condivisa da mcp_server e dashboard."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# FINHUB_DATA_DIR sposta tutti i dati altrove. Serve per puntare un processo separato
# (il server MCP, avviato da un client) a una cartella di prova: monkeypatchare
# db.DATA_DIR vale solo dentro il processo che lo fa.
DATA_DIR = Path(os.environ.get("FINHUB_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
PROFILES_DIR = DATA_DIR / "profiles"
ACTIVE_PROFILE_FILE = DATA_DIR / "active_profile.txt"
DEFAULT_PROFILE = "default"
_LEGACY_DB_PATH = DATA_DIR / "portfolio.db"


def _resolve_active_profile_db() -> Path:
    # Un file .db per profilo (nativo in SQLite: niente colonna profile_id da filtrare ovunque)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    name = ACTIVE_PROFILE_FILE.read_text().strip() if ACTIVE_PROFILE_FILE.exists() else DEFAULT_PROFILE
    path = PROFILES_DIR / f"{name}.db"
    if name == DEFAULT_PROFILE and not path.exists() and _LEGACY_DB_PATH.exists():
        # migrazione one-shot dal vecchio DB unico (pre-profili) al profilo "default"
        _LEGACY_DB_PATH.rename(path)
    return path


DB_PATH = _resolve_active_profile_db()

SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL CHECK(category IN ('ETF', 'BTP', 'ALTRO')),
    name TEXT NOT NULL,
    ticker_or_isin TEXT,
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    manual_price REAL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    notes TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cash_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    balance REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    description TEXT
);
"""


@contextmanager
def get_connection():
    # row_factory=Row converte risultati in dict; commit automatico al termine (no explicit conn.commit)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Le modifiche allo schema vivono qui, non dentro SCHEMA: DB nuovi e DB gia esistenti
# percorrono la stessa sequenza, quindi non possono divergere. PRAGMA user_version tiene
# il conto di dove siamo arrivati. Quando la lista diventa lunga, si rigenera SCHEMA da un
# DB migrato e si azzera.
MIGRATIONS = [
    # v1: lega le transazioni a un conto e le rende re-importabili senza duplicati
    [
        "ALTER TABLE transactions ADD COLUMN account_id INTEGER REFERENCES cash_accounts(id)",
        "ALTER TABLE transactions ADD COLUMN dedup_key TEXT",
        # UNIQUE non si puo aggiungere con ALTER: serve un indice separato.
        # In SQLite due NULL non collidono in un indice unique, quindi le righe inserite
        # a mano (dedup_key NULL) restano duplicabili - che e il comportamento giusto.
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_dedup ON transactions(dedup_key)",
    ],
    # v2: separa il prezzo di mercato dall'override manuale. Finora refresh_etf_quote
    # scriveva la quotazione live dentro manual_price, cioe nella stessa colonna in cui
    # l'utente mette a mano il prezzo dei BTP: un refresh sovrascriveva senza avviso un
    # valore dichiarato a mano, e non c'era modo di sapere ne la fonte ne la data.
    [
        "ALTER TABLE holdings ADD COLUMN market_price REAL",
        "ALTER TABLE holdings ADD COLUMN market_price_at TEXT",
    ],
]


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version >= len(MIGRATIONS):
            return
        # executescript() committa, e il DDL non apre transazioni implicite: senza questo
        # BEGIN un ALTER fallito a meta lascerebbe il file mezzo migrato con user_version
        # ancora indietro, e da li in poi ogni avvio crasherebbe con "duplicate column name".
        conn.execute("BEGIN")
        for n, statements in enumerate(MIGRATIONS[version:], start=version + 1):
            for sql in statements:
                conn.execute(sql)
            conn.execute(f"PRAGMA user_version = {n}")  # i PRAGMA non accettano '?'


# --- profili (un DB SQLite per profilo) ---

def list_profiles() -> list[str]:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    names = sorted(p.stem for p in PROFILES_DIR.glob("*.db"))
    return names or [DEFAULT_PROFILE]


def get_active_profile() -> str:
    return DB_PATH.stem


def set_active_profile(name: str):
    # Crea il profilo se non esiste (nuovo file .db con schema inizializzato) o passa a uno esistente
    global DB_PATH
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = PROFILES_DIR / f"{name}.db"
    ACTIVE_PROFILE_FILE.write_text(name)
    init_db()


@contextmanager
def profilo(name: str):
    """Punta il processo a un profilo per la durata del blocco, poi ripristina.

    Diverso da set_active_profile, che cambia il profilo per sempre e riscrive
    active_profile.txt: qui il cambio e temporaneo e non tocca lo stato su disco, perche
    serve a un'operazione singola che dichiara su quale profilo vuole agire.

    Il profilo deve gia esistere: crearlo al volo qui vorrebbe dire che un nome digitato
    male diventa un profilo nuovo e vuoto in cui l'import sparisce senza un errore.
    """
    global DB_PATH
    path = PROFILES_DIR / f"{name}.db"
    if not path.exists():
        raise ValueError(f"profilo inesistente: {name!r}. Esistenti: {', '.join(list_profiles())}")
    precedente = DB_PATH
    DB_PATH = path
    try:
        yield
    finally:
        DB_PATH = precedente


def _now():
    return datetime.now().isoformat(timespec="seconds")


# --- holdings (ETF / BTP / altri investimenti) ---

def add_holding(category, name, ticker_or_isin, quantity, avg_price, manual_price=None, currency="EUR", notes=None):
    # category: 'ETF', 'BTP', o 'ALTRO' (CHECK nel DB)
    # avg_price: prezzo di carico (storico), manual_price: prezzo corrente aggiornabile (es. BTP)
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO holdings (category, name, ticker_or_isin, quantity, avg_price, manual_price, currency, notes, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (category, name, ticker_or_isin, quantity, avg_price, manual_price, currency, notes, _now()),
        )
        return cur.lastrowid


def list_holdings(category=None):
    with get_connection() as conn:
        if category:
            rows = conn.execute("SELECT * FROM holdings WHERE category = ? ORDER BY name", (category,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM holdings ORDER BY category, name").fetchall()
        return [dict(r) for r in rows]


def update_holding(holding_id, **fields):
    # Generico: accetta qualunque campo. updated_at viene sempre aggiornato automaticamente (invariante)
    if not fields:
        return
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE holdings SET {cols} WHERE id = ?", (*fields.values(), holding_id))


def delete_holding(holding_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))


# --- liquidità ---

def upsert_cash_account(name, balance):
    # Upsert: INSERT if new, UPDATE if exists (via ON CONFLICT name UNIQUE constraint)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO cash_accounts (name, balance, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET balance = excluded.balance, updated_at = excluded.updated_at",
            (name, balance, _now()),
        )


def list_cash_accounts():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name").fetchall()]


def get_or_create_cash_account(name) -> int:
    # Volutamente NON upsert_cash_account: quella riscrive il saldo, e un import di
    # movimenti non sa nulla del saldo. Qui serve solo l'id del conto.
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO cash_accounts (name, balance, updated_at) VALUES (?, 0, ?)",
            (name, _now()),
        )
        return conn.execute("SELECT id FROM cash_accounts WHERE name = ?", (name,)).fetchone()[0]


# --- spese/entrate ---

def add_transaction(date, type_, category, amount, description=None):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO transactions (date, type, category, amount, description) VALUES (?, ?, ?, ?, ?)",
            (date, type_, category, amount, description),
        )
        return cur.lastrowid


def list_transactions(limit=200):
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM transactions ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def update_transaction(transaction_id, **fields):
    # Generico come update_holding. Niente updated_at: transactions non ce l'ha.
    # Serve per correggere una riga sbagliata e per ricategorizzare in blocco.
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE transactions SET {cols} WHERE id = ?", (*fields.values(), transaction_id))


def delete_transaction(transaction_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))


def add_imported_transactions(rows) -> tuple[int, int]:
    """rows: tuple (date, type, category, amount, description, account_id, dedup_key).
    INSERT OR IGNORE sull'indice unique di dedup_key: reimportare lo stesso estratto non
    duplica niente. Ritorna (inserite, saltate-perche-gia-presenti)."""
    if not rows:
        return 0, 0
    with get_connection() as conn:
        prima = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO transactions"
            " (date, type, category, amount, description, account_id, dedup_key)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        # total_changes e non cursor.rowcount: su executemany con OR IGNORE rowcount non e
        # affidabile. Il differenziale conta anche i duplicati interni al batch, che e giusto.
        inserite = conn.total_changes - prima
    return inserite, len(rows) - inserite


# --- prezzi ---

def prezzo_corrente(holding) -> float:
    """Prezzo da usare per valutare una posizione, in ordine di autorita:
    manual_price (l'utente lo afferma) > market_price (l'ultima quotazione) > avg_price (il carico).

    Unico posto dove vive questa regola: la usano portfolio_summary, la dashboard e market-data.
    """
    for campo in ("manual_price", "market_price", "avg_price"):
        if holding.get(campo) is not None:
            return holding[campo]
    return 0.0


# --- riepilogo ---

def portfolio_summary():
    # Valuta il portafoglio con prezzo_corrente(): manual_price (quello che dichiara l'utente)
    # vince su market_price (quello che dice il mercato), che vince su avg_price (il carico).
    # transactions NON entra qui di proposito: cash_accounts.balance e la fotografia che arriva
    # dall'estratto e transactions e il registro che arriva dallo stesso estratto. Sommarli
    # significherebbe contare due volte gli stessi soldi.
    holdings = list_holdings()
    cash = list_cash_accounts()
    invested_value = 0.0
    by_category = {}
    for h in holdings:
        value = prezzo_corrente(h) * h["quantity"]
        invested_value += value
        by_category[h["category"]] = by_category.get(h["category"], 0.0) + value
    cash_total = sum(c["balance"] for c in cash)
    return {
        "invested_value": invested_value,
        "cash_total": cash_total,
        "total_net_worth": invested_value + cash_total,
        "by_category": by_category,
    }
