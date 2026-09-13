"""Test della funzionalità di fetch automatico del prezzo nel server MCP.
Esegui: python tests/test_server.py
"""
import sys
from pathlib import Path
from unittest.mock import patch
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import db
from mcp_server import server

db.DB_PATH = Path(tempfile.mkdtemp()) / "test_server.db"
db.init_db()

# Test 1: avg_price fornito → usa quello (senza fetch)
print("Test 1: avg_price fornito, no fetch...")
holding_id = server.add_holding(
    category="ETF",
    name="Test ETF",
    quantity=10,
    avg_price=100.0,
    ticker_or_isin="TEST.MI"
)
holdings = db.list_holdings()
assert holdings[-1]["avg_price"] == 100.0
print("[OK] Test 1 passato")

# Test 2: avg_price non fornito, fetch automatico dal ticker
print("Test 2: fetch automatico del prezzo...")
with patch("shared.quotes.get_etf_quote", return_value=150.5):
    holding_id = server.add_holding(
        category="ETF",
        name="VWCE",
        quantity=5,
        ticker_or_isin="VWCE.MI"
    )
    holdings = db.list_holdings()
    assert holdings[-1]["avg_price"] == 150.5
print("[OK] Test 2 passato")

# Test 3: fetch fallisce (ticker non valido) - errore
print("Test 3: fetch fallisce - ValueError...")
try:
    with patch("shared.quotes.get_etf_quote", return_value=None):
        server.add_holding(
            category="ETF",
            name="Invalid",
            quantity=3,
            ticker_or_isin="INVALID.XX"
        )
    assert False, "Deve lanciare ValueError"
except ValueError as e:
    assert "Impossibile recuperare il prezzo" in str(e)
print("[OK] Test 3 passato")

# Test 4: nessun prezzo, nessun ticker - errore
print("Test 4: nessun prezzo disponibile - ValueError...")
try:
    server.add_holding(
        category="BTP",
        name="Test BTP",
        quantity=1000
    )
    assert False, "Deve lanciare ValueError"
except ValueError as e:
    assert "Devi fornire avg_price" in str(e)
print("[OK] Test 4 passato")

print("\nOK: tutti i test della funzionalità di fetch automatico superati")
