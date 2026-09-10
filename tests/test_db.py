"""Self-check minimo sulla logica di shared/db.py (schema + calcolo patrimonio).
Esegui: python tests/test_db.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.db as db

db.DB_PATH = Path(tempfile.mkdtemp()) / "test_portfolio.db"
db.init_db()

etf_id = db.add_holding("ETF", "iShares MSCI World", "SWDA.MI", quantity=10, avg_price=80.0)
db.update_holding(etf_id, manual_price=90.0)
db.add_holding("BTP", "BTP 2030", "IT0005441883", quantity=1000, avg_price=98.0, manual_price=99.5)
db.upsert_cash_account("Conto principale", 500.0)
db.add_transaction("2026-01-15", "expense", "spesa", 42.5, "supermercato")

holdings = db.list_holdings()
assert len(holdings) == 2, "attese 2 posizioni"
assert db.list_holdings("ETF")[0]["ticker_or_isin"] == "SWDA.MI"

summary = db.portfolio_summary()
expected_invested = 10 * 90.0 + 1000 * 99.5
assert abs(summary["invested_value"] - expected_invested) < 1e-6, summary
assert summary["cash_total"] == 500.0
assert abs(summary["total_net_worth"] - (expected_invested + 500.0)) < 1e-6

txs = db.list_transactions()
assert len(txs) == 1 and txs[0]["category"] == "spesa"

db.delete_holding(etf_id)
assert len(db.list_holdings()) == 1

print("OK: tutti i controlli superati")
