"""Server MCP market-data: quotazioni e stato dei prezzi del portafoglio.

Separato da finance-data di proposito: quello espone il portafoglio (stato dell'utente),
questo espone il mercato (stato del mondo). Due domini, due server.

Avvio manuale: python mcp_server/market_data.py  (trasporto stdio)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from typing import TypedDict

from mcp.server.mcpserver import MCPServer

from shared import db, quotes

mcp = MCPServer("market-data")


class Quotazione(TypedDict):
    """Il tipo di ritorno serve all'SDK per pubblicare un output schema: senza, un dict
    nudo torna al client solo come testo JSON e il tool non si autodescrive."""
    price: float | None
    source: str | None
    as_of: str | None
    error: str | None


@mcp.tool()
def get_quote(ticker_or_isin: str) -> Quotazione:
    """Quotazione di un simbolo. Ticker di Borsa Italiana (es. SWDA.MI) via yfinance,
    ISIN (es. IT0005441883) dal prezzo ufficiale MOT di Borsa Italiana.

    Ritorna price, source, as_of ed error: se price e None, error dice perche
    (simbolo inesistente, rete non raggiungibile, layout della pagina cambiato).
    """
    return quotes.get_quote(ticker_or_isin)


@mcp.tool()
def refresh_all_quotes() -> dict:
    """Aggiorna la quotazione di tutte le posizioni che hanno un ticker o un ISIN.

    Scrive in market_price, mai in manual_price: un prezzo dichiarato a mano dall'utente
    non viene sovrascritto da un refresh. Ritorna quante aggiornate e gli errori per simbolo.
    """
    aggiornate, errori = 0, {}
    for h in db.list_holdings():
        simbolo = h.get("ticker_or_isin")
        if not simbolo:
            continue
        esito = quotes.get_quote(simbolo)
        if esito["price"] is None:
            errori[simbolo] = esito["error"]
            continue
        db.update_holding(h["id"], market_price=esito["price"], market_price_at=esito["as_of"])
        aggiornate += 1
    return {"aggiornate": aggiornate, "errori": errori}


@mcp.resource(
    "market://symbols",
    name="Simboli del portafoglio",
    description="I simboli presenti in portafoglio con prezzo in uso, fonte e data dell'ultima quotazione.",
    mime_type="application/json",
)
def symbols() -> str:
    """Fotografia dei prezzi: cosa stiamo usando per valutare ogni posizione e quanto e vecchio.

    Non va a interrogare il mercato: legge quello che c'e a database. Serve a rispondere a
    'su quali simboli ho quotazioni, e quanto sono aggiornate' senza fare N chiamate di rete.
    """
    righe = []
    for h in db.list_holdings():
        prezzo = db.prezzo_corrente(h)
        if h.get("manual_price") is not None:
            fonte, aggiornato_al = "manuale", h.get("updated_at")
        elif h.get("market_price") is not None:
            fonte, aggiornato_al = "mercato", h.get("market_price_at")
        else:
            fonte, aggiornato_al = "prezzo di carico", None
        righe.append({
            "id": h["id"],
            "nome": h["name"],
            "categoria": h["category"],
            "simbolo": h.get("ticker_or_isin"),
            "prezzo_in_uso": prezzo,
            "fonte": fonte,
            "aggiornato_al": aggiornato_al,
        })
    return json.dumps(
        {"profilo": db.get_active_profile(), "simboli": righe},
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    mcp.run()
