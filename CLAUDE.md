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
python tests/test_profiles.py
python tests/test_server.py
```
The pre-commit hook (`.claude/hooks/pre-commit-tests.sh`) runs all of them before every `git commit`.

The MCP server auto-starts when Claude Code opens this folder (configured in `.mcp.json`).

## Architecture

FinHub: personal finance aggregator with two independent frontends sharing a single SQLite database.

### Layer 1: Shared Data Layer (`shared/`)
- **`db.py`**: SQLite schema (holdings, cash_accounts, transactions) and CRUD functions. Single source of truth.
  `prezzo_corrente(holding)` holds the price precedence rule in one place: `manual_price` > `market_price` > `avg_price`.
- **`quotes.py`**: quotes from two sources, picked by symbol shape — ticker (SWDA.MI) via yfinance, ISIN (IT0005441883)
  from the Borsa Italiana MOT page. `get_quote()` returns `{price, source, as_of, error}` so a bad symbol and an
  unreachable network stay distinguishable.
- **`importers.py`**: one parser per file format, each returning `[{date ISO, amount signed, description}]`.
  `import_file()` is idempotent — re-importing the same statement inserts nothing.

### Layer 2: MCP Servers (`mcp_server/`)
Two servers, two domains. `server.py` (**finance-data**) exposes the portfolio — the user's state.
`market_data.py` (**market-data**) exposes the market — the world's state, plus the resource `market://symbols`.
Neither holds state: they always read/write the shared database.

**Tools exposed (14):**
- `list_holdings()`, `add_holding()`, `update_holding_price()`, `update_holding_notes()`, `delete_holding()`
- `list_cash_accounts()`, `set_cash_balance()`
- `add_transaction()`, `list_transactions()`
- `refresh_etf_quote()`, `portfolio_summary()`
- `list_profiles()`, `get_active_profile()`, `set_active_profile()`

**market-data tools:** `get_quote()`, `refresh_all_quotes()` · **resource:** `market://symbols`

### Layer 3: Streamlit Dashboard (`dashboard/app.py`)
Web UI for viewing the portfolio, updating prices, importing statements, and adding transactions manually.

**File import lives here and NOT in the MCP tools, on purpose.** `db.DB_PATH` is a module global resolved at
import time, and the MCP server is a separate process that does not see a profile switch made in the dashboard.
Getting the profile wrong costs one row when typing a single expense; it costs a 400-row statement on import.

The two frontends do **not** communicate with each other—they only share the database file. This keeps them independent: no API coupling, no state synchronization.

## Database

**One SQLite file per profile**: `data/profiles/<profile>.db`. The active profile name lives in
`data/active_profile.txt`; isolation is at the file level, so there is no `profile_id` column to
filter on. `data/portfolio.db` is the pre-profiles legacy path, migrated once to `default.db`.

Careful: `db.DB_PATH` is a module global resolved at import time. The MCP server and Streamlit are
separate processes and do **not** see each other's profile switch until restarted.

Three tables:

| Table | Purpose |
|-------|---------|
| `holdings` | ETF, BTP, and other investments: quantity, prices (avg and current manual), ticker/ISIN, notes |
| `cash_accounts` | Named accounts with balances (checking, savings, etc.) |
| `transactions` | Income and expense records with date, category, amount, `account_id`, `dedup_key` |

**Schema changes go in `MIGRATIONS` in `db.py`, never by editing `SCHEMA`** — `SCHEMA` is frozen at the v0 shape,
and `PRAGMA user_version` tracks how far a file has come, so fresh and existing databases walk the same path.

`FINHUB_DATA_DIR` moves the whole data directory elsewhere — the way to point a separate process (an MCP server
launched by a client) at a test fixture, since monkeypatching `db.DATA_DIR` only affects the process that does it.

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

Three self-checks, no fixtures and no framework: plain scripts with top-level `assert` that monkeypatch
`db.DB_PATH` onto a temp dir and print `OK`. Keep new tests in that style.

- `test_db.py` — schema and core logic (holdings CRUD, portfolio summary, transactions).
- `test_profiles.py` — profile isolation (two profiles never see each other's data).
- `test_server.py` — the only MCP-layer logic worth testing: `add_holding`'s automatic price fetch.
- `test_migrations.py` — the migration is idempotent, rolls back whole on failure, and NULL `dedup_key`s don't collide.
- `test_import.py` — re-importing a file inserts nothing, but two genuinely identical rows stay two rows.
- `test_market_data.py` — the only test that speaks MCP: real stdio handshake, `list_tools`, `read_resource`.
  `mcp_inspector.py` calls the Python functions in-process, so it covers neither transport nor schemas.

Run them before pushing changes to `shared/db.py`.

## Project-Specific Rules

**These are non-negotiable conventions for this repository:**

- **Database schema changes only via `shared/db.py`** — Never write direct SQL or schema modifications elsewhere. All CRUD goes through the functions in `db.py`.
- **Git user is `davidedg87`** — Commits in this repo always use the personal git user `davidedg87`, never the corporate user.
- **`manual_price` is the user's word, `market_price` is the market's** — a quote refresh writes `market_price`
  and must never overwrite `manual_price`. BTP prices can now be fetched from the MOT via `market-data`, but a
  hand-entered price still wins.

## Notes

- **No authentication**: designed for local personal use only. Do not expose to the network.
- **ETF quotes only**: yfinance covers Borsa Italiana (ticker suffix `.MI`). BTP prices go into `holdings.manual_price` until a reliable free source is added.
- **MCP registration**: `.mcp.json` points to the local venv Python. If you move the venv, update the `command` path to `.venv\Scripts\python.exe` absolute path.
