# -*- coding: utf-8 -*-
"""
NQ Command Center — Plateforme d'analyse ICT/MMM multi-timeframe
Nasdaq · S&P 500 · Or | Risque prop firm MMM | VIX | Macro | ML | Journal

⚠️ Outil d'aide à la décision. Ceci n'est pas un conseil financier.
"""
import datetime as dt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules import data_loader as dl
from modules import ict_analysis as ict
from modules import mmm_analysis as mmm
from modules import risk_calculator as rc
from modules import vix_sentiment as vs
from modules import news_events as ne
from modules import ml_engine as ml
from modules import pattern_memory as pm
from modules import journal as jr
from modules import charts as ch
from modules import correlations as cor

st.set_page_config(page_title="NQ Command Center", page_icon="📡", layout="wide")

st.markdown("""
<style>
    .main .block-container {padding-top: 1.2rem;}
    div[data-testid="stMetric"] {background: #161b22; border: 1px solid #2a313c;
        border-radius: 8px; padding: 10px 14px;}
    .stTabs [data-baseweb="tab"] {font-size: 0.95rem;}
</style>
""", unsafe_allow_html=True)

# ───────────────────────────── Sidebar ─────────────────────────────
st.sidebar.title("📡 NQ Command Center")
st.sidebar.caption("ICT · MMM · Macro · ML — *pas un conseil financier*")

page = st.sidebar.radio("Navigation", [
    "🎯 Dashboard & Signal",
    "📊 Analyse ICT multi-TF",
    "🧮 Risque prop firm (MMM)",
    "📓 Journal de trading",
    "😱 VIX & Psychologie",
    "🔗 Corrélations live",
    "🌍 Événements du jour",
    "🤖 Machine Learning",
    "🧠 Mémoire des patterns",
])

instrument = st.sidebar.selectbox("Instrument", list(dl.SYMBOLS.keys()))
ticker = dl.SYMBOLS[instrument]

if st.sidebar.button("🔄 Rafraîchir les données"):
    st.cache_data.clear()
    st.rerun()


@st.cache_data(ttl=300, show_spinner="Chargement des données…")
def full_analysis(tk: str):
    """Charge tous les TF, analyse ICT + MMM, calcule la confluence."""
    tfs = dl.load_all_timeframes(tk)
    analyses, mmm_res = {}, {}
    for tf, df in tfs.items():
        analyses[tf] = ict.analyze_timeframe(df, tf) if not df.empty else None
        mmm_res[tf] = mmm.mmm_summary(df) if not df.empty else None
    ltf_df = tfs.get("15m") if tfs.get("15m") is not None and not tfs["15m"].empty else tfs.get("1D")
    atr_val = float(dl.atr(ltf_df).iloc[-1]) if ltf_df is not None and len(ltf_df) > 15 else 0
    conf = ict.multi_tf_confluence(analyses, atr_val)
    return tfs, analyses, mmm_res, conf


