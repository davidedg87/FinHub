"""Dashboard di sola visualizzazione + inserimento manuale rapido. Legge/scrive lo stesso
SQLite del MCP server: i due non si parlano direttamente, condividono solo il DB.
Avvio: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from shared import db, quotes

db.init_db()
st.set_page_config(page_title="Le mie finanze", layout="wide")
st.title("Dashboard finanze personali")

summary = db.portfolio_summary()
c1, c2, c3 = st.columns(3)
c1.metric("Patrimonio netto", f"{summary['total_net_worth']:,.2f} €")
c2.metric("Investito", f"{summary['invested_value']:,.2f} €")
c3.metric("Liquidità", f"{summary['cash_total']:,.2f} €")

if summary["by_category"]:
    fig, ax = plt.subplots()
    ax.pie(summary["by_category"].values(), labels=summary["by_category"].keys(), autopct="%1.1f%%")
    ax.set_title("Allocazione per categoria")
    st.pyplot(fig)

tab_etf, tab_btp, tab_altro, tab_cash, tab_mov = st.tabs(["ETF", "BTP", "Altri investimenti", "Liquidità", "Spese/Entrate"])


def render_holdings_tab(category, help_ticker):
    holdings = db.list_holdings(category)
    if holdings:
        df = pd.DataFrame(holdings)
        df["prezzo_corrente"] = df["manual_price"].fillna(df["avg_price"])
        df["valore"] = df["prezzo_corrente"] * df["quantity"]
        st.dataframe(
            df[["id", "name", "ticker_or_isin", "quantity", "avg_price", "prezzo_corrente", "valore", "notes"]],
            use_container_width=True,
        )
        if category == "ETF":
            refresh_id = st.selectbox("Aggiorna quotazione per id", [h["id"] for h in holdings], key=f"refresh_{category}")
            if st.button("Vai a prendere il prezzo live", key=f"btn_refresh_{category}"):
                h = next(x for x in holdings if x["id"] == refresh_id)
                price = quotes.get_etf_quote(h["ticker_or_isin"]) if h["ticker_or_isin"] else None
                if price is not None:
                    db.update_holding(refresh_id, manual_price=price)
                    st.success(f"Prezzo aggiornato: {price}")
                    st.rerun()
                else:
                    st.error("Quotazione non disponibile per questo ticker")
    else:
        st.info("Nessuna posizione registrata.")

    with st.form(f"add_{category}", clear_on_submit=True):
        st.subheader("Aggiungi posizione")
        name = st.text_input("Nome")
        ticker = st.text_input(help_ticker)
        quantity = st.number_input("Quantità", min_value=0.0, step=1.0)
        avg_price = st.number_input("Prezzo di carico", min_value=0.0, step=0.01)
        notes = st.text_input("Note", value="")
        if st.form_submit_button("Salva") and name:
            db.add_holding(category, name, ticker or None, quantity, avg_price, notes=notes or None)
            st.rerun()

    if holdings:
        del_id = st.selectbox("Elimina posizione con id", [h["id"] for h in holdings], key=f"del_{category}")
        if st.button("Elimina", key=f"btn_del_{category}"):
            db.delete_holding(del_id)
            st.rerun()


with tab_etf:
    render_holdings_tab("ETF", "Ticker (es. SWDA.MI)")

with tab_btp:
    render_holdings_tab("BTP", "ISIN (es. IT0005441883)")
    st.caption("Il prezzo dei BTP va aggiornato a mano finché non c'è una fonte automatica.")

with tab_altro:
    render_holdings_tab("ALTRO", "Ticker/ISIN (opzionale)")

with tab_cash:
    accounts = db.list_cash_accounts()
    if accounts:
        st.dataframe(pd.DataFrame(accounts), use_container_width=True)
    with st.form("cash_form", clear_on_submit=True):
        st.subheader("Imposta saldo conto")
        acc_name = st.text_input("Nome conto")
        balance = st.number_input("Saldo", step=0.01)
        if st.form_submit_button("Salva") and acc_name:
            db.upsert_cash_account(acc_name, balance)
            st.rerun()

with tab_mov:
    transactions = db.list_transactions()
    if transactions:
        st.dataframe(pd.DataFrame(transactions), use_container_width=True)
    with st.form("tx_form", clear_on_submit=True):
        st.subheader("Registra movimento")
        tx_date = st.date_input("Data", value=date.today())
        tx_type = st.selectbox("Tipo", ["expense", "income"])
        tx_category = st.text_input("Categoria")
        amount = st.number_input("Importo", min_value=0.0, step=0.01)
        description = st.text_input("Descrizione", value="")
        if st.form_submit_button("Salva") and tx_category:
            db.add_transaction(tx_date.isoformat(), tx_type, tx_category, amount, description or None)
            st.rerun()
