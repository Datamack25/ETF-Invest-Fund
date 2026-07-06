"""
storage.py — Persistance en CSV
================================
4 fichiers CSV dans ./data/ (créés automatiquement) :

  assets.csv              -> univers des actifs (ticker, nom, catégorie, secteur, symboles)
  portfolios.csv          -> portefeuilles créés (nom, capital, allocations cibles)
  transactions.csv        -> chaque achat/vente enregistré
  performance_history.csv -> snapshots de valorisation (pour suivre la perf dans le temps)
"""

import os
from datetime import datetime
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

F_ASSETS = os.path.join(DATA_DIR, "assets.csv")
F_PORTFOLIOS = os.path.join(DATA_DIR, "portfolios.csv")
F_TRANSACTIONS = os.path.join(DATA_DIR, "transactions.csv")
F_PERF = os.path.join(DATA_DIR, "performance_history.csv")

# ---------------------------------------------------------------------------
# UNIVERS D'ACTIFS PAR DÉFAUT — repris de ta feuille Gestion_Portfeuille
# catégorie: ETF / Action / Bond
# ---------------------------------------------------------------------------
DEFAULT_ASSETS = [
    # ETFs thématiques
    ("NERD",  "Roundhill Video Games",        "ETF",  "Gaming",             "NYSEARCA:NERD",  "NERD"),
    ("ESPO",  "VanEck Video Gaming eSports",  "ETF",  "Gaming",             "NASDAQ:ESPO",    "ESPO"),
    ("XSD",   "SPDR S&P Semiconductor",       "ETF",  "Semiconductors",     "NYSEARCA:XSD",   "XSD"),
    ("SOXX",  "iShares Semiconductor",        "ETF",  "Semiconductors",     "NASDAQ:SOXX",    "SOXX"),
    ("SMH",   "VanEck Semiconductor",         "ETF",  "Semiconductors",     "NASDAQ:SMH",     "SMH"),
    ("SKYY",  "First Trust Cloud Computing",  "ETF",  "Cloud_Data storage", "NASDAQ:SKYY",    "SKYY"),
    ("CLOU",  "Global X Cloud Computing",     "ETF",  "Cloud_Data storage", "NASDAQ:CLOU",    "CLOU"),
    ("WCLD",  "WisdomTree Cloud Computing",   "ETF",  "Cloud_Data storage", "NASDAQ:WCLD",    "WCLD"),
    ("HACK",  "Amplify Cybersecurity",        "ETF",  "Cybersecurity",      "NYSEARCA:HACK",  "HACK"),
    ("CIBR",  "First Trust NASDAQ Cyber",     "ETF",  "Cybersecurity",      "NASDAQ:CIBR",    "CIBR"),
    ("BUG",   "Global X Cybersecurity",       "ETF",  "Cybersecurity",      "NASDAQ:BUG",     "BUG"),
    ("IPAY",  "Amplify Digital Payments",     "ETF",  "Fintechs",           "NYSEARCA:IPAY",  "IPAY"),
    ("ARKF",  "ARK Fintech Innovation",       "ETF",  "Fintechs",           "NYSEARCA:ARKF",  "ARKF"),
    ("FINX",  "Global X FinTech",             "ETF",  "Fintechs",           "NASDAQ:FINX",    "FINX"),
    ("ROBT",  "First Trust AI & Robotics",    "ETF",  "IA & Robotics",      "NASDAQ:ROBT",    "ROBT"),
    ("BOTZ",  "Global X Robotics & AI",       "ETF",  "IA & Robotics",      "NASDAQ:BOTZ",    "BOTZ"),
    ("QQQ",   "Invesco QQQ (Nasdaq 100)",     "ETF",  "Techs",              "NASDAQ:QQQ",     "QQQ"),
    ("SPY",   "SPDR S&P 500",                 "ETF",  "Large Cap",          "NYSEARCA:SPY",   "SPY"),
    ("EZU",   "iShares MSCI Eurozone",        "ETF",  "Europe",             "BATS:EZU",       "EZU"),
    ("IEMG",  "iShares Core MSCI EM",         "ETF",  "Émergents",          "NYSEARCA:IEMG",  "IEMG"),
    ("ITA",   "iShares US Aerospace&Defense", "ETF",  "Defense & aerospace","BATS:ITA",       "ITA"),
    ("PPA",   "Invesco Aerospace & Defense",  "ETF",  "Defense & aerospace","NYSEARCA:PPA",   "PPA"),
    ("XAR",   "SPDR S&P Aerospace & Defense", "ETF",  "Defense & aerospace","NYSEARCA:XAR",   "XAR"),
    # Actions
    ("XYZ",   "Block (Square)",               "Action", "Fintechs",         "NYSE:XYZ",       "XYZ"),
    ("PYPL",  "PayPal",                       "Action", "Fintechs",         "NASDAQ:PYPL",    "PYPL"),
    ("CRWD",  "CrowdStrike",                  "Action", "Cybersecurity",    "NASDAQ:CRWD",    "CRWD"),
    ("FTNT",  "Fortinet",                     "Action", "Cybersecurity",    "NASDAQ:FTNT",    "FTNT"),
    ("PANW",  "Palo Alto Networks",           "Action", "Cybersecurity",    "NASDAQ:PANW",    "PANW"),
    ("CHKP",  "Check Point Software",         "Action", "Cybersecurity",    "NASDAQ:CHKP",    "CHKP"),
    ("DLR",   "Digital Realty",               "Action", "Cloud_Data storage","NYSE:DLR",      "DLR"),
    ("NTAP",  "NetApp",                       "Action", "Cloud_Data storage","NASDAQ:NTAP",   "NTAP"),
    ("GOOGL", "Alphabet",                     "Action", "Techs",            "NASDAQ:GOOGL",   "GOOGL"),
    ("AMZN",  "Amazon",                       "Action", "Techs",            "NASDAQ:AMZN",    "AMZN"),
    ("AAPL",  "Apple",                        "Action", "Techs",            "NASDAQ:AAPL",    "AAPL"),
    ("CSCO",  "Cisco",                        "Action", "Techs",            "NASDAQ:CSCO",    "CSCO"),
    ("PLTR",  "Palantir",                     "Action", "Techs",            "NASDAQ:PLTR",    "PLTR"),
    ("TSLA",  "Tesla",                        "Action", "Techs",            "NASDAQ:TSLA",    "TSLA"),
    ("NVDA",  "NVIDIA",                       "Action", "Semiconductors",   "NASDAQ:NVDA",    "NVDA"),
    ("AVGO",  "Broadcom",                     "Action", "Semiconductors",   "NASDAQ:AVGO",    "AVGO"),
    ("TTWO",  "Take-Two Interactive",         "Action", "Gaming",           "NASDAQ:TTWO",    "TTWO"),
    ("SNOW",  "Snowflake",                    "Action", "IA & Robotics",    "NYSE:SNOW",      "SNOW"),
    # Bonds (ETF obligataires)
    ("AGG",   "iShares Core US Aggregate",    "Bond", "Obligations",        "NYSEARCA:AGG",   "AGG"),
    ("BND",   "Vanguard Total Bond Market",   "Bond", "Obligations",        "NASDAQ:BND",     "BND"),
    ("IEF",   "iShares 7-10Y Treasury",       "Bond", "Obligations",        "NASDAQ:IEF",     "IEF"),
    ("LQD",   "iShares IG Corporate Bond",    "Bond", "Obligations",        "NYSEARCA:LQD",   "LQD"),
    ("TLT",   "iShares 20+Y Treasury",        "Bond", "Obligations",        "NASDAQ:TLT",     "TLT"),
]

