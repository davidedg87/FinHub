"""MCP server 'finance-data': espone il portafoglio a Claude via tool.
Registralo in Claude Code/Desktop (vedi .mcp.json) e poi chiedi in chat, es.
'aggiungi 10 quote di SWDA.MI a 85 euro' oppure 'quanto vale il mio patrimonio'.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer
from shared import db, quotes

db.init_db()
mcp = MCPServer("finance-data")


@mcp.tool()
def list_holdings(category: str | None = None) -> list[dict]:
    """Elenca le posizioni in portafoglio (ETF, BTP, ALTRO). Filtra per categoria se indicata."""
    return db.list_holdings(category)


@mcp.tool()
def add_holding(
    category: str,
    name: str,
    quantity: float,
    avg_price: float,
    ticker_or_isin: str | None = None,
    currency: str = "EUR",
    notes: str | None = None,
) -> int:
    """Aggiunge una posizione. category deve essere 'ETF', 'BTP' o 'ALTRO'. Ritorna l'id creato."""
    return db.add_holding(category, name, ticker_or_isin, quantity, avg_price, currency=currency, notes=notes)


@mcp.tool()
def update_holding_price(holding_id: int, price: float) -> str:
    """Aggiorna manualmente il prezzo corrente di una posizione (uso tipico: BTP)."""
    db.update_holding(holding_id, manual_price=price)
    return "ok"


@mcp.tool()
def update_holding_notes(holding_id: int, notes: str | None) -> str:
    """Aggiorna le note di una posizione esistente."""
    db.update_holding(holding_id, notes=notes)
    return "ok"


@mcp.tool()
def delete_holding(holding_id: int) -> str:
    """Rimuove una posizione dal portafoglio."""
    db.delete_holding(holding_id)
    return "ok"


@mcp.tool()
def refresh_etf_quote(holding_id: int) -> str:
    """Va a prendere il prezzo live per una posizione ETF (serve il ticker, es. SWDA.MI) e lo salva."""
    holdings = {h["id"]: h for h in db.list_holdings("ETF")}
    holding = holdings.get(holding_id)
    if not holding or not holding["ticker_or_isin"]:
        return "holding non trovato o senza ticker"
    price = quotes.get_etf_quote(holding["ticker_or_isin"])
    if price is None:
        return "quotazione non disponibile"
    db.update_holding(holding_id, manual_price=price)
    return f"prezzo aggiornato: {price}"


@mcp.tool()
def set_cash_balance(account_name: str, balance: float) -> str:
    """Imposta il saldo di un conto/liquidità (crea il conto se non esiste)."""
    db.upsert_cash_account(account_name, balance)
    return "ok"


@mcp.tool()
def list_cash_accounts() -> list[dict]:
    """Elenca i conti di liquidità con il relativo saldo."""
    return db.list_cash_accounts()


@mcp.tool()
def add_transaction(date: str, type: str, category: str, amount: float, description: str | None = None) -> int:
    """Registra un'entrata o un'uscita. date in formato YYYY-MM-DD, type 'income' o 'expense'."""
    return db.add_transaction(date, type, category, amount, description)


@mcp.tool()
def list_transactions(limit: int = 50) -> list[dict]:
    """Elenca le ultime transazioni (spese/entrate), più recenti prima."""
    return db.list_transactions(limit)


@mcp.tool()
def portfolio_summary() -> dict:
    """Riepilogo: valore investito, liquidità totale, patrimonio netto, ripartizione per categoria."""
    return db.portfolio_summary()


if __name__ == "__main__":
    mcp.run()
