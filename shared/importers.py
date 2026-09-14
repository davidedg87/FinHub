"""Import di movimenti da file. Una funzione per formato, niente classi ne registry.

I tracciati bancari non differiscono per nome delle colonne: differiscono per separatore,
encoding, righe di preambolo prima dell'header, formato data e convenzione dei segni (c'e
chi mette entrate e uscite in due colonne, chi in una sola con il segno). Un dizionario di
mappature colonne avrebbe bisogno di un'escape hatch entro la seconda banca, e a quel punto
e piu lungo di tre funzioni.

Contratto di un parser: prende un path, ritorna list[dict] con tre chiavi

    {"date": "2026-02-01", "amount": -1.20, "description": "BAR SPORT PAG. CARTA *1234"}
              ISO            CON SEGNO       testo grezzo della banca

Il parser fa parsing, non semantica: income/expense lo deriva import_file dal segno.
Il giorno che arriva PSD2 e un'altra funzione che ritorna le stesse tre chiavi.
"""
import hashlib
from datetime import datetime

import pandas as pd

from . import db

# Una sola grafia, ovunque: category e testo libero e un import ne scrive centinaia di righe
# in un colpo. Due varianti ("da categorizzare" e "Da categorizzare") e il riepilogo per
# categoria smette di dire qualcosa.
CATEGORIA_DEFAULT = "da categorizzare"


def parse_generico(path) -> list[dict]:
    """CSV semplice: colonne data, importo, descrizione. Data ISO o gg/mm/aaaa, importo con
    il segno (negativo = uscita), separatore ',' o ';' dedotto da pandas.

    E il formato di riferimento: se una banca esporta qualcosa di simile, conviene passare
    da qui invece di scrivere un parser nuovo.
    """
    df = pd.read_csv(path, sep=None, engine="python", dtype=str, keep_default_na=False)
    df.columns = [c.strip().lower() for c in df.columns]
    return [
        {
            "date": _iso(r.get("data")),
            "amount": _importo(r.get("importo")),
            "description": str(r.get("descrizione", "")).strip(),
        }
        for _, r in df.iterrows()
    ]


# I parser delle singole banche si aggiungono qui, uno per fonte, guardando un export vero.
PARSERS = {
    "generico": parse_generico,
}


def formati() -> list[str]:
    return sorted(PARSERS)


# --- parsing dei campi ---

_FORMATI_DATA = ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y")


def _iso(value) -> str | None:
    """Ritorna la data in ISO, o None se non e interpretabile (chi chiama la scarta)."""
    testo = str(value or "").strip()
    for fmt in _FORMATI_DATA:
        try:
            return datetime.strptime(testo, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _importo(value) -> float | None:
    """Numero italiano (1.234,56) o inglese (1234.56) -> float con segno. None se illeggibile.

    Serve perche pandas, senza decimal=',' esplicito, lascia '1.234,56' come stringa
    SENZA sollevare nessun errore: la colonna sembra letta e invece non lo e.
    """
    testo = str(value or "").strip().replace("€", "").replace(" ", "")
    if not testo:
        return None
    if "," in testo:  # notazione italiana: il punto e separatore di migliaia
        testo = testo.replace(".", "").replace(",", ".")
    try:
        numero = float(testo)
    except ValueError:
        return None
    return None if numero != numero else numero  # scarta i NaN


def _problema(row) -> str | None:
    """Validazione al confine di fiducia: un CSV storto non deve entrare nel database.

    date e TEXT senza vincolo di formato e list_transactions ordina lessicograficamente:
    una sola riga rimasta in gg/mm/aaaa sballerebbe l'ordinamento in silenzio.
    """
    if not row.get("date"):
        return "data non interpretabile"
    if row.get("amount") is None:
        return "importo non interpretabile"
    if row["amount"] == 0:
        return "importo a zero"
    return None


# --- import ---

def import_file(path, formato: str, conto: str, categoria: str = CATEGORIA_DEFAULT) -> dict:
    """Importa i movimenti di un file in un conto. Idempotente: reimportare lo stesso file
    non duplica niente.

    Ritorna {profilo, inserite, duplicate, scartate: [{riga, motivo}]}. Una riga illeggibile
    non fa fallire l'import: finisce in scartate col motivo, cosi l'utente la vede e le altre
    entrano comunque.
    """
    if formato not in PARSERS:
        raise ValueError(f"formato sconosciuto: {formato!r}. Disponibili: {', '.join(formati())}")

    righe = PARSERS[formato](path)
    account_id = db.get_or_create_cash_account(conto)

    occorrenze, da_inserire, scartate = {}, [], []
    for riga in righe:
        motivo = _problema(riga)
        if motivo:
            scartate.append({"riga": riga, "motivo": motivo})
            continue

        importo = riga["amount"]
        descrizione = " ".join(str(riga.get("description") or "").lower().split())
        # Importo CON SEGNO nella chiave: un rimborso di +1,20 non deve collidere con un
        # addebito di -1,20. E niente categoria: la assegniamo noi, non la banca, quindi
        # ricategorizzare una riga la renderebbe reimportabile.
        base = f"{account_id}|{riga['date']}|{importo:.2f}|{descrizione}"
        # L'occorrenza e posizionale DENTRO il file, mai contata sulle righe gia a database:
        # contarle a database farebbe assegnare 3 e 4 al secondo import, duplicando tutto.
        # Cosi invece due caffe identici lo stesso giorno restano due righe (occorrenza 1 e 2)
        # e lo stesso file reimportato rifa 1 e 2, quindi non inserisce niente.
        # ponytail: un estratto che si sovrappone solo in parte a uno gia importato puo
        # sottostimare l'occorrenza -> riga saltata, mai duplicata. Se serve esattezza, il
        # parser metta il riferimento univoco della banca (CRO, numero movimento) in description.
        occorrenze[base] = occorrenze.get(base, 0) + 1
        da_inserire.append((
            riga["date"],
            "income" if importo > 0 else "expense",
            categoria,
            abs(importo),
            riga.get("description"),
            account_id,
            hashlib.sha256(f"{base}|{occorrenze[base]}".encode()).hexdigest()[:16],
        ))

    inserite, duplicate = db.add_imported_transactions(da_inserire)
    return {
        # Il profilo attivo di QUESTO processo: db.DB_PATH e un global risolto all'import e
        # i due frontend non si accorgono a vicenda del cambio profilo. Averlo nel report
        # rende visibile subito un import finito nel posto sbagliato.
        "profilo": db.get_active_profile(),
        "inserite": inserite,
        "duplicate": duplicate,
        "scartate": scartate,
    }
