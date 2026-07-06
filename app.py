"""
ETFCore — Plateforme d'investissement ETF
==========================================
Prix : Google Finance en priorité, Yahoo Finance en fallback.
Persistance : fichiers CSV (data/assets.csv, portfolios.csv,
transactions.csv, performance_history.csv).

Lancement :  streamlit run app.py
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import storage as db
from data_fetcher import get_price, get_index_dashboard, get_history, WORLD_INDICES

# ---------------------------------------------------------------------------
# CONFIG & THEME
# ---------------------------------------------------------------------------
st.set_page_config(page_title="ETFCore — Plateforme ETF", page_icon="📈", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(180deg,#0b1020 0%,#0e1428 100%); color:#e8ecf5; }
h1,h2,h3 { color:#e8ecf5 !important; }
[data-testid="stMetric"] {
  background:#141b33; border:1px solid #263259; border-radius:14px; padding:14px;
}
[data-testid="stMetricLabel"] { color:#9fb0d8 !important; }
[data-testid="stSidebar"] { background:#0a0f1f; border-right:1px solid #1d2848; }
div.stButton>button {
  background:linear-gradient(90deg,#2557d6,#6e3df5); color:#fff; border:0;
  border-radius:10px; font-weight:600;
}
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px;
  background:#1d2848; border:1px solid #35437a; color:#9fb0d8; margin-right:6px;}
</style>
""", unsafe_allow_html=True)

PALETTE = ["#4f8cff", "#8b5cf6", "#22d3ee", "#f59e0b", "#10b981",
           "#ef4444", "#e879f9", "#84cc16", "#fb7185", "#38bdf8"]
CAT_COLORS = {"ETF": "#4f8cff", "Action": "#8b5cf6", "Bond": "#10b981"}


def style_fig(fig, h=380):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d4ee"), height=h,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor="#1d2848")
    fig.update_yaxes(gridcolor="#1d2848")
    return fig


def valorise(holds: pd.DataFrame, assets: pd.DataFrame) -> pd.DataFrame:
    """Ajoute prix actuel (Google→Yahoo), valeur, gain/perte aux positions."""
    if holds.empty:
        return holds
    rows = []
    for _, r in holds.iterrows():
        a = assets[assets["ticker"] == r["ticker"]]
        g_sym = a["google_symbol"].iloc[0] if not a.empty else r["ticker"]
        y_sym = a["yahoo_symbol"].iloc[0] if not a.empty else r["ticker"]
        q = get_price(g_sym, y_sym)
        px_now = q["price"]
        val = px_now * r["quantite"] if px_now else None
        rows.append({**r, "prix_actuel": px_now, "source": q["source"],
                     "valeur": val,
                     "gain_perte": (val - r["investi"]) if val is not None else None,
                     "rdmt_pct": ((val / r["investi"] - 1) * 100) if (val is not None and r["investi"]) else None})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# SIDEBAR / NAVIGATION
# ---------------------------------------------------------------------------
st.sidebar.title("📈 ETFCore")
st.sidebar.caption("Google Finance ▸ fallback Yahoo Finance")
page = st.sidebar.radio("Navigation", [
    "🏠 Accueil",
    "🌍 Indices mondiaux",
    "💼 Mes portefeuilles",
    "🛒 Transactions",
    "📊 Performance",
    "🗂️ Actifs & données (CSV)",
])
st.sidebar.divider()
st.sidebar.markdown(
    "<span class='badge'>Actions 15%</span><span class='badge'>ETFs 65%</span>"
    "<span class='badge'>Bonds 20%</span>", unsafe_allow_html=True)
st.sidebar.caption("Stratégie cible par défaut (modifiable par portefeuille).")

assets = db.load_assets()

