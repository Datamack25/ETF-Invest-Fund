"""
data_fetcher.py — Récupération des prix
=========================================
Stratégie : Google Finance (scraping) en PRIORITÉ,
puis Yahoo Finance (yfinance) en FALLBACK si Google échoue.

Chaque prix retourné indique sa source : "Google Finance" ou "Yahoo Finance".
"""

import re
import requests
import pandas as pd
import streamlit as st

try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
}

# ---------------------------------------------------------------------------
# INDICES MONDIAUX — mapping Google Finance <-> Yahoo Finance
# (repris de ta feuille Gestion_Portfeuille)
# ---------------------------------------------------------------------------
WORLD_INDICES = {
    # nom          : (google_symbol,            yahoo_symbol,  région)
    "DOW":                ("INDEXDJX:.DJI",      "^DJI",       "USA"),
    "S&P500":             ("INDEXSP:.INX",       "^GSPC",      "USA"),
    "NASDAQ":             ("INDEXNASDAQ:.IXIC",  "^IXIC",      "USA"),
    "DAX":                ("INDEXDB:DAX",        "^GDAXI",     "Europe"),
    "FTSE 100":           ("INDEXFTSE:UKX",      "^FTSE",      "Europe"),
    "CAC 40":             ("INDEXEURO:PX1",      "^FCHI",      "Europe"),
    "IBEX 35":            ("INDEXBME:INDI",      "^IBEX",      "Europe"),
    "STOXX 50":           ("INDEXSTOXX:SX5E",    "^STOXX50E",  "Europe"),
    "Nikkei 225":         ("INDEXNIKKEI:NI225",  "^N225",      "Asie"),
    "Shanghai Composite": ("SHA:000001",         "000001.SS",  "Asie"),
    "Hang Seng":          ("INDEXHANGSENG:HSI",  "^HSI",       "Asie"),
    "Sensex (BSE 30)":    ("INDEXBOM:SENSEX",    "^BSESN",     "Asie"),
    "Kospi":              ("KRX:KOSPI",          "^KS11",      "Asie"),
    "VIX":                ("INDEXCBOE:VIX",      "^VIX",       "Fear Index"),
}

# Mapping ticker simple -> symbole Google Finance (bourse:ticker)
US_EXCHANGES = ["NYSEARCA", "NASDAQ", "NYSE", "BATS", "NYSEAMERICAN"]


# ---------------------------------------------------------------------------
# GOOGLE FINANCE (source principale)
# ---------------------------------------------------------------------------
def _google_quote(symbol: str, timeout: int = 6):
    """
    Scrape https://www.google.com/finance/quote/<symbol>
    symbol au format 'BOURSE:TICKER' ou 'INDEX...:...'
    Retourne float ou None.
    """
    url = f"https://www.google.com/finance/quote/{symbol}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None
        # Le prix est dans <div class="YMlKec fxKbKc">1 234,56</div>
        m = re.search(r'class="YMlKec fxKbKc">([^<]+)<', r.text)
        if not m:
            return None
        raw = m.group(1)
        raw = raw.replace("\u202f", "").replace("\xa0", "").replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
        return float(raw)
    except Exception:
        return None


def google_price(ticker: str):
    """
    Essaie Google Finance pour un ticker simple (ex: 'SPY', 'HACK').
    Teste plusieurs bourses US si aucune bourse n'est précisée.
    Retourne (prix, symbole_google) ou (None, None).
    """
    if ":" in ticker:  # déjà au format BOURSE:TICKER
        p = _google_quote(ticker)
        return (p, ticker) if p is not None else (None, None)
    for exch in US_EXCHANGES:
        sym = f"{exch}:{ticker}"
        p = _google_quote(sym)
        if p is not None:
            return p, sym
    return None, None


# ---------------------------------------------------------------------------
# YAHOO FINANCE (fallback)
# ---------------------------------------------------------------------------
def yahoo_price(ticker: str):
    """Fallback Yahoo Finance. Retourne float ou None."""
    if not YF_OK:
        return None
    try:
        t = yf.Ticker(ticker)
        # fast_info est le plus rapide et fiable
        p = getattr(t.fast_info, "last_price", None)
        if p:
            return float(p)
        hist = t.history(period="5d")["Close"].dropna()
        if len(hist):
            return float(hist.iloc[-1])
    except Exception:
        pass
    return None


def yahoo_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Historique de prix (Yahoo uniquement — Google ne fournit pas d'API historique)."""
    if not YF_OK:
        return pd.DataFrame()
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# API PUBLIQUE — Google d'abord, Yahoo si Google impossible
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_price(ticker: str, yahoo_symbol: str = None):
    """
    Retourne dict {ticker, price, source} .
    1) Google Finance
    2) Yahoo Finance si Google échoue
    """
    price, _ = google_price(ticker)
    if price is not None:
        return {"ticker": ticker, "price": price, "source": "Google Finance"}

    y_sym = yahoo_symbol or ticker.split(":")[-1]
    price = yahoo_price(y_sym)
    if price is not None:
        return {"ticker": ticker, "price": price, "source": "Yahoo Finance"}

    return {"ticker": ticker, "price": None, "source": "Indisponible"}


@st.cache_data(ttl=300, show_spinner=False)
def get_index_dashboard() -> pd.DataFrame:
    """
    Récupère tous les indices mondiaux (Google prioritaire, Yahoo fallback).
    Retourne un DataFrame: Indice | Région | Prix | Var 1J % | Source
    """
    rows = []
    for name, (g_sym, y_sym, region) in WORLD_INDICES.items():
        price, source, chg = None, "Indisponible", None

        p, _ = (google_price(g_sym) if ":" in g_sym else (None, None))
        if p is not None:
            price, source = p, "Google Finance"

        # Yahoo pour le prix (fallback) ET pour la variation 1 jour
        hist = yahoo_history(y_sym, period="5d")
        if not hist.empty and len(hist) >= 2:
            closes = hist["Close"].dropna()
            if len(closes) >= 2:
                chg = (closes.iloc[-1] / closes.iloc[-2] - 1) * 100
            if price is None:
                price, source = float(closes.iloc[-1]), "Yahoo Finance"

        rows.append({
            "Indice": name, "Région": region, "Prix": price,
            "Var 1J %": chg, "Source": source,
            "Yahoo": y_sym, "Google": g_sym,
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=900, show_spinner=False)
def get_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Historique pour graphiques (Yahoo)."""
    return yahoo_history(ticker, period=period)
