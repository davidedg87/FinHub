"""Test dell'isolamento tra profili (un DB SQLite separato per profilo).
Esegui: python tests/test_profiles.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.db as db

tmp = Path(tempfile.mkdtemp())
db.DATA_DIR = tmp
db.PROFILES_DIR = tmp / "profiles"
db.ACTIVE_PROFILE_FILE = tmp / "active_profile.txt"
db._LEGACY_DB_PATH = tmp / "portfolio.db"
db.set_active_profile("alice")

db.add_holding("ETF", "Alice ETF", "AAA.MI", quantity=10, avg_price=50.0)
assert db.get_active_profile() == "alice"
assert len(db.list_holdings()) == 1

db.set_active_profile("bob")
assert db.get_active_profile() == "bob"
assert len(db.list_holdings()) == 0, "il profilo bob deve partire vuoto, isolato da alice"

db.add_holding("ETF", "Bob ETF", "BBB.MI", quantity=5, avg_price=20.0)
assert len(db.list_holdings()) == 1

db.set_active_profile("alice")
alice_holdings = db.list_holdings()
assert len(alice_holdings) == 1 and alice_holdings[0]["name"] == "Alice ETF"

assert set(db.list_profiles()) == {"alice", "bob"}

print("OK: isolamento tra profili verificato")
