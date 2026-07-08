# -*- coding: utf-8 -*-
"""
ETF Core Invest — Plateforme de gestion de portefeuille (Actions / ETF / Bonds)
Persistance CSV via storage.py · Prix live yfinance · Corrélations 14 actifs

⚠️ Outil de suivi et d'aide à la décision. Ceci n'est pas un conseil financier.
"""
import datetime as dt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

import storage as db

st.set_page_config(page_title="ETF Core Invest", page_icon="💼", layout="wide")

st.markdown("""
<style>
    .main .block-container {padding-top: 1.2rem;}
    div[data-testid="stMetric"] {background: #161b22; border: 1px solid #2a313c;
        border-radius: 8px; padding: 10px 14px;}
</style>
""", unsafe_allow_html=True)

CAT_COLORS = {"Action": "#42a5f5", "ETF": "#26a69a", "Bond": "#ffca28"}

# ═══════════════════════ PRIX LIVE (yfinance) ═══════════════════════
@st.cache_data(ttl=600, show_spinner=False)
def fetch_prices(tickers: tuple) -> dict:
    """Derniers prix pour une liste de tickers Yahoo (batch)."""
    if not tickers:
        return {}
    try:
        raw = yf.download(list(tickers), period="5d", interval="1d",
                          progress=False, auto_adjust=True)
        closes = raw["Close"] if "Close" in raw else raw
        if isinstance(closes, pd.Series):  # un seul ticker
            return {tickers[0]: float(closes.dropna().iloc[-1])}
        out = {}
        for t in tickers:
            if t in closes.columns:
                s = closes[t].dropna()
                if len(s):
                    out[t] = float(s.iloc[-1])
        return out
    except Exception:
        return {}


def valorise(holds: pd.DataFrame, assets: pd.DataFrame):
    """Ajoute prix live, valeur de marché et P&L aux positions."""
    if holds.empty:
        return holds, 0.0, 0.0
    ymap = dict(zip(assets["ticker"], assets["yahoo_symbol"]))
    holds = holds.copy()
    holds["yahoo"] = holds["ticker"].map(ymap).fillna(holds["ticker"])
    prices = fetch_prices(tuple(holds["yahoo"].unique()))
    holds["prix_actuel"] = holds["yahoo"].map(prices)
    holds["valeur"] = (holds["prix_actuel"] * holds["quantite"]).round(2)
    holds["pnl"] = (holds["valeur"] - holds["investi"]).round(2)
    holds["pnl_pct"] = ((holds["valeur"] / holds["investi"] - 1) * 100).round(2)
    total_val = float(holds["valeur"].sum(skipna=True))
    total_inv = float(holds["investi"].sum())
    return holds, total_val, total_inv


# ═══════════════════════ SIDEBAR ═══════════════════════
st.sidebar.title("💼 ETF Core Invest")
st.sidebar.caption("Core/Satellite · Actions / ETF / Bonds — *pas un conseil financier*")

page = st.sidebar.radio("Navigation", [
    "📊 Tableau de bord",
    "💼 Portefeuilles",
    "🛒 Transactions",
    "🌐 Univers d'actifs",
    "📈 Historique de performance",
    "🔗 Corrélations live",
])

if st.sidebar.button("🔄 Rafraîchir les prix"):
    st.cache_data.clear()
    st.rerun()

pf_df = db.load_portfolios()
assets = db.load_assets()

# ═══════════════════════ APERÇU MARCHÉS (indices) ═══════════════════════
MARKET_INDICES = {
    "S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "Dow Jones": "^DJI",
    "CAC 40": "^FCHI", "DAX": "^GDAXI", "MSCI World": "URTH",
    "Or": "GC=F", "Pétrole WTI": "CL=F", "VIX": "^VIX",
    "EUR/USD": "EURUSD=X", "Bitcoin": "BTC-USD", "US 10Y": "^TNX",
}


@st.cache_data(ttl=600, show_spinner=False)
def load_market_history(period: str) -> pd.DataFrame:
    """Historique de clôture des indices. IMPORTANT : pas de ffill ici —
    chaque actif garde ses propres dates de cotation (BTC cote le week-end,
    pas le CAC), sinon les variations quotidiennes sortent à 0.00%."""
    try:
        raw = yf.download(list(MARKET_INDICES.values()), period=period, interval="1d",
                          progress=False, auto_adjust=True)
        closes = raw["Close"] if "Close" in raw else raw
        if isinstance(closes, pd.Series):
            closes = closes.to_frame()
        inv = {v: k for k, v in MARKET_INDICES.items()}
        closes = closes.rename(columns=inv)
        return closes.dropna(how="all")
    except Exception:
        return pd.DataFrame()