ASSET_COLS = ["ticker", "nom", "categorie", "secteur", "google_symbol", "yahoo_symbol"]
PF_COLS = ["portfolio", "capital", "devise", "alloc_actions", "alloc_etf", "alloc_bonds", "date_creation"]
TX_COLS = ["date", "portfolio", "ticker", "categorie", "secteur", "sens", "quantite", "prix", "montant", "source_prix"]
PERF_COLS = ["date", "portfolio", "valeur_marche", "investi", "gain_perte", "perf_pct"]


def _load(path: str, cols: list) -> pd.DataFrame:
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            for c in cols:
                if c not in df.columns:
                    df[c] = None
            return df[cols]
        except Exception:
            pass
    return pd.DataFrame(columns=cols)


def _save(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)


# ------------------------- ASSETS -------------------------
def load_assets() -> pd.DataFrame:
    df = _load(F_ASSETS, ASSET_COLS)
    if df.empty:
        df = pd.DataFrame(DEFAULT_ASSETS, columns=ASSET_COLS)
        _save(df, F_ASSETS)
    return df


def add_asset(ticker, nom, categorie, secteur, google_symbol, yahoo_symbol):
    df = load_assets()
    if ticker.upper() in df["ticker"].str.upper().values:
        return False, "Ce ticker existe déjà dans l'univers."
    row = pd.DataFrame([[ticker.upper(), nom, categorie, secteur, google_symbol, yahoo_symbol]], columns=ASSET_COLS)
    _save(pd.concat([df, row], ignore_index=True), F_ASSETS)
    return True, f"{ticker.upper()} ajouté à l'univers d'actifs."


