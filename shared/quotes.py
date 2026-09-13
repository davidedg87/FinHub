"""Fetch quotazioni live. Solo ETF per ora: yfinance copre bene i ticker di Borsa Italiana
(suffisso .MI, es. SWDA.MI). Per i BTP non esiste una fonte gratuita altrettanto affidabile:
il prezzo va aggiornato a mano in holdings.manual_price finché non si aggiunge una fonte vera
(es. scraping Borsa Italiana/MOT).
"""
import yfinance as yf


def get_etf_quote(ticker: str) -> float | None:
    try:
        data = yf.Ticker(ticker).fast_info
        price = data.get("lastPrice") or data.get("last_price")
        return float(price) if price else None
    except Exception:
        return None
