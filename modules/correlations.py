"""Corrélations live entre actifs et indices majeurs.
Matrice de corrélation des rendements + corrélation glissante par paire.
Données yfinance (délai ~15 min), rafraîchies toutes les 15 minutes."""
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st

# 14 actifs / indices suivis
CORR_ASSETS = {
    "Nasdaq 100": "NQ=F",
    "S&P 500": "ES=F",
    "Dow Jones": "YM=F",
    "CAC 40": "^FCHI",
    "DAX": "^GDAXI",
    "MSCI World": "URTH",        # ETF iShares MSCI World
    "Or": "GC=F",
    "Argent": "SI=F",
    "Pétrole WTI": "CL=F",
    "VIX": "^VIX",
    "US 10Y (taux)": "^TNX",
    "Dollar Index": "DX-Y.NYB",
    "EUR/USD": "EURUSD=X",
    "Bitcoin": "BTC-USD",
}

PERIODS = {
    "1 mois": ("1mo", "1d"),
    "3 mois": ("3mo", "1d"),
    "6 mois": ("6mo", "1d"),
    "1 an": ("1y", "1d"),
    "Intraday 5 jours (1h)": ("5d", "1h"),
}


@st.cache_data(ttl=900, show_spinner="Chargement des 14 actifs…")
def load_closes(period_key: str) -> pd.DataFrame:
    """Télécharge les clôtures de tous les actifs en un seul appel batch."""
    period, interval = PERIODS[period_key]
    tickers = list(CORR_ASSETS.values())
    try:
        raw = yf.download(tickers, period=period, interval=interval,
                          progress=False, auto_adjust=True)
        closes = raw["Close"] if "Close" in raw else raw
        # renomme ticker -> nom lisible
        inv = {v: k for k, v in CORR_ASSETS.items()}
        closes = closes.rename(columns=inv)
        # garde les colonnes avec assez de données, forward-fill les trous
        # (marchés à horaires différents : CAC ferme avant NY, crypto 24/7)
        closes = closes.dropna(axis=1, thresh=int(len(closes) * 0.5)).ffill()
        return closes.dropna(how="all")
    except Exception:
        return pd.DataFrame()


def correlation_matrix(closes: pd.DataFrame) -> pd.DataFrame:
    """Corrélation de Pearson sur les RENDEMENTS (pas les prix bruts,
    qui donneraient des corrélations trompeuses à cause des tendances)."""
    if closes.empty or len(closes) < 10:
        return pd.DataFrame()
    returns = closes.pct_change().dropna(how="all")
    return returns.corr(min_periods=8).round(2)


def rolling_correlation(closes: pd.DataFrame, asset_a: str, asset_b: str,
                        window: int = 20) -> pd.Series:
    """Corrélation glissante entre deux actifs (fenêtre en barres)."""
    if asset_a not in closes or asset_b not in closes:
        return pd.Series(dtype=float)
    ra = closes[asset_a].pct_change()
    rb = closes[asset_b].pct_change()
    return ra.rolling(window).corr(rb).dropna()


def key_pairs_summary(corr: pd.DataFrame) -> list:
    """Lecture rapide des paires critiques pour un trader NQ."""
    pairs = [
        ("Nasdaq 100", "VIX", "NQ/VIX : normalement fortement négative. Si elle remonte vers 0, méfiance — le marché ne price plus la peur normalement."),
        ("Nasdaq 100", "US 10Y (taux)", "NQ/Taux 10 ans : négative en régime 'inflation' (taux montent = tech baisse), positive en régime 'croissance'."),
        ("Nasdaq 100", "Or", "NQ/Or : proche de 0 en temps normal. Fortement négative = fuite vers la qualité (risk-off)."),
        ("Nasdaq 100", "Bitcoin", "NQ/BTC : élevée = le crypto trade comme un actif risqué tech ; un décrochage BTC peut précéder le NQ."),
        ("Or", "Dollar Index", "Or/DXY : structurellement négative. Si positive, signal de stress inhabituel."),
        ("S&P 500", "Pétrole WTI", "ES/WTI : positive = croissance ; négative = choc d'offre pétrolier (mauvais pour les indices)."),
        ("Nasdaq 100", "CAC 40", "NQ/CAC : mesure la synchronisation US/Europe. Faible = divergence régionale exploitable."),
    ]
    out = []
    for a, b, note in pairs:
        if a in corr.index and b in corr.columns:
            v = corr.loc[a, b]
            if pd.notna(v):
                out.append({"paire": f"{a} ↔ {b}", "corr": float(v), "note": note})
    return out


def regime_signal(corr: pd.DataFrame) -> dict:
    """Détermine le régime risk-on / risk-off à partir des corrélations."""
    score = 0
    checks = 0
    def get(a, b):
        try:
            return corr.loc[a, b]
        except Exception:
            return np.nan

    nq_vix = get("Nasdaq 100", "VIX")
    if pd.notna(nq_vix):
        checks += 1
        score += 1 if nq_vix < -0.5 else (-1 if nq_vix > -0.2 else 0)
    nq_gold = get("Nasdaq 100", "Or")
    if pd.notna(nq_gold):
        checks += 1
        score += -1 if nq_gold < -0.3 else 0
    gold_dxy = get("Or", "Dollar Index")
    if pd.notna(gold_dxy):
        checks += 1
        score += -1 if gold_dxy > 0.2 else 0

    if checks == 0:
        return {"regime": "Indéterminé", "desc": "Données insuffisantes."}
    if score >= 1:
        return {"regime": "RISK-ON (normal)",
                "desc": "Les corrélations sont dans leurs régimes habituels : le marché fonctionne normalement, "
                        "les setups techniques ICT sont fiables."}
    if score <= -1:
        return {"regime": "RISK-OFF / Stress",
                "desc": "Corrélations anormales (fuite vers l'or, VIX décorrélé, ou or+dollar ensemble) : "
                        "régime de stress où les niveaux techniques sont moins respectés. Réduire la taille."}
    return {"regime": "Transition",
            "desc": "Corrélations mitigées : le marché hésite entre régimes. Privilégier les timeframes courts."}