def delete_asset(ticker):
    df = load_assets()
    _save(df[df["ticker"] != ticker], F_ASSETS)


# ------------------------- PORTFOLIOS -------------------------
def load_portfolios() -> pd.DataFrame:
    return _load(F_PORTFOLIOS, PF_COLS)


def create_portfolio(nom, capital, devise, a_act, a_etf, a_bond):
    df = load_portfolios()
    if nom in df["portfolio"].values:
        return False, "Un portefeuille porte déjà ce nom."
    row = pd.DataFrame([[nom, capital, devise, a_act, a_etf, a_bond,
                         datetime.now().strftime("%Y-%m-%d")]], columns=PF_COLS)
    _save(pd.concat([df, row], ignore_index=True), F_PORTFOLIOS)
    return True, f"Portefeuille « {nom} » créé."


def delete_portfolio(nom):
    _save(load_portfolios().query("portfolio != @nom"), F_PORTFOLIOS)
    tx = load_transactions()
    _save(tx[tx["portfolio"] != nom], F_TRANSACTIONS)


# ------------------------- TRANSACTIONS -------------------------
def load_transactions() -> pd.DataFrame:
    df = _load(F_TRANSACTIONS, TX_COLS)
    if not df.empty:
        df["quantite"] = pd.to_numeric(df["quantite"], errors="coerce")
        df["prix"] = pd.to_numeric(df["prix"], errors="coerce")
        df["montant"] = pd.to_numeric(df["montant"], errors="coerce")
    return df


def add_transaction(portfolio, ticker, categorie, secteur, sens, quantite, prix, source_prix):
    df = load_transactions()
    montant = round(quantite * prix, 2)
    row = pd.DataFrame([[datetime.now().strftime("%Y-%m-%d %H:%M"), portfolio, ticker,
                         categorie, secteur, sens, quantite, prix, montant, source_prix]], columns=TX_COLS)
    _save(pd.concat([df, row], ignore_index=True), F_TRANSACTIONS)


def holdings(portfolio: str) -> pd.DataFrame:
    """Positions nettes d'un portefeuille (achats - ventes) + prix moyen d'achat."""
    tx = load_transactions()
    tx = tx[tx["portfolio"] == portfolio]
    if tx.empty:
        return pd.DataFrame(columns=["ticker", "categorie", "secteur", "quantite", "investi", "pru"])
    tx = tx.copy()
    tx["q_signed"] = tx.apply(lambda r: r["quantite"] if r["sens"] == "Achat" else -r["quantite"], axis=1)
    tx["m_signed"] = tx.apply(lambda r: r["montant"] if r["sens"] == "Achat" else -r["montant"], axis=1)
    g = tx.groupby(["ticker", "categorie", "secteur"], as_index=False).agg(
        quantite=("q_signed", "sum"), investi=("m_signed", "sum"))
    g = g[g["quantite"] > 0]
    g["pru"] = g["investi"] / g["quantite"]
    return g


# ------------------------- PERFORMANCE HISTORY -------------------------
def load_perf() -> pd.DataFrame:
    return _load(F_PERF, PERF_COLS)


def snapshot_perf(portfolio, valeur_marche, investi):
    df = load_perf()
    gain = valeur_marche - investi
    pct = (gain / investi * 100) if investi else 0
    row = pd.DataFrame([[datetime.now().strftime("%Y-%m-%d %H:%M"), portfolio,
                         round(valeur_marche, 2), round(investi, 2),
                         round(gain, 2), round(pct, 2)]], columns=PERF_COLS)
    _save(pd.concat([df, row], ignore_index=True), F_PERF)
