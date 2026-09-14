# FinHub

Accentratore personale di finanza: ETF, BTP, liquidità e movimenti di più fonti
(conto corrente, conto titoli, titoli di stato) in un'unica vista.

## Struttura

- `shared/db.py` — schema SQLite e CRUD, unica fonte di verità.
  Un database per profilo: `data/profiles/<profilo>.db`, con il profilo attivo in
  `data/active_profile.txt`.
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

## Inspector locale per MCP

Se vuoi una UI in stile Inspector per testare i tool MCP del server Python del progetto:

```
streamlit run dashboard/mcp_inspector.py
```

La pagina mostra:
- lista tool disponibili (letti dal modulo `mcp_server/server.py`)
- firma e descrizione del tool
- invocazione con payload JSON
- risultato e storico chiamate

## Registrare il server MCP in Claude Code

Il file `.mcp.json` nella root registra già il server per Claude Code, che lo avvia
automaticamente quando apri questa cartella come progetto. Se usi un virtualenv, aggiorna
il campo `command` con il path assoluto a `.venv\Scripts\python.exe`.

Poi in chat puoi chiedere ad esempio:
- "aggiungi 10 quote di SWDA.MI comprate a 85"
- "quanto vale il mio patrimonio netto"
- "aggiorna la quotazione di SWDA.MI"

## Test

Script con `assert`, senza framework. Lo hook di pre-commit li esegue tutti prima di
ogni `git commit`.

```
python tests/test_db.py
python tests/test_profiles.py
python tests/test_server.py
```

## Limiti noti

- BTP: nessuna fonte gratuita affidabile per il fetch automatico, prezzo manuale via
  `update_holding_price` (MCP) o dalla dashboard.
- Nessuna autenticazione: pensato per uso locale personale, non per essere esposto in rete.