def render_market_overview():
    """Tuiles indices + graphique d'évolution comparée. Toujours affiché."""
    st.subheader("🌍 Marchés du jour")
    hist = load_market_history("6mo")
    if hist.empty or len(hist) < 2:
        st.warning("Données de marché momentanément indisponibles (yfinance). "
                   "Clique « Rafraîchir les prix » dans quelques minutes.")
        return

    # Tuiles : dernier prix + variation quotidienne (sur les VRAIES cotations
    # de chaque actif : dropna par colonne, pas de valeurs recopiées)
    names = [n for n in MARKET_INDICES if n in hist.columns]
    for row_start in range(0, len(names), 6):
        cols = st.columns(6)
        for col, name in zip(cols, names[row_start:row_start + 6]):
            s = hist[name].dropna()
            s = s[~s.index.duplicated(keep="last")]
            if len(s) < 2:
                col.metric(name, "—")
                continue
            last, prev = float(s.iloc[-1]), float(s.iloc[-2])
            chg = (last / prev - 1) * 100 if prev else 0
            fmt = f"{last:,.2f}" if last < 10000 else f"{last:,.0f}"
            col.metric(name, fmt, f"{chg:+.2f}%")

    # Graphique d'évolution comparée (base 100)
    c1, c2 = st.columns([1, 2])
    with c1:
        per_key = st.selectbox("Période du graphique",
                               ["5 jours", "1 mois", "3 mois", "6 mois"], index=1)
        sel = st.multiselect("Indices à afficher", names,
                             default=[n for n in ["S&P 500", "Nasdaq 100", "CAC 40",
                                                  "MSCI World", "Or"] if n in names])
    n_days = {"5 jours": 5, "1 mois": 22, "3 mois": 66, "6 mois": 126}[per_key]
    seg = hist.ffill().tail(n_days)  # ffill ici seulement : lignes continues sur le graphe
    with c2:
        if sel and len(seg) > 1:
            fig = go.Figure()
            for name in sel:
                s = seg[name].dropna()
                if len(s) > 1:
                    base = s / s.iloc[0] * 100
                    fig.add_trace(go.Scatter(x=base.index, y=base.values,
                                             name=name, mode="lines"))
            fig.add_hline(y=100, line_dash="dot", line_color="#777")
            fig.update_layout(title=f"Évolution comparée (base 100) — {per_key}",
                              template="plotly_dark", height=360,
                              margin=dict(l=10, r=10, t=40, b=10),
                              legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(fig, use_container_width=True)
    st.caption("Prix yfinance (délai ~15 min). Base 100 = tous les indices ramenés à 100 "
               "au début de la période pour comparer leurs performances relatives.")


# ═══════════════════════ PAGE : DASHBOARD ═══════════════════════
if page == "📊 Tableau de bord":
    st.title("📊 Tableau de bord")

    # Les marchés s'affichent TOUJOURS, portefeuille ou pas
    render_market_overview()
    st.divider()

    st.subheader("💼 Mon portefeuille")
    if pf_df.empty:
        st.info("Aucun portefeuille pour l'instant. Crée-en un dans l'onglet 💼 Portefeuilles "
                "pour voir apparaître ici tes positions, ton P&L et ton allocation vs cible.")
        st.stop()

    pf_name = st.selectbox("Portefeuille", pf_df["portfolio"].tolist())
    pf = pf_df[pf_df["portfolio"] == pf_name].iloc[0]
    holds, total_val, total_inv = valorise(db.holdings(pf_name), assets)

    capital = float(pf["capital"])
    cash = capital - total_inv
    pnl = total_val - total_inv
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Capital", f"{capital:,.0f} {pf['devise']}")
    c2.metric("Investi", f"{total_inv:,.0f}")
    c3.metric("Valeur de marché", f"{total_val:,.0f}")
    c4.metric("P&L latent", f"{pnl:+,.0f}", f"{(pnl / total_inv * 100) if total_inv else 0:+.2f}%")
    c5.metric("Cash disponible", f"{cash:,.0f}")

    if holds.empty:
        st.caption("Aucune position. Enregistre des achats dans 🛒 Transactions.")
        st.stop()

    # Allocation réelle vs cible
    st.subheader("Allocation réelle vs cible")
    alloc_real = holds.groupby("categorie")["valeur"].sum()
    targets = {"Action": float(pf["alloc_actions"]), "ETF": float(pf["alloc_etf"]),
               "Bond": float(pf["alloc_bonds"])}
    cols = st.columns(3)
    for col, cat in zip(cols, ["Action", "ETF", "Bond"]):
        real = alloc_real.get(cat, 0) / total_val * 100 if total_val else 0
        tgt = targets[cat]
        delta = real - tgt
        col.metric(f"{cat}s", f"{real:.1f}%", f"{delta:+.1f}% vs cible {tgt:.0f}%",
                   delta_color="inverse" if abs(delta) > 5 else "off")
    ecarts = [cat for cat in targets if abs((alloc_real.get(cat, 0) / total_val * 100 if total_val else 0) - targets[cat]) > 5]
    if ecarts:
        st.warning(f"⚖️ Rééquilibrage à envisager sur : {', '.join(ecarts)} (écart > 5 pts vs cible).")

    col_l, col_r = st.columns(2)
    with col_l:
        fig = go.Figure(go.Pie(labels=alloc_real.index, values=alloc_real.values, hole=0.45,
                               marker=dict(colors=[CAT_COLORS.get(c, "#888") for c in alloc_real.index])))
        fig.update_layout(title="Par catégorie", template="plotly_dark", height=330,
                          margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with col_r:
        sect = holds.groupby("secteur")["valeur"].sum().sort_values()
        fig2 = go.Figure(go.Bar(x=sect.values, y=sect.index, orientation="h",
                                marker_color="#26a69a"))
        fig2.update_layout(title="Par secteur", template="plotly_dark", height=330,
                           margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Positions")
    show = holds[["ticker", "categorie", "secteur", "quantite", "pru",
                  "prix_actuel", "investi", "valeur", "pnl", "pnl_pct"]].copy()
    show = show.rename(columns={"pru": "PRU", "prix_actuel": "Prix actuel",
                                "pnl": "P&L", "pnl_pct": "P&L %"})
    st.dataframe(show.style.map(
        lambda v: "color:#26a69a" if isinstance(v, (int, float)) and v > 0 else
                  ("color:#ef5350" if isinstance(v, (int, float)) and v < 0 else ""),
        subset=["P&L", "P&L %"]), use_container_width=True, height=340)

    if st.button("📸 Enregistrer un snapshot de performance"):
        db.snapshot_perf(pf_name, total_val, total_inv)
        st.success("Snapshot enregistré dans performance_history.csv ✅")

# ═══════════════════════ PAGE : PORTEFEUILLES ═══════════════════════
elif page == "💼 Portefeuilles":
    st.title("💼 Portefeuilles")
    with st.expander("➕ Créer un portefeuille", expanded=pf_df.empty):
        c1, c2, c3 = st.columns(3)
        nom = c1.text_input("Nom du portefeuille")
        capital = c2.number_input("Capital initial", 100.0, 10_000_000.0, 10_000.0, step=500.0)
        devise = c3.selectbox("Devise", ["EUR", "USD"])
        st.caption("Allocation cible (%) — modèle Core/Satellite. Par défaut : 15/65/20.")
        a1, a2, a3 = st.columns(3)
        aa = a1.number_input("Actions %", 0, 100, 15)
        ae = a2.number_input("ETF %", 0, 100, 65)
        ab = a3.number_input("Bonds %", 0, 100, 20)
        if st.button("Créer", type="primary"):
            if not nom.strip():
                st.error("Donne un nom au portefeuille.")
            elif aa + ae + ab != 100:
                st.error(f"Les allocations doivent totaliser 100% (actuellement {aa + ae + ab}%).")
            else:
                ok, msg = db.create_portfolio(nom.strip(), capital, devise, aa, ae, ab)
                st.success(msg) if ok else st.error(msg)
                if ok:
                    st.rerun()

    if not pf_df.empty:
        st.subheader("Portefeuilles existants")
        st.dataframe(pf_df, use_container_width=True)
        to_del = st.selectbox("Supprimer un portefeuille", ["—"] + pf_df["portfolio"].tolist())
        if to_del != "—" and st.button(f"🗑️ Supprimer « {to_del} » et ses transactions"):
            db.delete_portfolio(to_del)
            st.success("Supprimé.")
            st.rerun()

# ═══════════════════════ PAGE : TRANSACTIONS ═══════════════════════
elif page == "🛒 Transactions":
    st.title("🛒 Transactions")
    if pf_df.empty:
        st.info("Crée d'abord un portefeuille.")
        st.stop()

    c1, c2, c3 = st.columns(3)
    pf_name = c1.selectbox("Portefeuille", pf_df["portfolio"].tolist())
    ticker = c2.selectbox("Actif", assets["ticker"].tolist())
    sens = c3.selectbox("Sens", ["Achat", "Vente"])
    arow = assets[assets["ticker"] == ticker].iloc[0]
    st.caption(f"{arow['nom']} — {arow['categorie']} / {arow['secteur']}")

    c4, c5, c6 = st.columns(3)
    qty = c4.number_input("Quantité", 0.0001, 1_000_000.0, 1.0, step=1.0, format="%.4f")
    live = fetch_prices((arow["yahoo_symbol"],)).get(arow["yahoo_symbol"])
    use_live = c5.checkbox(f"Prix live ({live:,.2f})" if live else "Prix live indisponible",
                           value=bool(live), disabled=not live)
    prix = float(live) if (use_live and live) else c6.number_input("Prix manuel", 0.01, 1_000_000.0, 100.0)
    st.metric("Montant", f"{qty * prix:,.2f}")

    if st.button("Enregistrer la transaction", type="primary"):
        db.add_transaction(pf_name, ticker, arow["categorie"], arow["secteur"],
                           sens, qty, round(prix, 4),
                           "yahoo_live" if (use_live and live) else "manuel")
        st.success(f"{sens} de {qty:g} {ticker} @ {prix:,.2f} enregistré ✅")
        st.rerun()

    tx = db.load_transactions()
    tx_pf = tx[tx["portfolio"] == pf_name]
    if not tx_pf.empty:
        st.subheader(f"Historique — {pf_name}")
        st.dataframe(tx_pf.iloc[::-1], use_container_width=True, height=320)
        st.download_button("⬇️ Exporter (CSV)", tx_pf.to_csv(index=False),
                           f"transactions_{pf_name}.csv", "text/csv")

# ═══════════════════════ PAGE : UNIVERS ═══════════════════════
elif page == "🌐 Univers d'actifs":
    st.title("🌐 Univers d'actifs")
    st.caption(f"{len(assets)} actifs — {int((assets['categorie']=='ETF').sum())} ETF, "
               f"{int((assets['categorie']=='Action').sum())} actions, "
               f"{int((assets['categorie']=='Bond').sum())} bonds.")
    filt = st.multiselect("Filtrer par catégorie", ["ETF", "Action", "Bond"],
                          default=["ETF", "Action", "Bond"])
    st.dataframe(assets[assets["categorie"].isin(filt)], use_container_width=True, height=380)

    with st.expander("➕ Ajouter un actif"):
        c1, c2, c3 = st.columns(3)
        t = c1.text_input("Ticker (ex: MSFT)")
        n = c2.text_input("Nom")
        cat = c3.selectbox("Catégorie", ["Action", "ETF", "Bond"])
        c4, c5, c6 = st.columns(3)
        sec = c4.text_input("Secteur", "Techs")
        gsym = c5.text_input("Symbole Google (ex: NASDAQ:MSFT)")
        ysym = c6.text_input("Symbole Yahoo (ex: MSFT)")
        if st.button("Ajouter"):
            if t.strip() and n.strip():
                ok, msg = db.add_asset(t.strip(), n.strip(), cat, sec.strip(),
                                       gsym.strip() or t.strip(), ysym.strip() or t.strip())
                st.success(msg) if ok else st.error(msg)
                if ok:
                    st.rerun()
            else:
                st.error("Ticker et nom obligatoires.")

    to_del = st.selectbox("Supprimer un actif", ["—"] + assets["ticker"].tolist())
    if to_del != "—" and st.button(f"🗑️ Supprimer {to_del}"):
        db.delete_asset(to_del)
        st.rerun()

# ═══════════════════════ PAGE : PERFORMANCE ═══════════════════════
elif page == "📈 Historique de performance":
    st.title("📈 Historique de performance")
    perf = db.load_perf()
    if perf.empty:
        st.info("Aucun snapshot. Utilise le bouton 📸 du Tableau de bord pour en créer "
                "(idéalement 1 par jour/semaine pour construire ta courbe).")
        st.stop()
    pf_name = st.selectbox("Portefeuille", sorted(perf["portfolio"].unique()))
    p = perf[perf["portfolio"] == pf_name].copy()
    p["date"] = pd.to_datetime(p["date"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=p["date"], y=p["valeur_marche"], name="Valeur de marché",
                             line=dict(color="#26a69a", width=2)))
    fig.add_trace(go.Scatter(x=p["date"], y=p["investi"], name="Investi",
                             line=dict(color="#888", dash="dot")))
    fig.update_layout(template="plotly_dark", height=380, title=f"Évolution — {pf_name}",
                      margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(p.iloc[::-1], use_container_width=True, height=280)
    st.download_button("⬇️ Exporter (CSV)", p.to_csv(index=False),
                       f"performance_{pf_name}.csv", "text/csv")

# ═══════════════════════ PAGE : CORRÉLATIONS ═══════════════════════
elif page == "🔗 Corrélations live":
    st.title("🔗 Corrélations live")
    st.caption("Corrélations de Pearson sur les **rendements** (yfinance, rafraîchi 15 min). "
               "Deux vues : le contexte macro (14 indices/actifs) et la diversification "
               "réelle de ton portefeuille.")

    CORR_ASSETS = {
        "Nasdaq 100": "NQ=F", "S&P 500": "ES=F", "Dow Jones": "YM=F",
        "CAC 40": "^FCHI", "DAX": "^GDAXI", "MSCI World": "URTH",
        "Or": "GC=F", "Argent": "SI=F", "Pétrole WTI": "CL=F",
        "VIX": "^VIX", "US 10Y (taux)": "^TNX", "Dollar Index": "DX-Y.NYB",
        "EUR/USD": "EURUSD=X", "Bitcoin": "BTC-USD",
    }
    PERIODS = {"1 mois": "1mo", "3 mois": "3mo", "6 mois": "6mo", "1 an": "1y"}

    @st.cache_data(ttl=900, show_spinner="Chargement des actifs…")
    def load_closes(tickers: tuple, names: tuple, period: str) -> pd.DataFrame:
        try:
            raw = yf.download(list(tickers), period=period, interval="1d",
                              progress=False, auto_adjust=True)
            closes = raw["Close"] if "Close" in raw else raw
            if isinstance(closes, pd.Series):
                closes = closes.to_frame(tickers[0])
            closes = closes.rename(columns=dict(zip(tickers, names)))
            closes = closes.dropna(axis=1, thresh=int(len(closes) * 0.5)).ffill()
            return closes.dropna(how="all")
        except Exception:
            return pd.DataFrame()

    def corr_heatmap(corr: pd.DataFrame, title: str):
        fig = go.Figure(go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.index, zmin=-1, zmax=1,
            colorscale="RdBu", text=corr.values, texttemplate="%{text:.2f}",
            textfont=dict(size=9), colorbar=dict(title="Corr")))
        fig.update_layout(template="plotly_dark", height=560, title=title,
                          margin=dict(l=10, r=10, t=40, b=10), xaxis=dict(tickangle=-40))
        return fig

    tab1, tab2 = st.tabs(["🌍 Macro — 14 indices & actifs", "💼 Mon portefeuille"])

    with tab1:
        period_key = st.selectbox("Période", list(PERIODS.keys()), index=1)
        names = tuple(CORR_ASSETS.keys())
        closes = load_closes(tuple(CORR_ASSETS.values()), names, PERIODS[period_key])
        if closes.empty or len(closes) < 10:
            st.error("Données indisponibles. Réessaie dans quelques minutes.")
        else:
            corr = closes.pct_change().dropna(how="all").corr(min_periods=8).round(2)
            st.plotly_chart(corr_heatmap(corr, f"Corrélations — {period_key}"),
                            use_container_width=True)
            st.caption("🔵 +1 : bougent ensemble · 🔴 -1 : sens opposés · ~0 : indépendants.")

            # Paires clés pour un investisseur diversifié
            st.subheader("Lecture investisseur")
            pairs = [
                ("Nasdaq 100", "US 10Y (taux)", "Tech/Taux : négative = les hausses de taux pèsent sur ta poche croissance ; les bonds (IEF/TLT) compensent alors mal."),
                ("S&P 500", "Or", "Actions/Or : proche de 0 ou négative = l'or diversifie réellement ton portefeuille."),
                ("MSCI World", "CAC 40", "Monde/Europe : très élevée = détenir les deux n'apporte presque pas de diversification."),
                ("S&P 500", "Bitcoin", "Actions/BTC : élevée = le crypto n'est PAS un diversifiant, c'est du risque actions amplifié."),
                ("Or", "Dollar Index", "Or/DXY : négative structurellement. Un or fort + dollar fort = signal de stress."),
            ]
            for a, b, note in pairs:
                if a in corr.index and b in corr.columns and pd.notna(corr.loc[a, b]):
                    v = corr.loc[a, b]
                    badge = "🔵" if v > 0.4 else ("🔴" if v < -0.4 else "⚪")
                    st.markdown(f"{badge} **{a} ↔ {b} : {v:+.2f}** — {note}")

            with st.expander("📥 Exporter la matrice (CSV)"):
                st.download_button("Télécharger", corr.to_csv(), "correlations_macro.csv", "text/csv")

    with tab2:
        if pf_df.empty:
            st.info("Crée un portefeuille et des positions pour analyser sa diversification.")
        else:
            pf_name = st.selectbox("Portefeuille", pf_df["portfolio"].tolist(), key="corr_pf")
            holds = db.holdings(pf_name)
            if len(holds) < 2:
                st.info("Il faut au moins 2 positions pour calculer des corrélations.")
            else:
                period_key2 = st.selectbox("Période", list(PERIODS.keys()), index=2, key="corr_p2")
                ymap = dict(zip(assets["ticker"], assets["yahoo_symbol"]))
                tickers = tuple(ymap.get(t, t) for t in holds["ticker"])
                names2 = tuple(holds["ticker"])
                closes2 = load_closes(tickers, names2, PERIODS[period_key2])
                if closes2.empty or len(closes2.columns) < 2:
                    st.error("Données insuffisantes sur ces positions.")
                else:
                    corr2 = closes2.pct_change().dropna(how="all").corr(min_periods=8).round(2)
                    st.plotly_chart(corr_heatmap(corr2, f"Diversification — {pf_name}"),
                                    use_container_width=True)
                    # Corrélation moyenne = mesure de diversification effective
                    vals = corr2.values[np.triu_indices_from(corr2.values, k=1)]
                    vals = vals[~np.isnan(vals)]
                    if len(vals):
                        avg = float(np.mean(vals))
                        st.metric("Corrélation moyenne entre positions", f"{avg:+.2f}")
                        if avg > 0.7:
                            st.error("⚠️ Diversification très faible : tes positions bougent quasiment ensemble. "
                                     "En cas de baisse tech, tout ton portefeuille baisse en même temps. "
                                     "Pistes : renforcer la poche Bonds (AGG/IEF/TLT), ajouter EZU/IEMG ou de l'or.")
                        elif avg > 0.45:
                            st.warning("Diversification moyenne : le cœur du portefeuille reste concentré "
                                       "sur un même facteur (tech US probablement).")
                        else:
                            st.success("Bonne diversification effective : les positions ne bougent pas toutes ensemble.")
                        # Paire la plus corrélée = doublon potentiel
                        c2m = corr2.where(~np.eye(len(corr2), dtype=bool))
                        idx = np.unravel_index(np.nanargmax(c2m.values), c2m.shape)
                        st.caption(f"Paire la plus corrélée : **{corr2.index[idx[0]]} ↔ {corr2.columns[idx[1]]} "
                                   f"({c2m.values[idx]:+.2f})** — potentiel doublon, garder un seul des deux "
                                   "peut suffire.")

st.sidebar.divider()
st.sidebar.caption("⚠️ Les CSV sont éphémères sur Streamlit Cloud : exporte régulièrement. "
                   "Ceci n'est pas un conseil financier.")