# ===========================================================================
# 🏠 ACCUEIL
# ===========================================================================
if page == "🏠 Accueil":
    st.title("🏠 Plateforme d'investissement ETF")
    st.caption("Prix Google Finance en priorité — bascule automatique sur Yahoo Finance si indisponible.")

    # --- Aperçu marché (mini-dashboard indices) ---
    # try/except : si Google ET Yahoo échouent, la page s'affiche quand même
    try:
        with st.spinner("Chargement des indices…"):
            idx = get_index_dashboard()
    except Exception as e:
        idx = pd.DataFrame(columns=["Indice", "Prix", "Var 1J %"])
        st.warning(f"Indices momentanément indisponibles ({e}). Le reste de la plateforme fonctionne.")
    key_idx = ["S&P500", "NASDAQ", "CAC 40", "DAX", "Nikkei 225", "VIX"]
    cols = st.columns(len(key_idx))
    for c, name in zip(cols, key_idx):
        row = idx[idx["Indice"] == name] if not idx.empty else pd.DataFrame()
        if row.empty or pd.isna(row["Prix"].iloc[0]):
            c.metric(name, "N/A")
        else:
            chg = row["Var 1J %"].iloc[0]
            c.metric(name, f"{row['Prix'].iloc[0]:,.2f}",
                     f"{chg:+.2f}%" if pd.notna(chg) else None)

    st.divider()

    # --- Catégories principales d'investissement ---
    st.subheader("Catégories principales d'investissement")
    c1, c2 = st.columns([1, 1])

    with c1:
        cat_counts = assets.groupby("categorie").size().reset_index(name="Nb actifs")
        fig = px.pie(cat_counts, names="categorie", values="Nb actifs", hole=0.55,
                     color="categorie", color_discrete_map=CAT_COLORS,
                     title="Univers d'actifs par catégorie")
        st.plotly_chart(style_fig(fig), use_container_width=True)

    with c2:
        sec_counts = assets.groupby("secteur").size().reset_index(name="Nb actifs").sort_values("Nb actifs")
        fig = px.bar(sec_counts, x="Nb actifs", y="secteur", orientation="h",
                     color_discrete_sequence=["#4f8cff"], title="Répartition sectorielle de l'univers")
        st.plotly_chart(style_fig(fig), use_container_width=True)

    # --- Explorateur interactif de catégories ---
    st.subheader("🔎 Explorer une catégorie")
    e1, e2 = st.columns([1, 3])
    cat_sel = e1.selectbox("Catégorie", ["ETF", "Action", "Bond"])
    sect_opts = ["Tous"] + sorted(assets.query("categorie == @cat_sel")["secteur"].unique().tolist())
    sect_sel = e1.selectbox("Secteur", sect_opts)
    sub = assets.query("categorie == @cat_sel")
    if sect_sel != "Tous":
        sub = sub.query("secteur == @sect_sel")
    e2.dataframe(sub[["ticker", "nom", "secteur", "google_symbol", "yahoo_symbol"]],
                 use_container_width=True, hide_index=True)

    tick = e1.selectbox("Graphique", sub["ticker"].tolist() if not sub.empty else [])
    if tick:
        y_sym = assets.loc[assets["ticker"] == tick, "yahoo_symbol"].iloc[0]
        hist = get_history(y_sym, "1y")
        if not hist.empty:
            fig = go.Figure(go.Scatter(x=hist.index, y=hist["Close"], mode="lines",
                                       line=dict(color="#22d3ee", width=2), name=tick))
            fig.update_layout(title=f"{tick} — 12 mois (Yahoo Finance)")
            st.plotly_chart(style_fig(fig, 320), use_container_width=True)
        else:
            st.info("Historique indisponible pour cet actif.")

    # --- Vue synthétique de mes portefeuilles ---
    pfs = db.load_portfolios()
    st.subheader("💼 Mes portefeuilles")
    if pfs.empty:
        st.info("Aucun portefeuille — crée ton premier dans l'onglet **💼 Mes portefeuilles**.")
    else:
        for _, p in pfs.iterrows():
            h = valorise(db.holdings(p["portfolio"]), assets)
            invested = h["investi"].sum() if not h.empty else 0
            value = h["valeur"].dropna().sum() if not h.empty else 0
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(f"📁 {p['portfolio']}", f"{p['capital']:,.0f} {p['devise']}")
            k2.metric("Investi", f"{invested:,.2f}")
            k3.metric("Valeur marché", f"{value:,.2f}")
            gain = value - invested
            k4.metric("Gain / Perte", f"{gain:,.2f}",
                      f"{(gain/invested*100):+.2f}%" if invested else None)

