"""Schema e CRUD SQLite. Unica fonte di verità, condivisa da mcp_server e dashboard."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "portfolio.db"

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
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def _now():
    return datetime.now().isoformat(timespec="seconds")


# --- holdings (ETF / BTP / altri investimenti) ---

def add_holding(category, name, ticker_or_isin, quantity, avg_price, manual_price=None, currency="EUR", notes=None):
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
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO cash_accounts (name, balance, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET balance = excluded.balance, updated_at = excluded.updated_at",
            (name, balance, _now()),
        )


def list_cash_accounts():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name").fetchall()]


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


# --- riepilogo ---

def portfolio_summary():
    holdings = list_holdings()
    cash = list_cash_accounts()
    invested_value = 0.0
    by_category = {}
    for h in holdings:
        price = h["manual_price"] if h["manual_price"] is not None else h["avg_price"]
        value = price * h["quantity"]
        invested_value += value
        by_category[h["category"]] = by_category.get(h["category"], 0.0) + value
    cash_total = sum(c["balance"] for c in cash)
    return {
        "invested_value": invested_value,
        "cash_total": cash_total,
        "total_net_worth": invested_value + cash_total,
        "by_category": by_category,
    }