# ═════════════════════════ PAGE : DASHBOARD ═════════════════════════
if page == "🎯 Dashboard & Signal":
    st.title(f"🎯 Signal de trading — {instrument}")
    tfs, analyses, mmm_res, conf = full_analysis(ticker)

    if conf is None:
        st.error("Données indisponibles pour cet instrument (yfinance). Réessaie dans quelques minutes.")
        st.stop()

    vix_df = dl.load_vix()
    spx_df = dl.load_ohlc("ES=F", "1D")
    fg = vs.fear_greed_composite(vix_df, spx_df)

    c1, c2, c3, c4 = st.columns(4)
    dir_emoji = {"LONG": "🟢", "SHORT": "🔴", "NEUTRE": "⚪"}[conf["direction"]]
    c1.metric("Direction suggérée", f"{dir_emoji} {conf['direction']}")
    c2.metric("Probabilité hausse", f"{conf['prob_up']} %")
    c3.metric("Probabilité baisse", f"{conf['prob_down']} %")
    if fg:
        c4.metric("VIX / Sentiment", f"{fg['vix']:.1f} — {fg['label']}")

    # Filtre MMM : No body close, no trade
    ltf_mmm = mmm_res.get("15m")
    if ltf_mmm and ltf_mmm["no_trade"]:
        st.warning("⛔ **Règle MMM : dernière bougie 15m en NBC (pas de body close) → No Trade.** "
                   "Attendre un BuBC ou BeBC pour confirmer l'agression d'un camp.")

    # Plan de trade
    st.subheader("Plan de trade proposé (RR 1:2)")
    if conf["plan"]:
        p = conf["plan"]
        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("Entrée", f"{p['entry']:,}")
        pc2.metric("Stop Loss", f"{p['sl']:,}")
        pc3.metric("Take Profit (2R)", f"{p['tp']:,}")
        pc4.metric("Stop en points", f"{p['stop_pts']}")
        st.caption("Entrée positionnée sur FVG/Order Block du timeframe bas dans le sens de la confluence ; "
                   "stop dimensionné sur 1,2 × ATR. Utilise l'onglet Risque pour la taille de position exacte.")
    else:
        st.info("Marché sans direction claire (confluence neutre). Le meilleur trade est parfois de ne pas trader.")

    # Détail des scores par TF
    st.subheader("Confluence par timeframe")
    cols = st.columns(len(conf["detail"]))
    for col, (tf, d) in zip(cols, conf["detail"].items()):
        emoji = "🟢" if d["bias"] == "Haussier" else ("🔴" if d["bias"] == "Baissier" else "⚪")
        col.metric(f"{tf}", f"{emoji} {d['bias']}", f"score {d['score']:+.1f}")

    # Raisons du signal (TF 15m + 1D)
    with st.expander("🔍 Justification du signal (lecture ICT)"):
        for tf in ["1D", "60m", "15m", "5m"]:
            a = analyses.get(tf)
            if a and a["reasons"]:
                st.markdown(f"**{tf}** — zone {a['pd']['zone']} ({a['pd']['pct_range']:.0f}% du range)")
                for r in a["reasons"]:
                    st.markdown(f"- {r}")

    # Impact macro du jour
    st.subheader("Contexte macro du jour")
    events = ne.fetch_events()
    imp = ne.market_impact_summary(events)
    if imp:
        m1, m2, m3 = st.columns(3)
        m1.metric("Effet net Nasdaq", imp["nq_txt"])
        m2.metric("Effet net Or", imp["gold_txt"])
        m3.metric("Annonces à fort impact", imp["high_impact"])
        if imp["warning"]:
            st.error("⚠️ Journée à haut risque événementiel : plusieurs annonces majeures. "
                     "Réduire la taille ou éviter les entrées autour des publications.")
    else:
        st.caption("Aucun événement significatif détecté sur les flux (ou flux indisponibles).")

    # Enregistrement du contexte dans la mémoire
    if st.button("💾 Enregistrer ce contexte dans la mémoire des patterns"):
        a15 = analyses.get("15m") or analyses.get("1D")
        mlr = None
        try:
            mlr = ml.train_predict(tfs["1D"])
        except Exception:
            pass
        pm.record_context(
            symbole=instrument, timeframe="multi", prix=a15["price"],
            biais=a15["bias"], sweep=a15["sweeps"][-1]["type"] if a15["sweeps"] else "aucun",
            n_fvg=len(a15["fvgs"]), body_close=ltf_mmm["last_state"] if ltf_mmm else "?",
            zone_pd=a15["pd"]["zone"], vix_regime=fg["regime"]["regime"] if fg else "?",
            prob_ict=conf["prob_up"], prob_ml=mlr["proba_up"] if mlr else "",
            direction=conf["direction"])
        st.success("Contexte enregistré dans data/patterns_memory.csv ✅")