# ===========================================================================
# 🌍 INDICES MONDIAUX
# ===========================================================================
elif page == "🌍 Indices mondiaux":
    st.title("🌍 Indices mondiaux")
    st.caption("USA · Europe · Asie · Fear Index (VIX) — comme dans ta feuille Gestion_Portefeuille.")

    try:
        with st.spinner("Récupération des indices…"):
            idx = get_index_dashboard()
    except Exception as e:
        st.error(f"Impossible de récupérer les indices : {e}")
        st.stop()

    for region in ["USA", "Europe", "Asie", "Fear Index"]:
        st.subheader(region)
        sub = idx[idx["Région"] == region]
        cols = st.columns(max(len(sub), 1))
        for c, (_, r) in zip(cols, sub.iterrows()):
            if pd.isna(r["Prix"]):
                c.metric(r["Indice"], "N/A")
            else:
                c.metric(r["Indice"], f"{r['Prix']:,.2f}",
                         f"{r['Var 1J %']:+.2f}%" if pd.notna(r["Var 1J %"]) else None)
        st.caption(" · ".join(f"{r['Indice']}: {r['Source']}" for _, r in sub.iterrows()))

    st.divider()
    st.subheader("📉 Comparaison graphique (base 100)")
    choices = st.multiselect("Indices à comparer", list(WORLD_INDICES.keys()),
                             default=["S&P500", "CAC 40", "Nikkei 225"])
    period = st.select_slider("Période", ["1mo", "3mo", "6mo", "1y", "2y"], value="1y")
    if choices:
        fig = go.Figure()
        for i, name in enumerate(choices):
            y_sym = WORLD_INDICES[name][1]
            h = get_history(y_sym, period)
            if not h.empty:
                base = h["Close"] / h["Close"].iloc[0] * 100
                fig.add_trace(go.Scatter(x=h.index, y=base, name=name,
                                         line=dict(color=PALETTE[i % len(PALETTE)], width=2)))
        fig.update_layout(title="Performance relative (base 100)")
        st.plotly_chart(style_fig(fig, 460), use_container_width=True)

