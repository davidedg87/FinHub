"""Self-check sull'import di movimenti da file (shared/importers.py).
Il punto che deve reggere: reimportare lo stesso estratto non duplica niente, ma due
movimenti realmente identici nello stesso file restano due righe.
Esegui: python tests/test_import.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.db as db
import shared.importers as imp

tmp = Path(tempfile.mkdtemp())
db.DB_PATH = tmp / "test_import.db"
db.init_db()


def scrivi(nome, testo):
    path = tmp / nome
    path.write_text(testo, encoding="utf-8")
    return path


# --- due movimenti identici nello stesso file sono due righe legittime ---
# Due caffe da 1,20 lo stesso giorno allo stesso bar non sono un duplicato.

estratto = scrivi("estratto.csv", """data;importo;descrizione
15/01/2026;-1,20;BAR SPORT
15/01/2026;-1,20;BAR SPORT
16/01/2026;1.234,56;STIPENDIO
17/01/2026;-1,20;BAR SPORT RIMBORSO
""")

r = imp.import_file(estratto, "generico", "Conto ING")
assert r["inserite"] == 4, r
assert r["duplicate"] == 0, r
assert r["scartate"] == [], r
assert r["profilo"] == db.get_active_profile()

# --- lo stesso file reimportato non inserisce niente ---

r2 = imp.import_file(estratto, "generico", "Conto ING")
assert r2["inserite"] == 0, r2
assert r2["duplicate"] == 4, r2
assert len(db.list_transactions()) == 4, "l'import ripetuto ha duplicato delle righe"

# --- il segno diventa income/expense, l'importo va a database positivo ---

per_descrizione = {t["description"]: t for t in db.list_transactions()}
assert per_descrizione["STIPENDIO"]["type"] == "income"
assert abs(per_descrizione["STIPENDIO"]["amount"] - 1234.56) < 1e-6, "numero italiano letto male"
assert per_descrizione["BAR SPORT"]["type"] == "expense"
assert per_descrizione["BAR SPORT"]["amount"] == 1.20

# --- tutte le righe sono legate al conto, che e stato creato con saldo a zero ---

conti = db.list_cash_accounts()
assert len(conti) == 1 and conti[0]["name"] == "Conto ING"
assert conti[0]["balance"] == 0, "l'import non deve toccare il saldo"
assert all(t["account_id"] == conti[0]["id"] for t in db.list_transactions())

# get_or_create su un conto che esiste gia non ne crea un altro e non azzera il saldo
db.upsert_cash_account("Conto ING", 2500.0)
assert db.get_or_create_cash_account("Conto ING") == conti[0]["id"]
assert db.list_cash_accounts()[0]["balance"] == 2500.0, "il saldo e stato riscritto"

# --- le righe illeggibili non fanno fallire l'import: le altre entrano ---

sporco = scrivi("sporco.csv", """data;importo;descrizione
20/01/2026;-10,00;BUONA
non-una-data;-10,00;DATA ROTTA
21/01/2026;;IMPORTO VUOTO
22/01/2026;0,00;IMPORTO A ZERO
""")

r3 = imp.import_file(sporco, "generico", "Conto ING")
assert r3["inserite"] == 1, r3
motivi = sorted(s["motivo"] for s in r3["scartate"])
assert motivi == ["data non interpretabile", "importo a zero", "importo non interpretabile"], motivi
assert all(t["date"] != "non-una-data" for t in db.list_transactions()), "riga rotta finita a database"

# --- conti diversi non si mescolano: stessa riga, conto diverso, chiave diversa ---

r4 = imp.import_file(estratto, "generico", "Conto Directa")
assert r4["inserite"] == 4, r4
assert len(db.list_transactions()) == 9, "4 + 1 + 4"

# --- formato sconosciuto: errore chiaro, non un crash oscuro ---

try:
    imp.import_file(estratto, "banca-inesistente", "Conto ING")
    raise AssertionError("un formato sconosciuto doveva sollevare ValueError")
except ValueError as e:
    assert "generico" in str(e), "l'errore deve elencare i formati disponibili"

print("OK: import idempotente, righe identiche conservate, righe rotte scartate")
