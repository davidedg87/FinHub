"""Self-check del server MCP market-data, sul protocollo vero.

E l'unico test del repo che parla MCP: avvia il server come processo separato su stdio e
fa handshake, list_tools, list_resources e read_resource come farebbe un client. Il
mcp_inspector chiama le funzioni Python in-process, quindi non copre trasporto, schemi
e serializzazione - cioe esattamente quello che si rompe aggiornando l'SDK.

Niente rete: la posizione di prova non ha ticker, quindi nessuna quotazione viene richiesta.
Esegui: python tests/test_market_data.py
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import shared.db as db

RADICE = Path(__file__).resolve().parent.parent

# Un profilo tutto nostro in una tempdir: il server e un processo separato e risolve il
# profilo attivo da solo, quindi lo si pilota dall'ambiente, non monkeypatchando db.DB_PATH.
tmp = Path(tempfile.mkdtemp())
profilo = "test-market-data"
(tmp / "profiles").mkdir()
(tmp / "active_profile.txt").write_text(profilo)

db.DATA_DIR = tmp
db.PROFILES_DIR = tmp / "profiles"
db.ACTIVE_PROFILE_FILE = tmp / "active_profile.txt"
db.DB_PATH = tmp / "profiles" / f"{profilo}.db"
db.init_db()
db.add_holding("BTP", "BTP Mz72", None, quantity=1000, avg_price=98.0, manual_price=53.81)
db.add_holding("ETF", "Senza prezzo", None, quantity=10, avg_price=100.0)


async def main():
    # FINHUB_DATA_DIR: il server e un altro processo e non vede i nostri monkeypatch,
    # quindi lo si punta alla cartella di prova dall'ambiente.
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "FINHUB_DATA_DIR": str(tmp)}
    parametri = StdioServerParameters(
        command=sys.executable,
        args=[str(RADICE / "mcp_server" / "market_data.py")],
        env=ambiente,
        cwd=str(RADICE),
    )
    async with stdio_client(parametri) as (leggi, scrivi):
        async with ClientSession(leggi, scrivi) as sessione:
            await sessione.initialize()

            nomi_tool = {t.name for t in (await sessione.list_tools()).tools}
            assert nomi_tool == {"get_quote", "refresh_all_quotes"}, nomi_tool

            risorse = (await sessione.list_resources()).resources
            uri = {str(r.uri) for r in risorse}
            assert "market://symbols" in uri, uri

            # get_quote su un simbolo vuoto: risponde senza rete e senza sollevare
            esito = await sessione.call_tool("get_quote", {"ticker_or_isin": ""})
            assert esito.structured_content["error"] == "simbolo vuoto", esito.structured_content

            # la resource si legge davvero e riporta le due posizioni del profilo di prova
            letto = await sessione.read_resource("market://symbols")
            payload = json.loads(letto.contents[0].text)
            assert payload["profilo"] == profilo, payload["profilo"]
            per_nome = {s["nome"]: s for s in payload["simboli"]}
            assert per_nome["BTP Mz72"]["fonte"] == "manuale"
            assert per_nome["BTP Mz72"]["prezzo_in_uso"] == 53.81
            # senza manual_price ne market_price si ricade sul prezzo di carico
            assert per_nome["Senza prezzo"]["fonte"] == "prezzo di carico"
            assert per_nome["Senza prezzo"]["prezzo_in_uso"] == 100.0

            print("OK: handshake, 2 tool, market://symbols letta sul protocollo")


asyncio.run(main())