# ===========================================================================
# 💼 MES PORTEFEUILLES (création avec allocations)
# ===========================================================================
elif page == "💼 Mes portefeuilles":
    st.title("💼 Constructeur de portefeuilles")

    with st.expander("➕ Créer un portefeuille", expanded=db.load_portfolios().empty):
        c1, c2, c3 = st.columns(3)
        nom = c1.text_input("Nom du portefeuille", placeholder="Ex: ETF Croissance 2026")
        capital = c2.number_input("Capital (montant)", min_value=100.0, value=31000.0, step=500.0)
        devise = c3.selectbox("Devise", ["€", "$"])

        st.markdown("**Allocation cible** (stratégie visée)")
        a1, a2, a3 = st.columns(3)
        al_act = a1.slider("Actions %", 0, 100, 15)
        al_etf = a2.slider("ETFs %", 0, 100, 65)
        al_bond = a3.slider("Bonds %", 0, 100, 20)
        total = al_act + al_etf + al_bond
        (st.success if total == 100 else st.warning)(f"Total allocation : {total}%")

        fig = px.pie(names=["Actions", "ETFs", "Bonds"], values=[al_act, al_etf, al_bond],
                     hole=0.5, color=["Actions", "ETFs", "Bonds"],
                     color_discrete_map={"Actions": "#8b5cf6", "ETFs": "#4f8cff", "Bonds": "#10b981"})
        st.plotly_chart(style_fig(fig, 280), use_container_width=True)

        st.markdown("**Montants par poche**")
        m1, m2, m3 = st.columns(3)
        m1.metric("Actions", f"{capital*al_act/100:,.0f} {devise}")
        m2.metric("ETFs", f"{capital*al_etf/100:,.0f} {devise}")
        m3.metric("Bonds", f"{capital*al_bond/100:,.0f} {devise}")

        if st.button("Créer le portefeuille", disabled=(total != 100 or not nom)):
            ok, msg = db.create_portfolio(nom, capital, devise, al_act, al_etf, al_bond)
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()

    pfs = db.load_portfolios()
    if pfs.empty:
        st.stop()

    st.divider()
    sel = st.selectbox("Portefeuille", pfs["portfolio"].tolist())
    p = pfs[pfs["portfolio"] == sel].iloc[0]
    h = valorise(db.holdings(sel), assets)

    invested = h["investi"].sum() if not h.empty else 0
    value = h["valeur"].dropna().sum() if not h.empty else 0
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Capital", f"{p['capital']:,.0f} {p['devise']}")
    k2.metric("Investi", f"{invested:,.2f}")
    k3.metric("Liquidités", f"{p['capital']-invested:,.2f}")
    k4.metric("Valeur marché", f"{value:,.2f}")
    gain = value - invested
    k5.metric("Gain/Perte", f"{gain:,.2f}", f"{(gain/invested*100):+.2f}%" if invested else None)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Stratégie visée vs actuelle**")
        cible = pd.DataFrame({"Catégorie": ["Action", "ETF", "Bond"],
                              "Visée %": [p["alloc_actions"], p["alloc_etf"], p["alloc_bonds"]]})
        if not h.empty and invested:
            act = h.groupby("categorie")["investi"].sum() / invested * 100
            cible["Actuelle %"] = cible["Catégorie"].map(act).fillna(0).round(1)
        else:
            cible["Actuelle %"] = 0.0
        fig = go.Figure()
        fig.add_bar(x=cible["Catégorie"], y=cible["Visée %"], name="Visée", marker_color="#4f8cff")
        fig.add_bar(x=cible["Catégorie"], y=cible["Actuelle %"], name="Actuelle", marker_color="#f59e0b")
        fig.update_layout(barmode="group", title="Allocation (%)")
        st.plotly_chart(style_fig(fig, 340), use_container_width=True)
    with c2:
        if not h.empty:
            sec = h.groupby("secteur")["investi"].sum().reset_index()
            fig = px.pie(sec, names="secteur", values="investi", hole=0.5,
                         color_discrete_sequence=PALETTE, title="Répartition sectorielle")
            st.plotly_chart(style_fig(fig, 340), use_container_width=True)
        else:
            st.info("Aucune position — ajoute des transactions dans l'onglet 🛒.")

    if not h.empty:
        st.markdown("**Positions**")
        show = h[["ticker", "categorie", "secteur", "quantite", "pru", "prix_actuel",
                  "investi", "valeur", "gain_perte", "rdmt_pct", "source"]].copy()
        show.columns = ["Ticker", "Catégorie", "Secteur", "Qté", "PRU", "Prix actuel",
                        "Investi", "Valeur", "Gain/Perte", "Rdmt %", "Source prix"]
        st.dataframe(show.round(2), use_container_width=True, hide_index=True)

        if st.button("📸 Enregistrer un snapshot de performance (CSV)"):
            db.snapshot_perf(sel, value, invested)
            st.success("Snapshot enregistré dans data/performance_history.csv ✔")

    with st.expander("🗑️ Supprimer ce portefeuille"):
        if st.button(f"Supprimer définitivement « {sel} »"):
            db.delete_portfolio(sel)
            st.rerun()

# ===========================================================================
# 🛒 TRANSACTIONS
# ===========================================================================
elif page == "🛒 Transactions":
    st.title("🛒 Transactions (achat / vente)")
    pfs = db.load_portfolios()
    if pfs.empty:
        st.warning("Crée d'abord un portefeuille dans 💼 Mes portefeuilles.")
        st.stop()

    c1, c2, c3 = st.columns(3)
    pf = c1.selectbox("Portefeuille", pfs["portfolio"].tolist())
    cat = c2.selectbox("Catégorie", ["ETF", "Action", "Bond"])
    tick = c3.selectbox("Actif", assets.query("categorie == @cat")["ticker"].tolist())

    a = assets[assets["ticker"] == tick].iloc[0]
    q = get_price(a["google_symbol"], a["yahoo_symbol"])

    c4, c5, c6 = st.columns(3)
    if q["price"]:
        c4.metric(f"Prix {tick}", f"{q['price']:,.2f}", help=f"Source : {q['source']}")
        c4.caption(f"🔌 {q['source']}")
    else:
        c4.warning("Prix indisponible (Google & Yahoo). Saisis-le manuellement.")
    sens = c5.radio("Sens", ["Achat", "Vente"], horizontal=True)
    qty = c6.number_input("Quantité", min_value=0.01, value=1.0, step=1.0)

    prix = st.number_input("Prix d'exécution", min_value=0.01,
                           value=float(q["price"]) if q["price"] else 100.0)
    st.metric("Montant", f"{qty*prix:,.2f}")

    if st.button("✅ Enregistrer la transaction"):
        db.add_transaction(pf, tick, a["categorie"], a["secteur"], sens, qty, prix,
                           q["source"] if q["price"] else "Manuel")
        st.success(f"{sens} {qty} × {tick} @ {prix:,.2f} enregistré dans data/transactions.csv ✔")

    st.divider()
    st.subheader("Historique des transactions")
    tx = db.load_transactions()
    tx = tx[tx["portfolio"] == pf]
    if tx.empty:
        st.info("Aucune transaction pour ce portefeuille.")
    else:
        st.dataframe(tx.sort_values("date", ascending=False),
                     use_container_width=True, hide_index=True)

