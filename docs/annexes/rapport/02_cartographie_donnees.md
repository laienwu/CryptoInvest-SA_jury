# Cartographie des Donnees (C2)

> Topographie exhaustive des donnees du projet : inventaire des sources, semantique metier,
> modeles de donnees, traitements et flux, mise a disposition et acces.

---

## 1. Inventaire des sources

Le projet exploite **6 types de sources** heterogenes pour satisfaire la competence C8
(automatiser l'extraction depuis API, scraping, fichier, BDD, big data).

### 1.1 Source 1 : API REST Binance (donnees crypto)

| Attribut | Valeur |
|----------|--------|
| **Type** | API REST publique |
| **URL** | `https://api.binance.com/api/v3/klines` |
| **Authentification** | Aucune (donnees publiques) |
| **Rate limit** | 1 200 requetes/minute (poids variable par endpoint) |
| **Format reponse** | JSON (tableaux de tableaux) |
| **Frequence** | Quotidienne (batch) + temps reel (streaming WebSocket) |
| **Module** | `src/pipeline/ingest.py` |
| **Volume** | 51 symboles x 30 jours = ~1 530 enregistrements/lot |

**Endpoints utilises :**

| Endpoint | Description | Frequence |
|----------|-------------|-----------|
| `/api/v3/klines` | Donnees OHLCV (candlesticks) | Quotidien (batch) |
| `/api/v3/ticker/price` | Prix actuel | Temps reel (live ticker) |
| `/api/v3/exchangeInfo` | Metadonnees symboles | Statique |

**Streaming WebSocket :**

| Flux | URL | Description |
|------|-----|-------------|
| Klines | `wss://stream.binance.com:9443/ws/{symbol}@kline_1d` | Bougies en temps reel |
| Order Book | `wss://stream.binance.com:9443/ws/{symbol}@depth20@100ms` | Carnet d'ordres (top 20 niveaux) |

### 1.2 Source 2 : Yahoo Finance / yfinance (actifs traditionnels)

| Attribut | Valeur |
|----------|--------|
| **Type** | Bibliotheque Python (API Yahoo Finance) |
| **Authentification** | Aucune (donnees publiques) |
| **Rate limit** | Non documente, throttling interne |
| **Format reponse** | DataFrame pandas (converti en dict en interne, ADR-003) |
| **Frequence** | Quotidienne |
| **Module** | `src/pipeline/ingest_yfinance.py` |
| **Volume** | 33 symboles x 30 jours = ~990 enregistrements/lot |

**Categories d'actifs :**

| Categorie | Exemples | Nombre |
|-----------|----------|--------|
| US Broad Market | SPY, QQQ, IWM, DIA | 4 |
| International | EFA, VGK, EEM | 3 |
| Obligations | TLT, BND, HYG | 3 |
| Matieres premieres | GLD, SLV, USO | 3 |
| Secteurs US | XLF, XLE, XLK, XLV | 4 |
| Mega caps US | AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA | 7 |
| Finance | JPM, V, GS | 3 |
| Sante / Consommation | JNJ, PG, KO | 3 |
| Europe | ASML.AS, MC.PA, SAP | 3 |
| **Total** | | **33** |

### 1.3 Source 3 : Fichier CSV (metadonnees symboles)

| Attribut | Valeur |
|----------|--------|
| **Type** | Fichier structure (CSV) |
| **Localisation** | `data/reference/symbols_metadata.csv` |
| **Authentification** | Systeme de fichiers (permissions OS) |
| **Format** | CSV avec en-tete |
| **Frequence** | Statique (reference) |
| **Module** | `src/pipeline/ingest_sources.py` (CSVSource) |

**Colonnes :** `symbol`, `name`, `sector`, `category`, `launch_year`, `market_cap_rank`, `is_stablecoin`, `consensus`

### 1.4 Source 4 : Fichier JSON (configuration portefeuille)

| Attribut | Valeur |
|----------|--------|
| **Type** | Fichier semi-structure (JSON) |
| **Localisation** | `data/reference/portfolio_config.json` |
| **Authentification** | Systeme de fichiers |
| **Format** | JSON |
| **Frequence** | Statique (reference) |
| **Module** | `src/pipeline/ingest_sources.py` (JSONSource) |

**Contenu :** contraintes d'investissement, parametres de risque, classification sectorielle, benchmarks.

### 1.5 Source 5 : Web Scraping CoinGecko (classements marche)

| Attribut | Valeur |
|----------|--------|
| **Type** | Scraping web (HTML parsing) |
| **URL** | `https://www.coingecko.com/` |
| **Authentification** | Aucune |
| **Rate limit** | Politesse : 1 requete/seconde |
| **Format** | HTML (parse vers dict Python) |
| **Frequence** | A la demande |
| **Module** | `src/pipeline/ingest_scraping.py` (ScrapingSource) |
| **Fallback** | Donnees statiques si le site est indisponible |

### 1.6 Source 6 : PostgreSQL (benchmarks historiques)

| Attribut | Valeur |
|----------|--------|
| **Type** | Base de donnees relationnelle |
| **Connexion** | `postgresql://portfolio:***@localhost:5433/portfolio_benchmarks` |
| **Authentification** | Login/mot de passe (variable d'environnement) |
| **Format** | Tuples SQL |
| **Frequence** | A la demande |
| **Module** | `src/pipeline/ingest_postgres.py` (PostgresSource) |
| **Fallback** | Donnees statiques si PostgreSQL est indisponible |

### 1.7 Synthese des sources

| # | Source | Type C8 | Format | Auth | Frequence | Volume/lot |
|---|--------|---------|--------|------|-----------|------------|
| 1 | Binance API | API REST | JSON | Non | Quotidien | ~1 530 records |
| 2 | yfinance | Bibliotheque/API | DataFrame→dict | Non | Quotidien | ~990 records |
| 3 | CSV | Fichier structure | CSV | OS | Statique | ~51 lignes |
| 4 | JSON | Fichier semi-structure | JSON | OS | Statique | 1 fichier |
| 5 | CoinGecko | Scraping web | HTML | Non | A la demande | ~20 records |
| 6 | PostgreSQL | BDD relationnelle | SQL | Oui | A la demande | ~3 indices |

---

## 2. Glossaire metier (Semantique)

### 2.1 Termes communs (crypto et traditionnel)

| Terme | Definition |
|-------|------------|
| **OHLCV** | Open, High, Low, Close, Volume — donnees de chandelier japonais |
| **Kline** | Chandelier japonais sur une periode donnee (synonyme de candlestick) |
| **Interval** | Periode du chandelier (1d = journalier, 1h = horaire) |
| **Rendement** | Variation relative du prix entre deux periodes : `(P_t - P_{t-1}) / P_{t-1}` |
| **Volatilite** | Ecart-type annualise des rendements (risque) |
| **Correlation** | Mesure de co-mouvement entre deux actifs [-1, 1] |
| **Covariance** | Mesure de variance conjointe entre deux actifs |
| **Sharpe Ratio** | Rendement excedentaire ajuste au risque : `(R - Rf) / sigma` |
| **Sortino Ratio** | Sharpe ajuste avec uniquement le risque baissier (downside deviation) |
| **Max Drawdown** | Perte maximale depuis un pic precedent |
| **VaR** | Value at Risk — perte maximale avec un niveau de confiance donne |
| **CVaR** | Conditional VaR — perte moyenne au-dela du VaR (expected shortfall) |

### 2.2 Termes specifiques crypto

| Terme | Definition |
|-------|------------|
| **Symbol** | Paire de trading (ex: BTCUSDT = Bitcoin vs Tether) |
| **Quote asset** | Monnaie de cotation (USDT dans BTCUSDT) |
| **Base asset** | Actif echange (BTC dans BTCUSDT) |
| **Order Book** | Carnet d'ordres — listes des offres d'achat (bids) et de vente (asks) |
| **Spread** | Ecart entre le meilleur bid et le meilleur ask |
| **Market Cap Rank** | Classement par capitalisation boursiere |

### 2.3 Termes specifiques actifs traditionnels

| Terme | Definition |
|-------|------------|
| **ETF** | Exchange-Traded Fund — fonds negociable en bourse replicant un indice |
| **Ticker** | Identifiant boursier (ex: SPY, AAPL, MC.PA) |
| **Benchmark** | Indice de reference pour mesurer la performance (ex: S&P 500) |
| **Alpha** | Surperformance par rapport au benchmark ajustee du risque (CAPM) |
| **Beta** | Sensibilite de l'actif aux mouvements du marche |
| **Secteur** | Classification economique (Technologie, Sante, Finance, etc.) |
| **Jours de trading** | 365/an pour crypto, 252/an pour actifs traditionnels |

### 2.4 Termes d'optimisation de portefeuille

| Terme | Definition |
|-------|------------|
| **Markowitz** | Optimisation moyenne-variance (frontiere efficiente) |
| **Risk Parity** | Allocation a contribution de risque egale |
| **HRP** | Hierarchical Risk Parity — allocation basee sur le clustering |
| **Black-Litterman** | Optimisation bayesienne integrant des vues de l'investisseur |
| **Frontiere efficiente** | Ensemble des portefeuilles optimaux risque/rendement |
| **Poids (weights)** | Proportion du capital allouee a chaque actif |

---

## 3. Modeles de donnees

### 3.1 Donnees brutes — Zone Bronze (`data/raw/`)

**3.1.1 Klines crypto** : `data/raw/klines/{SYMBOL}.parquet`

| Colonne | Type | Nullable | Description |
|---------|------|----------|-------------|
| timestamp | STRING | Non | Date ISO 8601 (YYYY-MM-DD) |
| open | FLOAT64 | Non | Prix d'ouverture |
| high | FLOAT64 | Non | Prix le plus haut de la periode |
| low | FLOAT64 | Non | Prix le plus bas de la periode |
| close | FLOAT64 | Non | Prix de cloture |
| volume | FLOAT64 | Non | Volume echange (quote asset) |

Fichiers : 51 fichiers Parquet (un par symbole crypto), ~30 records chacun.

**3.1.2 Klines traditionnels** : `data/raw/trad/{SYMBOL}.parquet`

Schema identique aux klines crypto. 33 fichiers Parquet (un par symbole trad), ~30 records chacun.

**3.1.3 Streaming klines** : `data/streaming/klines/{SYMBOL}.parquet`

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Symbole de la paire |
| timestamp | STRING | Date ISO 8601 |
| open | FLOAT64 | Prix d'ouverture |
| high | FLOAT64 | Prix le plus haut |
| low | FLOAT64 | Prix le plus bas |
| close | FLOAT64 | Prix de cloture |
| volume | FLOAT64 | Volume echange |
| event_time | STRING | Horodatage de reception ISO 8601 |

**3.1.4 Streaming order book** : `data/streaming/orderbook/{SYMBOL}.parquet`

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Symbole de la paire |
| timestamp | STRING | Horodatage ISO 8601 |
| best_bid | FLOAT64 | Meilleur prix d'achat |
| best_ask | FLOAT64 | Meilleur prix de vente |
| spread | FLOAT64 | Ecart bid-ask |
| spread_bps | FLOAT64 | Spread en points de base |
| bid_depth | FLOAT64 | Profondeur totale des achats (top 20) |
| ask_depth | FLOAT64 | Profondeur totale des ventes (top 20) |
| imbalance | FLOAT64 | Desequilibre offre/demande |
| levels | INT | Nombre de niveaux |

### 3.2 Donnees transformees — Zone Silver (`data/processed/`)

**returns.parquet** : rendements journaliers par symbole

| Colonne | Type | Description |
|---------|------|-------------|
| date | STRING | Date du rendement |
| symbol | STRING | Symbole |
| value | FLOAT64 | Rendement journalier |

**volatility.parquet** : volatilite annualisee

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Symbole |
| value | FLOAT64 | `std(returns) x sqrt(trading_days)` |

**mean_returns.parquet** : rendement moyen annualise

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Symbole |
| value | FLOAT64 | `mean(returns) x trading_days` |

**correlation.parquet** / **covariance.parquet** : matrices symetriques

| Colonne | Type | Description |
|---------|------|-------------|
| symbol_row | STRING | Symbole ligne |
| symbol_col | STRING | Symbole colonne |
| value | FLOAT64 | Coefficient (correlation ou covariance) |

Note : les memes datasets existent en version `_trad` pour les actifs traditionnels
(ex: `returns_trad.parquet`, `volatility_trad.parquet`).

### 3.3 Donnees agregees — Zone Gold (`data/output/`)

**weights.json** : allocation optimale du portefeuille

```json
{
  "_metadata": {"saved_at": "2025-01-15T10:30:00"},
  "symbols": ["BTCUSDT", "ETHUSDT", "..."],
  "weights": {"BTCUSDT": 0.35, "ETHUSDT": 0.25},
  "expected_return": 0.15,
  "volatility": 0.28,
  "sharpe_ratio": 0.54
}
```

**frontier.json** : frontiere efficiente (50 points)

```json
{
  "frontier": [{"volatility": 0.18, "return": 0.12, "weights": [0.6, 0.3, 0.1]}],
  "max_sharpe": {"volatility": 0.28, "return": 0.18, "weights": ["..."]},
  "min_variance": {"volatility": 0.15, "return": 0.10, "weights": ["..."]},
  "assets": [{"symbol_index": 0, "volatility": 0.45, "return": 0.15}],
  "capital_market_line": {"x": [0.0, 0.5], "y": [0.05, 0.35]},
  "risk_free_rate": 0.05,
  "symbols": ["BTCUSDT", "ETHUSDT", "..."]
}
```

**backtest.json** : resultats du backtesting walk-forward

```json
{
  "windows": [
    {
      "window_id": 0,
      "train_start": "2025-01-01", "train_end": "2025-03-01",
      "test_start": "2025-03-02", "test_end": "2025-04-01",
      "weights": {"BTCUSDT": 0.4, "ETHUSDT": 0.35},
      "test_return": 0.0512
    }
  ],
  "cumulative_values": {"dates": [], "strategy": [], "equal_weight": [], "btc_only": []},
  "metrics": {
    "strategy": {"cumulative_return": 0.25, "annualized_return": 0.35,
                  "max_drawdown": 0.12, "sharpe_ratio": 1.85, "calmar_ratio": 2.92}
  },
  "config": {"train_window": 60, "test_window": 30, "strategy": "max_sharpe"}
}
```

Note : les equivalents traditionnels existent (`weights_trad.json`, `frontier_trad.json`, `backtest_trad.json`).

---

## 4. Modele dimensionnel (Star Schema)

Le Data Warehouse utilise un schema en etoile implemente dans **DuckDB** via des vues SQL
gerees par **dbt-duckdb** (ADR-007). Les modeles dbt se trouvent dans `dbt_project/models/marts/`.

### 4.1 Table de faits : `fact_prices`

Source dbt : `dbt_project/models/marts/fact_prices.sql`

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | FK vers dim_symbol |
| timestamp | DATE | FK vers dim_date |
| open_price | FLOAT64 | Prix d'ouverture |
| high_price | FLOAT64 | Prix le plus haut |
| low_price | FLOAT64 | Prix le plus bas |
| close_price | FLOAT64 | Prix de cloture |
| volume | FLOAT64 | Volume echange |

Deduplication : `ROW_NUMBER() OVER (PARTITION BY symbol, timestamp)` pour eliminer les doublons.

### 4.2 Table de dimension : `dim_symbol`

Source dbt : `dbt_project/models/marts/dim_symbol.sql`

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Identifiant unique |
| first_date | DATE | Premiere date disponible |
| last_date | DATE | Derniere date disponible |
| record_count | INT | Nombre total de records |
| asset_class | STRING | `crypto` ou `traditional` (derive du suffixe USDT) |

### 4.3 Table de dimension : `dim_date`

Source dbt : `dbt_project/models/marts/dim_date.sql`

| Colonne | Type | Description |
|---------|------|-------------|
| date_key | DATE | Cle primaire |
| year | INT | Annee |
| month | INT | Mois |
| day | INT | Jour |
| day_of_week | INT | Jour de la semaine (0=dimanche) |
| is_weekend | BOOLEAN | Vrai si samedi ou dimanche |

Date spine generee via `generate_series(min_date, max_date, INTERVAL '1 day')`.

### 4.4 Tables d'agregation dbt

| Modele | Description |
|--------|-------------|
| `agg_daily_returns.sql` | Rendements logarithmiques journaliers |
| `portfolio_summary.sql` | Metriques resume du portefeuille |

### 4.5 Schema visuel

```
                    ┌──────────────────┐
                    │   dim_symbol     │
                    ├──────────────────┤
                    │ symbol (PK)      │
                    │ first_date       │
                    │ last_date        │
                    │ record_count     │
                    │ asset_class      │
                    └────────┬─────────┘
                             │
┌──────────────────┐  ┌──────┴───────────┐
│   dim_date       │  │   fact_prices    │
├──────────────────┤  ├──────────────────┤
│ date_key (PK)    │◄─┤ symbol (FK)      │
│ year             │  │ timestamp (FK)   │
│ month            │  │ open_price       │
│ day              │  │ high_price       │
│ day_of_week      │  │ low_price        │
│ is_weekend       │  │ close_price      │
└──────────────────┘  │ volume           │
                      └──────────────────┘
```

---

## 5. Flux de donnees (Traitements)

### 5.1 Pipeline batch crypto

```
[Binance API]  ──────────────────────────────────────────────────────────────
      │ ingest.py (51 symboles, REST /klines)
      ▼
[data/raw/klines/]  ─── BRONZE ─────────────────────────────────────────────
      │ transform.py (rendements, volatilite, correlation, covariance)
      ▼
[data/processed/]  ─── SILVER ──────────────────────────────────────────────
      │ optimize.py (Markowitz max-Sharpe, frontiere efficiente)
      │ backtest.py (walk-forward 60j train / 30j test)
      ▼
[data/output/]  ─── GOLD ──────────────────────────────────────────────────
      │
      ▼
[FastAPI / Streamlit / DuckDB]  ─── EXPOSITION ─────────────────────────────
```

### 5.2 Pipeline batch actifs traditionnels

```
[Yahoo Finance]  ───────────────────────────────────────────────────────────
      │ ingest_yfinance.py (33 symboles, yfinance Ticker.history)
      ▼
[data/raw/trad/]  ─── BRONZE ───────────────────────────────────────────────
      │ transform.py (transform_yfinance_data)
      ▼
[data/processed/*_trad.parquet]  ─── SILVER ─────────────────────────────────
      │ optimize.py (optimize_yfinance_portfolio, frontier_trad)
      │ backtest.py (run_yfinance_backtest)
      ▼
[data/output/*_trad.json]  ─── GOLD ────────────────────────────────────────
      │
      ▼
[FastAPI /portfolio/trad/*]  ─── EXPOSITION ─────────────────────────────────
```

### 5.3 Pipeline streaming (temps reel)

```
[Binance WebSocket]  ───────────────────────────────────────────────────────
      │ stream_producer.py (klines + order book depth)
      ▼
[Kafka / Redpanda]  ── topics: klines-raw, orderbook-raw ───────────────────
      │ stream_consumer.py (micro-batch, deduplication)
      ▼
[data/streaming/klines/]    ─── BRONZE (streaming) ──────────────────────────
[data/streaming/orderbook/] ─── BRONZE (streaming) ──────────────────────────
```

### 5.4 Pipeline dbt (transformations SQL)

```
[data/raw/klines/*.parquet]  ─── sources Parquet ────────────────────────────
      │ dbt run (dbt-duckdb)
      ▼
[stg_klines, stg_symbols]  ─── staging ──────────────────────────────────────
      │
      ▼
[fact_prices, dim_symbol, dim_date]  ─── marts (star schema) ─────────────────
[agg_daily_returns, portfolio_summary]  ─── agregations ──────────────────────
      │
      ▼
[data/warehouse.duckdb]  ─── DWH materialise ────────────────────────────────
```

### 5.5 Matrice des flux

| Source | Destination | Frequence | Volume estime            | Format |
|--------|-------------|-----------|--------------------------|--------|
| Binance API | data/raw/klines/ | Quotidien | 51 x 30 = ~1 530 records | Parquet |
| Yahoo Finance | data/raw/trad/ | Quotidien | 33 x 30 = ~990 records   | Parquet |
| CoinGecko | memoire (enrichment) | A la demande | ~20 records              | dict |
| CSV reference | memoire (enrichment) | Statique | ~51 lignes               | CSV |
| JSON reference | memoire (config) | Statique | 1 fichier                | JSON |
| PostgreSQL | memoire (benchmarks) | A la demande | ~3 indices               | SQL |
| data/raw/ | data/processed/ | Post-ingest | ~7 fichiers Silver       | Parquet |
| data/processed/ | data/output/ | Post-transform | ~10 fichiers Gold        | JSON |
| data/raw/ | warehouse.duckdb | dbt run | Star schema complet      | DuckDB |
| Binance WS | Kafka → data/streaming/ | Temps reel | Variable (continu)       | Parquet |
| data/ | API REST :8000 | On-demand | Variable                 | JSON |
| data/ | Dashboard :8501 | On-demand | Variable                 | Plotly |

### 5.6 Orchestration

| Orchestrateur | Role | Fichier |
|---------------|------|---------|
| **Airflow** | Orchestrateur principal (toutes les executions planifiees/repetees) | `dags/portfolio_dag.py` |
| **docker-compose pipeline** | Bootstrap uniquement (chargement initial complet) | `docker-compose.yml` |

Regle : Airflow est le seul orchestrateur pour les executions programmees. Le service
`pipeline` dans docker-compose sert uniquement au chargement initial et/ou trigger d'un besoin custom.

---

## 6. Acces et autorisations (Mise a disposition)

### 6.1 Methodes d'acces aux donnees

| Methode | Protocole | Port | Authentification | Consommateurs |
|---------|-----------|------|------------------|---------------|
| Fichiers Parquet | Systeme de fichiers | N/A | Permissions OS | Pipeline, scripts |
| DuckDB SQL | In-process | N/A | Aucune | dbt, scripts analytiques |
| API REST (FastAPI) | HTTP/JSON | 8000 | Aucune (MVP) | Applications, dashboard |
| Dashboard (Streamlit) | HTTP | 8501 | Aucune | Utilisateurs finaux |
| Airflow Web UI | HTTP | 8081 | Login basique | Administrateurs |
| Redpanda Console | HTTP | 8080 | Aucune | Administrateurs |
| Prometheus | HTTP | 9090 | Aucune | Monitoring |
| Grafana | HTTP | 3000 | Login | Monitoring |
| Delta Lake | Fichiers Delta | N/A | Permissions OS | Pipeline avance |
| MinIO (S3) | HTTP/S3 API | 9000 | Access key/Secret key | Stockage objet |

### 6.2 Matrice des roles

| Role | Bronze | Silver | Gold | API | Dashboard | Airflow |
|------|--------|--------|------|-----|-----------|---------|
| Data Engineer | RW | RW | RW | RW | RW | Admin |
| Analyste | R | R | R | R | R | Viewer |
| Application | - | - | R | R | - | - |

---

## 7. Qualite des donnees

### 7.1 Controles implementes

Le module `src/pipeline/validation.py` implemente un framework de validation a trois niveaux :
**Stockage séparé par tier de donnée avec autorisation ad-hoc par AD group user**

| Zone | Controle | Description |
|------|----------|-------------|
| Bronze | Schema OHLCV | 6 colonnes requises, aucune nullable |
| Bronze | Prix positifs | `open, high, low, close, volume > 0` |
| Bronze | Coherence OHLC | `low <= open, close <= high` |
| Bronze | Records minimum | Au moins 2 records par symbole |
| Silver | Rendements bornes | Rendements dans une plage raisonnable |
| Silver | Volatilite positive | `volatilite > 0` |
| Silver | Matrices symetriques | `correlation[i,j] == correlation[j,i]` |
| Gold | Somme des poids | `sum(weights) == 1.0` (tolerance 1e-6) |
| Gold | Poids dans [0,1] | Pas de positions negatives |
| Gold | 3 strategies backtest | Presence des 3 benchmarks |

### 7.2 Metriques de qualite

| Metrique | Cible | Mesure |
|----------|-------|--------|
| Completude | 100% | Aucun champ null dans Bronze/Silver |
| Unicite | 100% | Deduplication dans fact_prices (dbt) |
| Fraicheur | < 24h | Monitore via Airflow + Prometheus |
| Coherence | 100% | Tests dbt (`assert_positive_volumes`) |

---

## 8. Donnees manquantes identifiees

| Donnee absente | Raison | Impact | Mitigation |
|----------------|--------|--------|------------|
| Market cap en temps reel | API CoinGecko rate-limited | Classement approximatif | Fallback vers donnees statiques |
| Donnees fondamentales crypto | Non disponibles publiquement | Pas d'analyse fondamentale | Focus sur l'analyse technique |
| Historique > 1 an (batch) | Limite API Binance sur `/klines` | Backtesting limite | Fenetre glissante 30 jours suffisante pour la demo |
| Donnees intraday (batch) | Choix de design (intervalle 1d) | Pas de trading haute frequence | Streaming disponible pour le temps reel |
| Frais de transaction reels | Variables selon le compte | Estimation dans le module `costs.py` | Modele configurable (0.1% par defaut) |
| Dividendes / coupons | Non integres dans le calcul de rendement trad | Rendement total sous-estime | `auto_adjust=True` dans yfinance |
| Donnees ESG | Non disponibles dans les sources utilisees | Pas de filtrage ESG | Hors scope du projet |

---