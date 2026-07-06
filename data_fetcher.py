# 📈 ETFCore — Plateforme d'investissement ETF

Plateforme Streamlit inspirée de la feuille *Gestion_Portefeuille* : indices mondiaux, constructeur de portefeuilles avec allocations (Actions / ETFs / Bonds), transactions, et suivi de performance.

## 🔌 Sources de prix
1. **Google Finance** (prioritaire) — scraping de `google.com/finance/quote/BOURSE:TICKER`
2. **Yahoo Finance** (fallback automatique via `yfinance`) — utilisé quand Google échoue, et pour tous les historiques de prix (Google n'expose pas d'historique)

Chaque prix affiché indique sa source.

## 🗂️ Persistance CSV (dossier `data/`, créé automatiquement)
| Fichier | Contenu |
|---|---|
| `assets.csv` | Univers d'actifs (46 pré-chargés depuis ta feuille : HACK, CIBR, SMH, ARKF, NVDA, AGG…) |
| `portfolios.csv` | Portefeuilles (capital, devise, allocations cibles) |
| `transactions.csv` | Chaque achat/vente (date, prix, source du prix) |
| `performance_history.csv` | Snapshots de valorisation pour suivre la perf dans le temps |

## 🚀 Lancement local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## ☁️ Déploiement Streamlit Cloud
Structure **plate** (pas de sous-dossiers de modules → pas de `ModuleNotFoundError`) :
```
repo/
├── app.py
├── data_fetcher.py
├── storage.py
├── requirements.txt
└── README.md
```
1. Crée le repo GitHub et uploade **les 4 fichiers à la racine** (le dossier `data/` se crée tout seul au premier lancement).
2. Streamlit Cloud → New app → main file : `app.py`.

⚠️ **Important sur Streamlit Cloud** : le disque est éphémère (les CSV sont perdus au redémarrage). Utilise le bouton *⬇️ Télécharger les CSV* de l'onglet 🗂️ régulièrement, ou pousse le dossier `data/` sur GitHub pour recharger tes données.

## 📄 Pages
- **🏠 Accueil** — indices clés, catégories d'investissement (donut + barres sectorielles), explorateur interactif avec graphique 12 mois, synthèse des portefeuilles
- **🌍 Indices mondiaux** — USA / Europe / Asie / VIX (mêmes indices que ta feuille) + comparaison base 100
- **💼 Mes portefeuilles** — création avec sliders d'allocation (défaut 15/65/20), stratégie visée vs actuelle, répartition sectorielle, positions valorisées en temps réel
- **🛒 Transactions** — achat/vente avec prix Google→Yahoo pré-rempli, historique
- **📊 Performance** — courbes de valeur et de perf % à partir des snapshots
- **🗂️ Actifs & données** — ajout/suppression d'actifs, export des 4 CSV
