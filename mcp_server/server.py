"""MCP server 'finance-data': espone il portafoglio a Claude via tool.
Registralo in Claude Code/Desktop (vedi .mcp.json) e poi chiedi in chat, es.
'aggiungi 10 quote di SWDA.MI a 85 euro' oppure 'quanto vale il mio patrimonio'.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer
from shared import db, importers, quotes

db.init_db()
mcp = MCPServer("finance-data")


@mcp.tool()
def list_profiles() -> list[str]:
    """Elenca i profili esistenti (ognuno con il proprio portafoglio separato)."""
    return db.list_profiles()


@mcp.tool()
def get_active_profile() -> str:
    """Ritorna il nome del profilo attualmente attivo."""
    return db.get_active_profile()


@mcp.tool()
def set_active_profile(name: str) -> str:
    """Passa al profilo indicato (lo crea vuoto se non esiste). Le operazioni successive agiscono sul suo portafoglio."""
    db.set_active_profile(name)
    return f"profilo attivo: {name}"


@mcp.tool()
def list_holdings(category: str | None = None) -> list[dict]:
    """Elenca le posizioni in portafoglio (ETF, BTP, ALTRO). Filtra per categoria se indicata."""
    return db.list_holdings(category)


@mcp.tool()
def add_holding(
    category: str,
    name: str,
    quantity: float,
    avg_price: float | None = None,
    ticker_or_isin: str | None = None,
    currency: str = "EUR",
    notes: str | None = None,
) -> int:
    """Aggiunge una posizione. category deve essere 'ETF', 'BTP' o 'ALTRO'.
    Se avg_price non è fornito ma il ticker è presente, recupera il prezzo corrente da yfinance."""
    if avg_price is None:
        if not ticker_or_isin:
            raise ValueError("Devi fornire avg_price oppure un ticker valido.")
        price = quotes.get_etf_quote(ticker_or_isin)
        if price is None:
            raise ValueError(f"Impossibile recuperare il prezzo per {ticker_or_isin}. Specifica avg_price manualmente.")
        avg_price = price
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
    esito = quotes.get_quote(holding["ticker_or_isin"])
    if esito["price"] is None:
        return f"quotazione non disponibile: {esito['error']}"
    # market_price e non manual_price: quest'ultima e quello che l'utente afferma a mano
    # (i BTP) e un refresh non deve sovrascriverlo.
    db.update_holding(holding_id, market_price=esito["price"], market_price_at=esito["as_of"])
    return f"prezzo aggiornato: {esito['price']} ({esito['source']}, {esito['as_of']})"


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
def update_transaction(transaction_id: int, category: str | None = None, date: str | None = None,
                       amount: float | None = None, description: str | None = None) -> str:
    """Corregge una transazione esistente. Passa solo i campi da cambiare.
    Serve anche per ricategorizzare quello che un import ha messo in 'da categorizzare'."""
    campi = {k: v for k, v in
             {"category": category, "date": date, "amount": amount, "description": description}.items()
             if v is not None}
    if not campi:
        return "nessun campo da aggiornare"
    db.update_transaction(transaction_id, **campi)
    return f"transazione {transaction_id} aggiornata: {', '.join(campi)}"


@mcp.tool()
def delete_transaction(transaction_id: int) -> str:
    """Cancella una transazione. Definitivo: non c'e cestino, chiedi conferma prima."""
    db.delete_transaction(transaction_id)
    return f"transazione {transaction_id} cancellata"


@mcp.tool()
def list_import_formats() -> list[str]:
    """Formati di file che l'import sa leggere (da passare a import_transactions_file)."""
    return importers.formati()


@mcp.tool()
def import_transactions_file(path: str, formato: str, conto: str, profilo: str) -> dict:
    """Importa i movimenti di un file in un conto. Idempotente: reimportare lo stesso file
    non duplica niente. Ritorna quante inserite, quante gia presenti e quali scartate e perche.

    profilo e OBBLIGATORIO e deve gia esistere. Non e una formalita: db.DB_PATH e un global
    risolto all'import e questo server e un processo diverso dalla dashboard, quindi non vede
    i cambi di profilo fatti li. Farlo dichiarare a chi chiama e il modo piu corto per non
    scaricare centinaia di righe nel portafoglio sbagliato, da cui non si torna facilmente
    indietro. Chiedi conferma all'utente prima di chiamare questo tool.
    """
    with db.profilo(profilo):
        return importers.import_file(path, formato, conto)


@mcp.tool()
def portfolio_summary() -> dict:
    """Riepilogo: valore investito, liquidità totale, patrimonio netto, ripartizione per categoria."""
    return db.portfolio_summary()


if __name__ == "__main__":
    mcp.run()
