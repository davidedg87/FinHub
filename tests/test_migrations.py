"""Self-check sulla migrazione dello schema (PRAGMA user_version in shared/db.py).
Copre quello che, se si rompe, si porta via i dati: idempotenza e rollback.
Esegui: python tests/test_migrations.py
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.db as db

MIGRAZIONI_VERE = list(db.MIGRATIONS)


def _db_vergine(nome):
    """Un DB allo schema v0, come quelli creati prima delle migrazioni."""
    path = Path(tempfile.mkdtemp()) / nome
    conn = sqlite3.connect(path)
    conn.executescript(db.SCHEMA)
    conn.execute("INSERT INTO holdings (category, name, quantity, avg_price, updated_at)"
                 " VALUES ('ETF', 'VWCE', 51, 149.98, '2026-09-11T15:13:00')")
    conn.execute("INSERT INTO transactions (date, type, category, amount) VALUES ('2026-01-15','expense','spesa',42.5)")
    conn.commit()
    conn.close()
    return path


# --- la migrazione si applica, e riapplicarla non fa niente ---

db.DB_PATH = _db_vergine("migrazione.db")
db.init_db()
db.init_db()  # secondo giro: deve essere un no-op, non ri-ALTERare

conn = sqlite3.connect(db.DB_PATH)
assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRAZIONI_VERE)
colonne = [r[1] for r in conn.execute("PRAGMA table_info(transactions)")]
assert "account_id" in colonne and "dedup_key" in colonne, colonne
assert "idx_tx_dedup" in [r[1] for r in conn.execute("PRAGMA index_list(transactions)")]

# i dati preesistenti sopravvivono
assert conn.execute("select count(*) from holdings").fetchone()[0] == 1
assert conn.execute("select count(*) from transactions").fetchone()[0] == 1

# dedup_key NULL sulle righe manuali: in SQLite due NULL non collidono in un indice unique,
# quindi due caffe identici digitati a mano restano due righe
conn.execute("INSERT INTO transactions (date,type,category,amount) VALUES ('2026-01-01','expense','bar',1.2)")
conn.execute("INSERT INTO transactions (date,type,category,amount) VALUES ('2026-01-01','expense','bar',1.2)")
conn.commit()
assert conn.execute("select count(*) from transactions").fetchone()[0] == 3

# la stessa dedup_key invece collide
conn.execute("INSERT INTO transactions (date,type,category,amount,dedup_key) VALUES ('2026-01-02','expense','bar',1.2,'abc')")
conn.commit()
try:
    conn.execute("INSERT INTO transactions (date,type,category,amount,dedup_key) VALUES ('2026-01-02','expense','bar',1.2,'abc')")
    raise AssertionError("la dedup_key duplicata doveva essere rifiutata")
except sqlite3.IntegrityError:
    pass
conn.close()


# --- una migrazione che fallisce a meta non lascia il file mezzo migrato ---
# Senza il BEGIN esplicito in init_db() il DDL girerebbe in autocommit: il primo ALTER
# resterebbe applicato con user_version ancora indietro, e da li ogni avvio successivo
# crasherebbe con "duplicate column name" su un file che l'utente non sa riparare.

db.DB_PATH = _db_vergine("rollback.db")
db.MIGRATIONS = MIGRAZIONI_VERE + [[
    "ALTER TABLE holdings ADD COLUMN market_price REAL",
    "ALTER TABLE holdings ADD COLUMN market_price REAL",  # duplicata di proposito: esplode
]]
try:
    db.init_db()
    raise AssertionError("la migrazione rotta doveva sollevare")
except sqlite3.OperationalError:
    pass
finally:
    db.MIGRATIONS = MIGRAZIONI_VERE

conn = sqlite3.connect(db.DB_PATH)
assert conn.execute("PRAGMA user_version").fetchone()[0] == 0, "user_version non doveva avanzare"
assert "market_price" not in [r[1] for r in conn.execute("PRAGMA table_info(holdings)")]
assert "dedup_key" not in [r[1] for r in conn.execute("PRAGMA table_info(transactions)")], \
    "anche gli step riusciti vanno annullati: sono nella stessa transazione"
conn.close()


# --- update/delete di una transazione ---

db.DB_PATH = _db_vergine("crud.db")
db.init_db()
tx_id = db.add_transaction("2026-02-01", "expense", "da categorizzare", 12.0, "BAR SPORT")
db.update_transaction(tx_id, category="Bar")
assert db.list_transactions()[0]["category"] == "Bar"
db.update_transaction(tx_id)  # nessun campo: no-op, non deve sollevare
db.delete_transaction(tx_id)
assert all(t["id"] != tx_id for t in db.list_transactions())

print("OK: migrazione idempotente, rollback completo, CRUD transazioni")