# ═════════════════════ PAGE : ANALYSE MULTI-TF ═════════════════════
elif page == "📊 Analyse ICT multi-TF":
    st.title(f"📊 Analyse ICT / MMM — {instrument}")
    tfs, analyses, mmm_res, conf = full_analysis(ticker)

    tabs = st.tabs(["5 minutes", "15 minutes", "60 minutes", "Journalier"])
    for tab, tf in zip(tabs, ["5m", "15m", "60m", "1D"]):
        with tab:
            df, a, m = tfs.get(tf), analyses.get(tf), mmm_res.get(tf)
            if df is None or df.empty or a is None:
                st.warning("Données indisponibles pour ce timeframe.")
                continue
            st.plotly_chart(ch.candles_with_ict(df.tail(200), a, m,
                            f"{instrument} — {tf}"), use_container_width=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Biais ICT", a["bias"], f"score {a['score']:+.1f}")
            c2.metric("Zone", a["pd"]["zone"].upper(), f"{a['pd']['pct_range']:.0f}% du range")
            if m:
                c3.metric("État MMM", m["last_state"],
                          "No Trade" if m["no_trade"] else "Body close ✓")

            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown("**Lecture ICT**")
                for r in a["reasons"] or ["Aucun signal notable."]:
                    st.markdown(f"- {r}")
                if a["fvgs"]:
                    st.markdown("**FVG non comblés :** " + ", ".join(
                        f"{g['type']} [{g['bot']:.1f} – {g['top']:.1f}]" for g in a["fvgs"][-4:]))
            with col_r:
                if m:
                    st.markdown("**Lecture Order Flow (MMM)**")
                    if m["accelerators"]:
                        ax = m["accelerators"][-1]
                        st.markdown(f"- Dernier accélérateur : **{ax['type']}** (×{ax['ratio']})")
                    for lv in m["wickless"][-3:]:
                        st.markdown(f"- Niveau {lv['type']} non balayé @ **{lv['level']:.1f}** (cible probable)")
                    for g in m["gaps"][-3:]:
                        st.markdown(f"- Gap {g['type']} ouvert [{g['bot']:.1f} – {g['top']:.1f}]")
                    for ev in m["absorption"][-2:]:
                        st.markdown(f"- @ {ev['level']:.1f} : *{ev['label']}* (vol ×{ev['vr']})")

# ═════════════════════ PAGE : RISQUE PROP FIRM ═════════════════════
elif page == "🧮 Risque prop firm (MMM)":
    st.title("🧮 Calculateur MMM — Risk & Lot Size")
    st.caption("Framework : Drawdown ÷ 10 = risque max/trade · 1 micro / 1000$ de DD · "
               "minis à partir de 10 000$ de DD · max 3 trades/jour · RR minimum 1:2.")

    c1, c2 = st.columns(2)
    with c1:
        account = st.number_input("Taille du compte financé ($)", 1000, 1000000, 50000, step=5000)
        drawdown = st.number_input("Drawdown disponible ($) — ton vrai capital", 100, 200000, 2500, step=100)
    with c2:
        instr = st.selectbox("Instrument tradé", list(rc.POINT_VALUES.keys()))
        winrate = st.slider("Ton winrate estimé (%)", 20, 80, 40)

    res = rc.mmm_position_size(drawdown, instr)

    st.subheader("Dimensionnement")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Risque max / trade", f"${res['max_risk']:,.0f}", "DD ÷ 10")
    m2.metric("Micros au total", res["micros_total"])
    if res["minis"] > 0:
        m3.metric("Soit en Minis", f"{res['minis']} mini(s) + {res['micros_restants']} micro(s)")
    else:
        m3.metric("Minis", "🔒 Débloqués à 10k$ DD")
    m4.metric("Stop max", f"{res['stop_max_points']} pts",
              f"@ ${res['point_value_total']:.0f}/pt")

    if res["micros_total"] == 0:
        st.error("Drawdown < 1000$ : aucune taille recommandée. Le compte ne survivrait pas à 10 pertes.")
    else:
        st.success(f"Ce dimensionnement supporte **10 pertes consécutives** avant liquidation "
                   f"({res['micros_total']} micros × ~100$/trade de risque).")

    # Comparaison avec la règle 1% classique
    with st.expander("Pourquoi pas la règle du 1% classique ?"):
        st.markdown(f"""
| Approche | Risque/trade | Pertes avant liquidation |
|---|---|---|
| 1% du compte ({account:,}$) | ${account * 0.01:,.0f} | **{max(1, int(drawdown / (account * 0.01)))} trades** ⚠️ |
| 1% du drawdown | ${drawdown * 0.01:,.0f} | 100 trades (croissance trop lente) |
| **MMM : DD ÷ 10** | **${res['max_risk']:,.0f}** | **10 trades** ✅ |
""")

    st.subheader("Matrice des 5 scénarios journaliers (3 trades max, RR 1:2)")
    matrix = rc.daily_matrix(res["max_risk"])
    dfm = pd.DataFrame(matrix)
    dfm["resultat"] = dfm["resultat"].map(lambda x: f"{'+' if x > 0 else ''}{x:,.0f} $")
    st.table(dfm.rename(columns={"scenario": "Scénario", "resultat": "Résultat", "action": "Action"}))

    exp = rc.expectancy(winrate, res["max_risk"])
    st.metric("Espérance par trade à ce winrate", f"${exp:,.0f}",
              "Positive ✅" if exp > 0 else "Négative — travailler le winrate ou le RR ⚠️")
    st.caption(f"Avec un RR 1:2, le seuil de rentabilité est à 33,3% de winrate. Tu es à {winrate}%.")

# ═════════════════════ PAGE : JOURNAL ═════════════════════
elif page == "📓 Journal de trading":
    st.title("📓 Journal de trading")
    df_j = jr.load_journal()
    n_today = jr.trades_today(df_j)

    if n_today >= 3:
        st.error(f"⛔ {n_today} trades enregistrés aujourd'hui. **Règle MMM : STOP TRADING.**")
    elif n_today > 0:
        st.info(f"{n_today}/3 trades aujourd'hui. Il t'en reste {3 - n_today}.")

    with st.expander("➕ Ajouter un trade", expanded=df_j.empty):
        c1, c2, c3 = st.columns(3)
        with c1:
            t_date = st.date_input("Date", dt.date.today())
            t_time = st.time_input("Heure", dt.datetime.now().time())
            t_instr = st.selectbox("Instrument", list(dl.SYMBOLS.keys()) + ["Autre"])
            t_dir = st.selectbox("Direction", ["LONG", "SHORT"])
        with c2:
            t_session = st.selectbox("Session", ["Asie", "Londres", "New York AM", "New York PM"])
            t_setup = st.selectbox("Setup", ["FVG", "Order Block", "Sweep + MSS", "BOS continuation",
                                             "UH/UL cible", "Absorption", "Autre"])
            t_entry = st.number_input("Entrée", 0.0, step=0.25, format="%.2f")
            t_stop = st.number_input("Stop", 0.0, step=0.25, format="%.2f")
        with c3:
            t_target = st.number_input("Target", 0.0, step=0.25, format="%.2f")
            t_exit = st.number_input("Sortie réelle", 0.0, step=0.25, format="%.2f")
            t_contracts = st.number_input("Contrats (micros)", 1, 100, 5)
            t_risk = st.number_input("Risque ($)", 0.0, step=50.0)
        t_result = st.number_input("Résultat ($)", step=50.0, format="%.2f")
        t_plan = st.checkbox("Plan respecté ?", True)
        t_notes = st.text_area("Notes (contexte, émotion, erreur…)", height=80)
        if st.button("Enregistrer le trade", type="primary"):
            jr.add_trade(date=t_date.isoformat(), heure=t_time.strftime("%H:%M"),
                         instrument=t_instr, direction=t_dir, session=t_session, setup=t_setup,
                         entree=t_entry, stop=t_stop, target=t_target, sortie=t_exit,
                         contrats=t_contracts, risque_usd=t_risk, resultat_usd=t_result,
                         respect_plan="Oui" if t_plan else "Non", notes=t_notes)
            st.success("Trade enregistré ✅")
            st.rerun()

    if not df_j.empty:
        s = jr.stats(df_j)
        st.subheader("Statistiques")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Trades", s["n_trades"])
        m2.metric("Winrate", f"{s['winrate']}%")
        m3.metric("P&L total", f"${s['pnl_total']:,.0f}")
        m4.metric("Profit factor", s["profit_factor"])
        m5.metric("R moyen", s["avg_r"])

        fig = go.Figure(go.Scatter(y=s["equity"], mode="lines+markers",
                                   line=dict(color="#26a69a", width=2)))
        fig.update_layout(title="Courbe d'équité", template="plotly_dark", height=300,
                          margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Historique")
        st.dataframe(df_j.iloc[::-1], use_container_width=True, height=320)

        col_d, col_e = st.columns(2)
        with col_d:
            idx = st.number_input("Supprimer la ligne n° (0 = plus ancien)", 0, max(0, len(df_j) - 1), 0)
            if st.button("🗑️ Supprimer"):
                jr.delete_trade(int(idx)); st.rerun()
        with col_e:
            st.download_button("⬇️ Exporter le journal (CSV)", df_j.to_csv(index=False),
                               "journal_trading.csv", "text/csv")
    else:
        st.caption("Aucun trade enregistré pour l'instant.")

# ═════════════════════ PAGE : VIX ═════════════════════
elif page == "😱 VIX & Psychologie":
    st.title("😱 VIX & Psychologie du marché")
    vix_df = dl.load_vix()
    spx_df = dl.load_ohlc("ES=F", "1D")
    fg = vs.fear_greed_composite(vix_df, spx_df)

    if fg is None:
        st.error("VIX indisponible pour le moment.")
        st.stop()

    reg = fg["regime"]
    c1, c2, c3 = st.columns(3)
    c1.metric("VIX", f"{fg['vix']:.2f}")
    c2.metric("Indice Fear & Greed (composite)", f"{fg['index']}/100", fg["label"])
    c3.metric("Biais Nasdaq suggéré", reg["nq_bias"])

    # Jauge
    gauge = go.Figure(go.Indicator(
        mode="gauge+number", value=fg["index"],
        title={"text": f"Psychologie : {fg['label']}"},
        gauge={"axis": {"range": [0, 100]},
               "bar": {"color": reg["color"]},
               "steps": [{"range": [0, 25], "color": "#4a1414"},
                         {"range": [25, 45], "color": "#4a3214"},
                         {"range": [45, 55], "color": "#333"},
                         {"range": [55, 75], "color": "#1e3a1e"},
                         {"range": [75, 100], "color": "#144a14"}]}))
    gauge.update_layout(template="plotly_dark", height=300, margin=dict(l=30, r=30, t=60, b=10))
    st.plotly_chart(gauge, use_container_width=True)

    st.markdown(f"**Régime : {reg['regime']}** — {reg['desc']}")

    if not vix_df.empty:
        fig = go.Figure(go.Scatter(x=vix_df.index, y=vix_df["Close"],
                                   line=dict(color="#ff9800", width=2)))
        for lvl, txt in [(13, "Complaisance"), (17, "Calme"), (25, "Nervosité"), (35, "Peur")]:
            fig.add_hline(y=lvl, line_dash="dot", line_color="#555",
                          annotation_text=txt, annotation_font_size=9)
        fig.update_layout(title="VIX — 1 an", template="plotly_dark", height=350,
                          margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

# ═════════════════════ PAGE : CORRÉLATIONS ═════════════════════
elif page == "🔗 Corrélations live":
    st.title("🔗 Corrélations live — 14 actifs & indices")
    st.caption("Corrélations de Pearson calculées sur les **rendements** (données yfinance, "
               "rafraîchies toutes les 15 min). Nasdaq, S&P, Dow, CAC 40, DAX, MSCI World, "
               "Or, Argent, Pétrole, VIX, Taux 10 ans, Dollar Index, EUR/USD, Bitcoin.")

    period_key = st.selectbox("Période de calcul", list(cor.PERIODS.keys()), index=1)
    closes = cor.load_closes(period_key)

    if closes.empty or len(closes.columns) < 4:
        st.error("Données insuffisantes (yfinance indisponible ou marchés fermés). Réessaie dans quelques minutes.")
        st.stop()

    corr = cor.correlation_matrix(closes)
    if corr.empty:
        st.error("Pas assez d'historique sur cette période pour calculer les corrélations.")
        st.stop()

    # Régime de marché déduit des corrélations
    reg = cor.regime_signal(corr)
    st.metric("Régime détecté", reg["regime"])
    st.caption(reg["desc"])

    # Heatmap
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=corr.columns, y=corr.index,
        zmin=-1, zmax=1, colorscale="RdBu", reversescale=False,
        text=corr.values, texttemplate="%{text:.2f}",
        textfont=dict(size=9), colorbar=dict(title="Corr")))
    fig.update_layout(template="plotly_dark", height=620,
                      margin=dict(l=10, r=10, t=30, b=10),
                      xaxis=dict(tickangle=-40))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("🔵 proche de +1 : les actifs bougent ensemble · 🔴 proche de -1 : ils bougent en sens opposé · "
               "proche de 0 : indépendants.")

    # Lecture des paires critiques pour un trader NQ
    st.subheader("Paires critiques (lecture trader NQ)")
    for p in cor.key_pairs_summary(corr):
        v = p["corr"]
        badge = "🔵" if v > 0.4 else ("🔴" if v < -0.4 else "⚪")
        with st.container(border=True):
            st.markdown(f"{badge} **{p['paire']} : {v:+.2f}** — {p['note']}")

    # Corrélation glissante d'une paire au choix
    st.subheader("Corrélation glissante (fenêtre 20 barres)")
    c1, c2 = st.columns(2)
    assets = list(closes.columns)
    a = c1.selectbox("Actif A", assets, index=assets.index("Nasdaq 100") if "Nasdaq 100" in assets else 0)
    b = c2.selectbox("Actif B", assets, index=assets.index("VIX") if "VIX" in assets else 1)
    roll = cor.rolling_correlation(closes, a, b)
    if not roll.empty:
        figr = go.Figure(go.Scatter(x=roll.index, y=roll.values,
                                    line=dict(color="#26a69a", width=2)))
        figr.add_hline(y=0, line_dash="dot", line_color="#777")
        figr.add_hline(y=0.5, line_dash="dot", line_color="#2e7d32")
        figr.add_hline(y=-0.5, line_dash="dot", line_color="#c62828")
        figr.update_layout(title=f"{a} ↔ {b} — corrélation glissante",
                           template="plotly_dark", height=320,
                           yaxis=dict(range=[-1, 1]),
                           margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(figr, use_container_width=True)
        st.caption("Une corrélation qui **change de régime** (ex. NQ/VIX qui remonte vers 0) est souvent "
                   "un signal avancé de changement de comportement du marché.")

    with st.expander("📥 Exporter la matrice (CSV)"):
        st.download_button("Télécharger", corr.to_csv(), "correlations.csv", "text/csv")

# ═════════════════════ PAGE : ÉVÉNEMENTS ═════════════════════
elif page == "🌍 Événements du jour":
    st.title("🌍 Annonces macro, géopolitiques & événements naturels")
    st.caption("Sources : flux RSS publics (CNBC, MarketWatch, Investing, Yahoo). "
               "Impact estimé par mots-clés — vérifie toujours le calendrier économique officiel (ForexFactory).")

    if st.button("📰 Charger les événements du jour et calculer leur impact", type="primary"):
        with st.spinner("Récupération des flux…"):
            events = ne.fetch_events()
        if not events:
            st.warning("Aucun événement récupéré (flux indisponibles ou journée calme).")
        else:
            imp = ne.market_impact_summary(events)
            if imp:
                m1, m2, m3 = st.columns(3)
                m1.metric("Effet net Nasdaq", imp["nq_txt"], f"score {imp['nq_net']:+d}")
                m2.metric("Effet net Or", imp["gold_txt"], f"score {imp['gold_net']:+d}")
                m3.metric("Annonces fort impact", imp["high_impact"])
                if imp["warning"]:
                    st.error("⚠️ Plusieurs annonces majeures aujourd'hui — volatilité attendue élevée.")
            impact_badge = {3: "🔴 FORT", 2: "🟠 MOYEN", 1: "🟡 FAIBLE"}
            for e in events:
                with st.container(border=True):
                    st.markdown(f"**{impact_badge[e['impact']]}** · {e['categories']} · *{e['source']}* · {e['heure']}")
                    st.markdown(f"**[{e['titre']}]({e['lien']})**")
                    if e["resume"]:
                        st.caption(e["resume"])
                    st.markdown(f"Impact estimé → Nasdaq : **{e['effet_nq']}** · Or : **{e['effet_or']}**")

# ═════════════════════ PAGE : MACHINE LEARNING ═════════════════════
elif page == "🤖 Machine Learning":
    st.title(f"🤖 Prédiction ML — {instrument}")
    st.caption("Random Forest entraîné sur les features techniques + signaux ICT/MMM, "
               "validé en walk-forward (TimeSeriesSplit). La précision affichée est hors-échantillon.")

    tf_ml = st.selectbox("Timeframe de prédiction", ["1D", "60m", "15m"])
    if st.button("🚀 Entraîner et prédire", type="primary"):
        df = dl.load_ohlc(ticker, tf_ml)
        if df.empty or len(df) < 150:
            st.error("Pas assez d'historique pour ce timeframe.")
        else:
            with st.spinner("Entraînement du modèle…"):
                res = ml.train_predict(df)
            if res is None:
                st.error("Échantillon insuffisant après construction des features.")
            else:
                c1, c2, c3, c4 = st.columns(4)
                emoji = "🟢" if res["direction"] == "HAUSSE" else "🔴"
                c1.metric("Prochaine bougie", f"{emoji} {res['direction']}")
                c2.metric("Probabilité hausse", f"{res['proba_up']}%")
                c3.metric("Précision walk-forward", f"{res['cv_accuracy']}%", f"± {res['cv_std']}%")
                c4.metric("Échantillons", res["n_samples"])

                if res["cv_accuracy"] < 53:
                    st.warning("⚠️ Précision proche du hasard (50%) : ne trade pas ce signal seul. "
                               "Il ne vaut que combiné à la confluence ICT et au contexte macro.")

                st.subheader("Features les plus importantes")
                imp_df = res["importances"].reset_index()
                imp_df.columns = ["Feature", "Importance"]
                fig = go.Figure(go.Bar(x=imp_df["Importance"], y=imp_df["Feature"],
                                       orientation="h", marker_color="#26a69a"))
                fig.update_layout(template="plotly_dark", height=350,
                                  yaxis=dict(autorange="reversed"),
                                  margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

# ═════════════════════ PAGE : MÉMOIRE ═════════════════════
elif page == "🧠 Mémoire des patterns":
    st.title("🧠 Mémoire des patterns de marché")
    st.caption("Chaque contexte enregistré depuis le Dashboard est stocké dans data/patterns_memory.csv. "
               "La plateforme met à jour les résultats réels et calcule des probabilités conditionnelles "
               "à partir des contextes similaires passés.")

    mem = pm.get_memory()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Mettre à jour les résultats réels"):
            prices = {}
            for name, tk in dl.SYMBOLS.items():
                df = dl.load_ohlc(tk, "1D")
                if not df.empty:
                    prices[name] = float(df["Close"].iloc[-1])
            mem = pm.update_outcomes(prices)
            st.success("Résultats mis à jour ✅")
    with c2:
        if not mem.empty:
            st.download_button("⬇️ Exporter la mémoire (CSV)", mem.to_csv(index=False),
                               "patterns_memory.csv", "text/csv")

    if mem.empty:
        st.info("Mémoire vide. Va sur le Dashboard et clique « Enregistrer ce contexte » pour commencer "
                "à construire l'historique.")
    else:
        st.dataframe(mem.iloc[::-1], use_container_width=True, height=300)

        done = mem[mem["resultat_reel"].isin(["HAUSSE", "BAISSE"])]
        if len(done) >= 3:
            st.subheader("Fiabilité des prédictions passées")
            correct = (done["direction_predite"].map({"LONG": "HAUSSE", "SHORT": "BAISSE"})
                       == done["resultat_reel"]).mean() * 100
            st.metric("Taux de bonne direction (ICT)", f"{correct:.0f}%",
                      f"sur {len(done)} contextes résolus")

            tfs2, analyses2, mmm2, _ = full_analysis(ticker)
            a = analyses2.get("15m") or analyses2.get("1D")
            m = mmm2.get("15m")
            if a:
                sim = pm.similar_context_stats(instrument, a["bias"],
                                               m["last_state"] if m else "?", "")
                if sim:
                    st.subheader(f"Contexte actuel similaire à {sim['n']} situations passées")
                    st.metric("Probabilité historique de hausse", f"{sim['prob_hausse']}%")
        else:
            st.caption("Enregistre au moins quelques contextes et mets à jour les résultats "
                       "pour débloquer les statistiques conditionnelles.")

st.sidebar.divider()
st.sidebar.caption("⚠️ Outil éducatif et d'aide à la décision. Les probabilités sont des estimations "
                   "statistiques, pas des garanties. Ceci n'est pas un conseil financier.")
