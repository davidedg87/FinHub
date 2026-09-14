"""Fetch quotazioni. Due fonti, scelte dal formato del simbolo:

- ticker di Borsa Italiana (SWDA.MI) -> yfinance
- ISIN (IT0005441883)                -> scheda MOT di Borsa Italiana, prezzo ufficiale

get_quote() ritorna sempre un dizionario e dice ANCHE perche non ce l'ha fatta: un
ticker inesistente e la rete giu sono problemi diversi e vanno distinti da chi chiama.
get_etf_quote() resta come scorciatoia per il codice che vuole solo il numero.
"""
import re
import urllib.error
import urllib.request
from datetime import datetime

import yfinance as yf

# ISIN: 2 lettere di paese + 9 alfanumerici + 1 cifra di controllo
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")

_MOT_URL = "https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp/scheda/{isin}.html"
# La scheda MOT mette etichetta e valore in due <td> affiancati.
_MOT_RIGA = r"<strong>\s*{etichetta}\s*</strong>.*?<span[^>]*>\s*({valore})\s*</span>"


def get_quote(ticker_or_isin: str) -> dict:
    """{"price": float|None, "source": str, "as_of": str|None, "error": str|None}.

    price None + error valorizzato = non ce l'ha fatta, e error dice perche.
    """
    simbolo = (ticker_or_isin or "").strip().upper()
    if not simbolo:
        return {"price": None, "source": None, "as_of": None, "error": "simbolo vuoto"}
    if _ISIN.fullmatch(simbolo):
        return _quota_mot(simbolo)
    return _quota_yfinance(simbolo)


def get_etf_quote(ticker: str) -> float | None:
    """Solo il prezzo, per chi non ha bisogno di sapere perche manca."""
    return get_quote(ticker)["price"]


def _quota_yfinance(ticker: str) -> dict:
    esito = {"price": None, "source": "yfinance", "as_of": None, "error": None}
    try:
        info = yf.Ticker(ticker).fast_info
        prezzo = info.get("lastPrice") or info.get("last_price")
    except KeyError:
        esito["error"] = f"nessuna quotazione per {ticker} (ticker inesistente?)"
        return esito
    except Exception as e:
        esito["error"] = f"yfinance non raggiungibile: {type(e).__name__}"
        return esito
    if prezzo is None:
        esito["error"] = f"nessuna quotazione per {ticker} (ticker inesistente?)"
        return esito
    esito["price"] = float(prezzo)
    esito["as_of"] = datetime.now().isoformat(timespec="seconds")
    return esito


def _quota_mot(isin: str) -> dict:
    """Prezzo ufficiale dalla scheda MOT. E scraping di una pagina pubblica: se Borsa
    Italiana cambia il layout, error lo dice invece di restituire un numero sbagliato.
    """
    esito = {"price": None, "source": "borsaitaliana-mot", "as_of": None, "error": None}
    richiesta = urllib.request.Request(
        _MOT_URL.format(isin=isin), headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=20) as risposta:
            pagina = risposta.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        esito["error"] = f"ISIN non trovato sul MOT (HTTP {e.code})" if e.code == 404 else f"HTTP {e.code}"
        return esito
    except Exception as e:
        esito["error"] = f"Borsa Italiana non raggiungibile: {type(e).__name__}"
        return esito

    if isin not in pagina:
        esito["error"] = f"ISIN {isin} non presente sul MOT"
        return esito

    prezzo = _campo(pagina, "Prezzo ufficiale") or _campo(pagina, "Prezzo di riferimento")
    if prezzo is None:
        esito["error"] = "prezzo non trovato nella pagina (layout cambiato?)"
        return esito
    esito["price"] = prezzo
    esito["as_of"] = _data(_campo_testo(pagina, "Data Pr Ufficiale", r"[\d/]+"))
    return esito


def _campo_testo(pagina: str, etichetta: str, valore: str = r"[\d.,]+") -> str | None:
    pattern = _MOT_RIGA.replace("{etichetta}", re.escape(etichetta)).replace("{valore}", valore)
    m = re.search(pattern, pagina, re.S)
    return m.group(1) if m else None


def _campo(pagina: str, etichetta: str) -> float | None:
    testo = _campo_testo(pagina, etichetta)
    if not testo:
        return None
    try:  # notazione italiana: 1.234,56
        return float(testo.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _data(testo: str | None) -> str:
    """gg/mm/aa della scheda MOT -> ISO. Se manca o e illeggibile, vale adesso."""
    if testo:
        for fmt in ("%d/%m/%y", "%d/%m/%Y"):
            try:
                return datetime.strptime(testo.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return datetime.now().isoformat(timespec="seconds")