# ===========================================================================
# 📊 PERFORMANCE
# ===========================================================================
elif page == "📊 Performance":
    st.title("📊 Suivi de performance")
    perf = db.load_perf()
    if perf.empty:
        st.info("Aucun snapshot. Depuis 💼 Mes portefeuilles, clique sur "
                "« 📸 Enregistrer un snapshot » pour alimenter performance_history.csv.")
        st.stop()

    pf_sel = st.multiselect("Portefeuilles", perf["portfolio"].unique().tolist(),
                            default=perf["portfolio"].unique().tolist())
    sub = perf[perf["portfolio"].isin(pf_sel)].copy()
    sub["date"] = pd.to_datetime(sub["date"])

    fig = px.line(sub, x="date", y="valeur_marche", color="portfolio",
                  markers=True, color_discrete_sequence=PALETTE,
                  title="Valeur de marché dans le temps")
    st.plotly_chart(style_fig(fig, 400), use_container_width=True)

    fig2 = px.line(sub, x="date", y="perf_pct", color="portfolio",
                   markers=True, color_discrete_sequence=PALETTE,
                   title="Performance % dans le temps")
    fig2.add_hline(y=0, line_dash="dot", line_color="#9fb0d8")
    st.plotly_chart(style_fig(fig2, 360), use_container_width=True)

    st.dataframe(sub.sort_values("date", ascending=False),
                 use_container_width=True, hide_index=True)

# ===========================================================================
# 🗂️ ACTIFS & DONNÉES (CSV)
# ===========================================================================
elif page == "🗂️ Actifs & données (CSV)":
    st.title("🗂️ Univers d'actifs & fichiers CSV")

    with st.expander("➕ Ajouter un actif à l'univers"):
        c1, c2, c3 = st.columns(3)
        t = c1.text_input("Ticker", placeholder="VWCE")
        n = c2.text_input("Nom", placeholder="Vanguard FTSE All-World")
        cat = c3.selectbox("Catégorie", ["ETF", "Action", "Bond"])
        c4, c5, c6 = st.columns(3)
        sec = c4.text_input("Secteur", placeholder="Monde")
        gsym = c5.text_input("Symbole Google Finance", placeholder="FRA:VWCE ou NYSEARCA:XXX")
        ysym = c6.text_input("Symbole Yahoo Finance", placeholder="VWCE.DE")
        if st.button("Ajouter l'actif"):
            if t and gsym and ysym:
                ok, msg = db.add_asset(t, n or t, cat, sec or "Autre", gsym, ysym)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()
            else:
                st.error("Ticker + symboles Google et Yahoo sont obligatoires.")

    st.subheader("Univers actuel (data/assets.csv)")
    st.dataframe(assets, use_container_width=True, hide_index=True)
    del_t = st.selectbox("Supprimer un actif", ["—"] + assets["ticker"].tolist())
    if del_t != "—" and st.button(f"Supprimer {del_t}"):
        db.delete_asset(del_t)
        st.rerun()

    st.divider()
    st.subheader("⬇️ Télécharger les CSV")
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("assets.csv", assets.to_csv(index=False), "assets.csv", "text/csv")
    d2.download_button("portfolios.csv", db.load_portfolios().to_csv(index=False), "portfolios.csv", "text/csv")
    d3.download_button("transactions.csv", db.load_transactions().to_csv(index=False), "transactions.csv", "text/csv")
    d4.download_button("performance_history.csv", db.load_perf().to_csv(index=False), "performance_history.csv", "text/csv")
    st.caption("⚠️ Sur Streamlit Cloud le disque est éphémère : télécharge régulièrement tes CSV "
               "(ou pousse le dossier data/ sur GitHub) pour ne rien perdre.")
