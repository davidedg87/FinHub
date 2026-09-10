# Finance Dashboard

Progetto personale per monitorare ETF, BTP, liquidità e spese/entrate.

## Struttura

- `shared/db.py` — schema SQLite e CRUD, unica fonte di verità (`data/portfolio.db`).
- `shared/quotes.py` — fetch quotazioni ETF live (yfinance). I BTP si aggiornano a mano.
- `mcp_server/server.py` — server MCP: espone il portafoglio a Claude come tool
  (aggiungi/leggi posizioni, aggiorna prezzi, riepilogo patrimonio).
- `dashboard/app.py` — dashboard Streamlit: visualizzazione e inserimento manuale.

I due frontend (Claude via MCP, e Streamlit) non comunicano tra loro: condividono solo
lo stesso file SQLite.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Avvio dashboard

```
streamlit run dashboard/app.py
```

## Registrare il server MCP in Claude Code

Il file `.mcp.json` nella root registra già il server per Claude Code, che lo avvia
automaticamente quando apri questa cartella come progetto. Se usi un virtualenv, aggiorna
il campo `command` con il path assoluto a `.venv\Scripts\python.exe`.

Poi in chat puoi chiedere ad esempio:
- "aggiungi 10 quote di SWDA.MI comprate a 85"
- "quanto vale il mio patrimonio netto"
- "aggiorna la quotazione di SWDA.MI"

## Test

```
python tests/test_db.py
```

## Limiti noti

- BTP: nessuna fonte gratuita affidabile per il fetch automatico, prezzo manuale via
  `update_holding_price` (MCP) o dalla dashboard.
- Nessuna autenticazione: pensato per uso locale personale, non per essere esposto in rete.
