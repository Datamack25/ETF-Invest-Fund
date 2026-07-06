"""
data_fetcher.py — Récupération des prix (v2 : parallèle + timeouts courts)
===========================================================================
Stratégie : Google Finance (scraping) en PRIORITÉ,
puis Yahoo Finance (yfinance) en FALLBACK si Google échoue.

v2 : les 14 indices sont récupérés EN PARALLÈLE (ThreadPoolExecutor)
avec un timeout de 3s par requête — la page ne reste plus bloquée
quand Google Finance refuse les requêtes depuis Streamlit Cloud.
"""

import re
import time
import requests
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor

try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False

TIMEOUT = 3  # secondes — court pour ne jamais bloquer l'affichage

# ---------------------------------------------------------------------------
# DISJONCTEUR GOOGLE : après 3 échecs consécutifs, on RESTE SUR YAHOO
# pendant 10 minutes (plus aucune tentative Google = plus aucune attente).
# ---------------------------------------------------------------------------
GOOGLE_MAX_FAILS = 3
GOOGLE_COOLDOWN = 600  # secondes (10 min) avant de retenter Google
_GOOGLE_STATE = {"fails": 0, "disabled_until": 0.0}


def google_available() -> bool:
    """False si Google a échoué 3 fois de suite (on reste sur Yahoo)."""
    return time.time() >= _GOOGLE_STATE["disabled_until"]


def _register_google(success: bool):
    if success:
        _GOOGLE_STATE["fails"] = 0
    else:
        _GOOGLE_STATE["fails"] += 1
        if _GOOGLE_STATE["fails"] >= GOOGLE_MAX_FAILS:
            _GOOGLE_STATE["disabled_until"] = time.time() + GOOGLE_COOLDOWN

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
}

WORLD_INDICES = {
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

US_EXCHANGES = ["NYSEARCA", "NASDAQ", "NYSE", "BATS", "NYSEAMERICAN"]


# ---------------------------------------------------------------------------
# GOOGLE FINANCE (source principale)
# ---------------------------------------------------------------------------
def _google_quote(symbol: str, timeout: int = TIMEOUT):
    url = f"https://www.google.com/finance/quote/{symbol}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None
        m = re.search(r'class="YMlKec fxKbKc">([^<]+)<', r.text)
        if not m:
            return None
        raw = (m.group(1).replace("\u202f", "").replace("\xa0", "")
               .replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip())
        return float(raw)
    except Exception:
        return None


def google_price(ticker: str):
    if not google_available():          # Google en panne -> on reste sur Yahoo
        return None, None
    if ":" in ticker:
        p = _google_quote(ticker)
        _register_google(p is not None)
        return (p, ticker) if p is not None else (None, None)
    # Ticker sans bourse : on teste les bourses US en parallèle
    syms = [f"{e}:{ticker}" for e in US_EXCHANGES]
    with ThreadPoolExecutor(max_workers=len(syms)) as ex:
        results = list(ex.map(_google_quote, syms))
    for sym, p in zip(syms, results):
        if p is not None:
            _register_google(True)
            return p, sym
    _register_google(False)
    return None, None


# ---------------------------------------------------------------------------
# YAHOO FINANCE (fallback)
# ---------------------------------------------------------------------------
def yahoo_price(ticker: str):
    if not YF_OK:
        return None
    try:
        t = yf.Ticker(ticker)
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
    if not YF_OK:
        return pd.DataFrame()
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# API PUBLIQUE
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_price(ticker: str, yahoo_symbol: str = None):
    """Google d'abord, Yahoo si Google impossible."""
    price, _ = google_price(ticker)
    if price is not None:
        return {"ticker": ticker, "price": price, "source": "Google Finance"}
    y_sym = yahoo_symbol or ticker.split(":")[-1]
    price = yahoo_price(y_sym)
    if price is not None:
        return {"ticker": ticker, "price": price, "source": "Yahoo Finance"}
    return {"ticker": ticker, "price": None, "source": "Indisponible"}


def _fetch_one_index(item):
    """Récupère UN indice (appelé en parallèle). Ne lève jamais d'exception."""
    name, (g_sym, y_sym, region) = item
    price, source, chg = None, "Indisponible", None
    try:
        if google_available():          # sinon on reste sur Yahoo directement
            p = _google_quote(g_sym)
            _register_google(p is not None)
            if p is not None:
                price, source = p, "Google Finance"
        hist = yahoo_history(y_sym, period="5d")
        if not hist.empty:
            closes = hist["Close"].dropna()
            if len(closes) >= 2:
                chg = (closes.iloc[-1] / closes.iloc[-2] - 1) * 100
            if price is None and len(closes):
                price, source = float(closes.iloc[-1]), "Yahoo Finance"
    except Exception:
        pass
    return {"Indice": name, "Région": region, "Prix": price,
            "Var 1J %": chg, "Source": source, "Yahoo": y_sym, "Google": g_sym}


@st.cache_data(ttl=300, show_spinner=False)
def get_index_dashboard() -> pd.DataFrame:
    """Tous les indices EN PARALLÈLE — ~3-6 s au lieu de 1-2 min."""
    with ThreadPoolExecutor(max_workers=14) as ex:
        rows = list(ex.map(_fetch_one_index, WORLD_INDICES.items()))
    order = {n: i for i, n in enumerate(WORLD_INDICES)}
    return pd.DataFrame(rows).sort_values("Indice", key=lambda s: s.map(order)).reset_index(drop=True)


@st.cache_data(ttl=900, show_spinner=False)
def get_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    return yahoo_history(ticker, period=period)
