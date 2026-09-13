# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

**Setup:**
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Run dashboard (Streamlit UI):**
```
streamlit run dashboard/app.py
```

**Run MCP inspector (test tools locally):**
```
streamlit run dashboard/mcp_inspector.py
```

**Run tests:**
```
python tests/test_db.py
```

The MCP server auto-starts when Claude Code opens this folder (configured in `.mcp.json`).

## Architecture

Personal finance tracker with two independent frontends sharing a single SQLite database.

### Layer 1: Shared Data Layer (`shared/`)
- **`db.py`**: SQLite schema (holdings, cash_accounts, transactions) and CRUD functions. Single source of truth.
- **`quotes.py`**: Live quote fetching (yfinance for ETF tickers like SWDA.MI). BTP prices are manual.

### Layer 2: MCP Server (`mcp_server/server.py`)
Exposes portfolio operations as MCP tools for Claude via the Model Context Protocol. No state—always reads/writes the shared database.

**Tools exposed:**
- `list_holdings()`, `add_holding()`, `update_holding_price()`, `delete_holding()`
- `list_cash_accounts()`, `set_cash_balance()`
- `add_transaction()`, `list_transactions()`
- `refresh_etf_quote()`, `portfolio_summary()`

### Layer 3: Streamlit Dashboard (`dashboard/app.py`)
Web UI for viewing portfolio, updating prices, and adding transactions manually. Reads/writes the same SQLite database.

The two frontends do **not** communicate with each other—they only share the database file. This keeps them independent: no API coupling, no state synchronization.

## Database

SQLite file at `data/portfolio.db`. Three tables:

| Table | Purpose |
|-------|---------|
| `holdings` | ETF, BTP, and other investments: quantity, prices (avg and current manual), ticker/ISIN, notes |
| `cash_accounts` | Named accounts with balances (checking, savings, etc.) |
| `transactions` | Income and expense records with date, category, amount |

## When to Add Code

**New MCP tool?** Add a function to `shared/db.py`, then decorate it in `mcp_server/server.py`:
```python
@mcp.tool()
def my_new_tool(param: str) -> result_type:
    """Docstring becomes tool description."""
    return db.my_new_function(param)
```

**New dashboard view?** Add a Streamlit tab or section to `dashboard/app.py`.

**Quote source for BTP?** Replace/extend `quotes.py` with a real source (Borsa Italiana scraper, etc.). Return `float | None` from `get_etf_quote()` signature.

## Test

`test_db.py` is the single self-check: sets up a temp DB, exercises the schema and core logic (holdings CRUD, portfolio summary, transactions), clears, and verifies. No fixtures or frameworks. Run it before pushing changes to `shared/db.py`.

## Project-Specific Rules

**These are non-negotiable conventions for this repository:**

- **Database schema changes only via `shared/db.py`** — Never write direct SQL or schema modifications elsewhere. All CRUD goes through the functions in `db.py`.
- **Git user is `davidedg87`** — Commits in this repo always use the personal git user `davidedg87`, never the corporate user.
- **BTP prices are manual** — Treasury bond prices have no automated fetch. Update them via the `update_holding_price` MCP tool or the Streamlit dashboard UI only.

## Notes

- **No authentication**: designed for local personal use only. Do not expose to the network.
- **ETF quotes only**: yfinance covers Borsa Italiana (ticker suffix `.MI`). BTP prices go into `holdings.manual_price` until a reliable free source is added.
- **MCP registration**: `.mcp.json` points to the local venv Python. If you move the venv, update the `command` path to `.venv\Scripts\python.exe` absolute path.
