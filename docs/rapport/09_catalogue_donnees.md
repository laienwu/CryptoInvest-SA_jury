# Catalogue de Donnees (C20)

> Catalogue exhaustif de tous les datasets du Data Lake et du Data Warehouse.
> Recense les metadonnees techniques, schemas, lignage, cycle de vie, qualite et acces.

---

## 1. Vue d'ensemble du Data Lake

### 1.1 Architecture des zones

```
data/
├── raw/                    # BRONZE — Donnees brutes
│   ├── klines/             #   51 fichiers crypto (BTCUSDT.parquet, ...)
│   └── trad/               #   33 fichiers traditionnels (SPY.parquet, ...)
├── streaming/              # BRONZE — Donnees temps reel
│   ├── klines/             #   Klines via Kafka (micro-batch)
│   └── orderbook/          #   Carnet d'ordres via Kafka
├── processed/              # SILVER — Donnees transformees
│   ├── returns.parquet     #   Rendements crypto
│   ├── volatility.parquet
│   ├── mean_returns.parquet
│   ├── correlation.parquet
│   ├── covariance.parquet
│   ├── returns_trad.parquet     # Rendements trad
│   ├── volatility_trad.parquet
│   ├── mean_returns_trad.parquet
│   ├── correlation_trad.parquet
│   └── covariance_trad.parquet
├── output/                 # GOLD — Resultats metier
│   ├── weights.json        #   Allocation crypto
│   ├── frontier.json       #   Frontiere efficiente crypto
│   ├── backtest.json       #   Backtesting crypto
│   ├── weights_trad.json   #   Allocation trad
│   ├── frontier_trad.json  #   Frontiere efficiente trad
│   └── backtest_trad.json  #   Backtesting trad
├── reference/              # REFERENCE — Donnees statiques
│   ├── symbols_metadata.csv
│   └── portfolio_config.json
└── warehouse.duckdb        # DWH — Star schema (DuckDB)

dbt_project/target/         # DBT — Modeles compiles et materialises
```

### 1.2 Resume du catalogue

| Zone | Datasets | Format | Volume estime | Retention |
|------|----------|--------|---------------|-----------|
| Bronze crypto | 51 fichiers | Parquet | ~150 KB | 1 an |
| Bronze trad | 33 fichiers | Parquet | ~100 KB | 1 an |
| Bronze streaming | Variable | Parquet | ~50 KB/jour | 30 jours |
| Silver crypto | 5 fichiers | Parquet | ~20 KB | 1 an |
| Silver trad | 5 fichiers | Parquet | ~15 KB | 1 an |
| Gold crypto | 3 fichiers | JSON | ~5 KB | 30 jours |
| Gold trad | 3 fichiers | JSON | ~5 KB | 30 jours |
| Reference | 2 fichiers | CSV + JSON | ~5 KB | Permanent |
| DWH (DuckDB) | 6 tables/vues | DuckDB | ~500 KB | Permanent |
| dbt target | ~8 artefacts | SQL compile | ~50 KB | Regenere |

---

## 2. Catalogue detaille — Zone Bronze

### 2.1 Dataset : klines crypto — `raw.klines.{symbol}`

| Metadonnee | Valeur |
|------------|--------|
| **Identifiant** | `raw.klines.{symbol}` |
| **Localisation** | `data/raw/klines/{SYMBOL}.parquet` |
| **Format** | Apache Parquet (compression Snappy) |
| **Source** | Binance API `/api/v3/klines` |
| **Frequence alimentation** | Quotidienne (incremental via Airflow) |
| **Proprietaire** | Data Engineer |
| **Classification** | Public |

#### Schema

| Colonne | Type | Nullable | Description |
|---------|------|----------|-------------|
| timestamp | STRING | Non | Date ISO 8601 (YYYY-MM-DD) |
| open | FLOAT64 | Non | Prix d'ouverture |
| high | FLOAT64 | Non | Prix le plus haut |
| low | FLOAT64 | Non | Prix le plus bas |
| close | FLOAT64 | Non | Prix de cloture |
| volume | FLOAT64 | Non | Volume echange (quote asset) |

#### Fichiers (51 symboles crypto)

| Categorie | Symboles | Nombre |
|-----------|----------|--------|
| Top 10 | BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT, AVAXUSDT, DOTUSDT, LINKUSDT | 10 |
| Layer 1 / Infrastructure | ATOMUSDT, NEARUSDT, APTUSDT, SUIUSDT, INJUSDT, THETAUSDT, ALGOUSDT, VETUSDT, FTMUSDT, HBARUSDT | 10 |
| DeFi | AAVEUSDT, UNIUSDT, DYDXUSDT, SNXUSDT, MKRUSDT, COMPUSDT, SUSHIUSDT, CRVUSDT, LDOUSDT, PENDLEUSDT, ENSUSDT | 11 |
| Layer 2 / Scaling | MATICUSDT, ARBUSDT, OPUSDT | 3 |
| Legacy | LTCUSDT, TRXUSDT, ICPUSDT, FILUSDT | 4 |
| AI / Data | FETUSDT, RUNEUSDT, GRTUSDT, RENDERUSDT | 4 |
| Meme coins | SHIBUSDT, PEPEUSDT, FLOKIUSDT, BOMEUSDT | 4 |
| Gaming / Metaverse | SANDUSDT, MANAUSDT, AXSUSDT, GALAUSDT, IMXUSDT | 5 |

#### Metadonnees techniques

```yaml
dataset:
  id: raw.klines
  created_at: 2025-01-01
  updated_at: # Derniere execution ingest
  schema_version: 1.0
  row_count: ~1530 (51 symboles x 30 jours)
  size_bytes: ~150000
  partitioning: by_symbol (1 fichier par symbole)
```

---

### 2.2 Dataset : klines traditionnels — `raw.trad.{symbol}`

| Metadonnee | Valeur |
|------------|--------|
| **Identifiant** | `raw.trad.{symbol}` |
| **Localisation** | `data/raw/trad/{SYMBOL}.parquet` |
| **Format** | Apache Parquet (compression Snappy) |
| **Source** | Yahoo Finance via yfinance |
| **Frequence alimentation** | Quotidienne |
| **Proprietaire** | Data Engineer |
| **Classification** | Public |

#### Schema

Identique au schema klines crypto (timestamp, open, high, low, close, volume).

#### Fichiers (33 symboles traditionnels)

| Categorie | Symboles | Nombre |
|-----------|----------|--------|
| US Broad Market | SPY, QQQ, IWM, DIA | 4 |
| International | EFA, VGK, EEM | 3 |
| Obligations | TLT, BND, HYG | 3 |
| Matieres premieres | GLD, SLV, USO | 3 |
| Secteurs US | XLF, XLE, XLK, XLV | 4 |
| Mega caps US | AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA | 7 |
| Finance | JPM, V, GS | 3 |
| Sante / Consommation | JNJ, PG, KO | 3 |
| Europe | ASML.AS, MC.PA, SAP.DE | 3 |

#### Metadonnees techniques

```yaml
dataset:
  id: raw.trad
  created_at: 2025-01-01
  updated_at: # Derniere execution ingest
  schema_version: 1.0
  row_count: ~990 (33 symboles x 30 jours)
  size_bytes: ~100000
  partitioning: by_symbol (1 fichier par symbole)
```

---

### 2.3 Dataset : streaming klines — `streaming.klines.{symbol}`

| Metadonnee | Valeur |
|------------|--------|
| **Identifiant** | `streaming.klines.{symbol}` |
| **Localisation** | `data/streaming/klines/{SYMBOL}.parquet` |
| **Format** | Apache Parquet |
| **Source** | Binance WebSocket → Kafka topic `klines-raw` → Consumer |
| **Frequence alimentation** | Temps reel (micro-batch toutes les 60s ou 100 records) |
| **Proprietaire** | Data Engineer |
| **Classification** | Public |

#### Schema

| Colonne | Type | Nullable | Description |
|---------|------|----------|-------------|
| symbol | STRING | Non | Symbole de la paire |
| timestamp | STRING | Non | Date ISO 8601 |
| open | FLOAT64 | Non | Prix d'ouverture |
| high | FLOAT64 | Non | Prix le plus haut |
| low | FLOAT64 | Non | Prix le plus bas |
| close | FLOAT64 | Non | Prix de cloture |
| volume | FLOAT64 | Non | Volume echange |
| event_time | STRING | Non | Horodatage de reception |

---

### 2.4 Dataset : streaming order book — `streaming.orderbook.{symbol}`

| Metadonnee | Valeur |
|------------|--------|
| **Identifiant** | `streaming.orderbook.{symbol}` |
| **Localisation** | `data/streaming/orderbook/{SYMBOL}.parquet` |
| **Format** | Apache Parquet |
| **Source** | Binance WebSocket → Kafka topic `orderbook-raw` → Consumer |
| **Frequence alimentation** | Temps reel (100ms d'intervalle) |
| **Proprietaire** | Data Engineer |
| **Classification** | Public |

#### Schema

| Colonne | Type | Nullable | Description |
|---------|------|----------|-------------|
| symbol | STRING | Non | Symbole de la paire |
| timestamp | STRING | Non | Horodatage ISO 8601 |
| best_bid | FLOAT64 | Non | Meilleur prix d'achat |
| best_ask | FLOAT64 | Non | Meilleur prix de vente |
| spread | FLOAT64 | Non | Ecart bid-ask |
| spread_bps | FLOAT64 | Non | Spread en points de base |
| bid_depth | FLOAT64 | Non | Profondeur totale bids (top 20) |
| ask_depth | FLOAT64 | Non | Profondeur totale asks (top 20) |
| imbalance | FLOAT64 | Non | Desequilibre offre/demande |
| levels | INT | Non | Nombre de niveaux de prix |

---

## 3. Catalogue detaille — Zone Silver

### 3.1 Datasets crypto

#### 3.1.1 `processed.returns`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/processed/returns.parquet` |
| **Source** | `raw.klines.*` (tous les symboles crypto) |
| **Transformation** | `(close[t] - close[t-1]) / close[t-1]` |
| **Module** | `src/pipeline/transform.py` |

| Colonne | Type | Description |
|---------|------|-------------|
| date | STRING | Date du rendement |
| symbol | STRING | Symbole |
| value | FLOAT64 | Rendement journalier |

#### 3.1.2 `processed.volatility`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/processed/volatility.parquet` |
| **Source** | `processed.returns` |
| **Transformation** | `std(returns) x sqrt(365)` |

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Symbole |
| value | FLOAT64 | Volatilite annualisee |

#### 3.1.3 `processed.mean_returns`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/processed/mean_returns.parquet` |
| **Source** | `processed.returns` |
| **Transformation** | `mean(returns) x 365` |

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Symbole |
| value | FLOAT64 | Rendement moyen annualise |

#### 3.1.4 `processed.correlation`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/processed/correlation.parquet` |
| **Source** | `processed.returns` |
| **Transformation** | Matrice de correlation (Pearson) |

| Colonne | Type | Description |
|---------|------|-------------|
| symbol_row | STRING | Symbole ligne |
| symbol_col | STRING | Symbole colonne |
| value | FLOAT64 | Coefficient de correlation [-1, 1] |

#### 3.1.5 `processed.covariance`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/processed/covariance.parquet` |
| **Source** | `processed.returns` |
| **Transformation** | Matrice de covariance annualisee |

| Colonne | Type | Description |
|---------|------|-------------|
| symbol_row | STRING | Symbole ligne |
| symbol_col | STRING | Symbole colonne |
| value | FLOAT64 | Covariance annualisee |

### 3.2 Datasets traditionnels

Les memes 5 datasets existent pour les actifs traditionnels avec le suffixe `_trad` :

| Dataset | Localisation | Annualisation |
|---------|--------------|---------------|
| `processed.returns_trad` | `data/processed/returns_trad.parquet` | N/A |
| `processed.volatility_trad` | `data/processed/volatility_trad.parquet` | `sqrt(252)` |
| `processed.mean_returns_trad` | `data/processed/mean_returns_trad.parquet` | `x 252` |
| `processed.correlation_trad` | `data/processed/correlation_trad.parquet` | N/A |
| `processed.covariance_trad` | `data/processed/covariance_trad.parquet` | `x 252` |

Note : l'annualisation utilise 365 jours pour crypto et 252 jours pour trad (marches fermes le weekend).

---

## 4. Catalogue detaille — Zone Gold

### 4.1 Dataset : `output.weights`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/output/weights.json` |
| **Source** | `processed.covariance`, `processed.mean_returns` |
| **Transformation** | Optimisation Markowitz (max Sharpe) |
| **Consommateurs** | API REST (`/portfolio`), Dashboard, Reporting |

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

### 4.2 Dataset : `output.frontier`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/output/frontier.json` |
| **Source** | `processed.covariance`, `processed.mean_returns` |
| **Transformation** | Frontiere efficiente (50 points, Markowitz) |
| **Consommateurs** | API REST (`/portfolio/frontier`), Dashboard (page Frontier) |

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

### 4.3 Dataset : `output.backtest`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/output/backtest.json` |
| **Source** | `raw.klines.*` (validation walk-forward) |
| **Transformation** | Fenetres glissantes : 60j train / 30j test |
| **Consommateurs** | API REST (`/portfolio/backtest`), Dashboard (page Backtest) |

```json
{
  "windows": [
    {
      "window_id": 0,
      "train_start": "2025-01-01", "train_end": "2025-03-01",
      "test_start": "2025-03-02", "test_end": "2025-04-01",
      "weights": {"BTCUSDT": 0.4, "ETHUSDT": 0.35, "BNBUSDT": 0.25},
      "test_return": 0.0512
    }
  ],
  "cumulative_values": {
    "dates": ["..."],
    "strategy": [1.0, 1.005],
    "equal_weight": [1.0, 1.004],
    "btc_only": [1.0, 1.003]
  },
  "metrics": {
    "strategy": {"cumulative_return": 0.25, "annualized_return": 0.35,
                  "max_drawdown": 0.12, "sharpe_ratio": 1.85, "calmar_ratio": 2.92},
    "equal_weight": {},
    "btc_only": {}
  },
  "config": {"train_window": 60, "test_window": 30, "strategy": "max_sharpe"}
}
```

### 4.4 Datasets traditionnels (Gold)

| Dataset | Localisation | Consommateur API |
|---------|--------------|------------------|
| `output.weights_trad` | `data/output/weights_trad.json` | `/portfolio/trad` |
| `output.frontier_trad` | `data/output/frontier_trad.json` | `/portfolio/trad/frontier` |
| `output.backtest_trad` | `data/output/backtest_trad.json` | `/portfolio/trad/backtest` |

Schemas identiques aux versions crypto.

---

## 5. Catalogue detaille — Data Warehouse (DuckDB)

### 5.1 Localisation

| Metadonnee | Valeur |
|------------|--------|
| **Fichier** | `data/warehouse.duckdb` |
| **Moteur** | DuckDB (OLAP analytique embarque) |
| **Gestion** | dbt-duckdb (`dbt_project/`) |
| **Materialisation** | Vues et tables DuckDB |

### 5.2 Tables / vues

| Modele dbt | Type | Source | Description |
|------------|------|--------|-------------|
| `stg_klines` | staging | `data/raw/klines/*.parquet` | Klines typees depuis Parquet brut |
| `stg_symbols` | staging | `stg_klines` | Symboles uniques + metadonnees |
| `fact_prices` | marts (fait) | `stg_klines` | OHLCV deduplique (table de faits) |
| `dim_symbol` | marts (dimension) | `stg_symbols` | Metadonnees symboles |
| `dim_date` | marts (dimension) | `stg_klines` | Spine de dates |
| `agg_daily_returns` | marts (agregation) | `fact_prices` | Rendements logarithmiques journaliers |
| `portfolio_summary` | marts (agregation) | `fact_prices` | Metriques resume portefeuille |

### 5.3 Tests dbt

| Test | Fichier | Description |
|------|---------|-------------|
| `assert_positive_volumes` | `dbt_project/tests/` | Verifie que tous les volumes > 0 |
| Schema tests | `dbt_project/models/marts/schema.yml` | not_null, unique sur les cles |

---

## 6. Catalogue detaille — Donnees de reference

### 6.1 `reference.symbols_metadata`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/reference/symbols_metadata.csv` |
| **Format** | CSV avec en-tete |
| **Frequence** | Statique (maintenance manuelle) |
| **Module lecteur** | `src/pipeline/ingest_sources.py` (CSVSource) |

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Paire de trading (ex: BTCUSDT) |
| name | STRING | Nom complet (ex: Bitcoin) |
| sector | STRING | Classification (Currency, Smart Contracts, ...) |
| category | STRING | Categorie technique (Layer 1, Layer 2, ...) |
| launch_year | INT | Annee de lancement |
| market_cap_rank | INT | Classement approximatif |
| is_stablecoin | BOOLEAN | Indicateur stablecoin |
| consensus | STRING | Mecanisme de consensus (PoW, PoS, ...) |

### 6.2 `reference.portfolio_config`

| Metadonnee | Valeur |
|------------|--------|
| **Localisation** | `data/reference/portfolio_config.json` |
| **Format** | JSON |
| **Frequence** | Statique |
| **Module lecteur** | `src/pipeline/ingest_sources.py` (JSONSource) |

Contenu : parametres de portefeuille, contraintes, classification sectorielle, benchmarks.

---

## 7. Lignage des donnees (Data Lineage)

### 7.1 Graphe de dependances

```
[Binance API]          [Yahoo Finance]        [Binance WebSocket]
      │                       │                        │
      │ ingest.py             │ ingest_yfinance.py     │ stream_producer.py
      ▼                       ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          BRONZE                                     │
│  ┌───────────────┐  ┌───────────────┐  ┌────────────┐ ┌──────────┐ │
│  │ raw/klines/   │  │ raw/trad/     │  │ streaming/ │ │streaming/│ │
│  │ (51 crypto)   │  │ (33 trad)     │  │ klines/    │ │orderbook/│ │
│  └───────┬───────┘  └───────┬───────┘  └────────────┘ └──────────┘ │
└──────────┼──────────────────┼──────────────────────────────────────┘
           │                  │
           ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          SILVER                                     │
│  ┌──────────┐  ┌──────────────────┐                                 │
│  │ returns  │  │ returns_trad     │                                 │
│  └────┬─────┘  └────┬─────────────┘                                 │
│       │              │                                               │
│       ▼              ▼                                               │
│  ┌──────────┐  ┌──────────────────┐                                 │
│  │vol, corr,│  │vol_trad, corr_   │                                 │
│  │cov, mean │  │trad, cov_trad,   │                                 │
│  │          │  │mean_trad         │                                 │
│  └────┬─────┘  └────┬─────────────┘                                 │
└───────┼──────────────┼─────────────────────────────────────────────┘
        │              │
        ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           GOLD                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │
│  │ weights  │ │ frontier │ │ backtest │  (crypto)                   │
│  └──────────┘ └──────────┘ └──────────┘                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │
│  │weights_  │ │frontier_ │ │backtest_ │  (trad)                    │
│  │trad      │ │trad      │ │trad      │                            │
│  └──────────┘ └──────────┘ └──────────┘                            │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       EXPOSITION                                    │
│  [FastAPI :8000]  [Streamlit :8501]  [DuckDB warehouse]            │
└─────────────────────────────────────────────────────────────────────┘

                    Pipeline parallele : dbt
[raw/klines/*.parquet] → stg_klines → stg_symbols
                                    → fact_prices → agg_daily_returns
                                    → dim_symbol     portfolio_summary
                                    → dim_date
                        (materialise dans warehouse.duckdb)
```

### 7.2 Matrice de lignage

| Dataset cible | Dependances directes | Module ETL |
|---------------|---------------------|------------|
| `raw.klines.*` | Binance API | `ingest.py` |
| `raw.trad.*` | Yahoo Finance (yfinance) | `ingest_yfinance.py` |
| `streaming.klines.*` | Binance WS → Kafka | `stream_producer.py` → `stream_consumer.py` |
| `streaming.orderbook.*` | Binance WS → Kafka | `stream_producer.py` → `stream_consumer.py` |
| `processed.returns` | `raw.klines.*` | `transform.py` |
| `processed.returns_trad` | `raw.trad.*` | `transform.py` |
| `processed.volatility` | `processed.returns` | `transform.py` |
| `processed.mean_returns` | `processed.returns` | `transform.py` |
| `processed.correlation` | `processed.returns` | `transform.py` |
| `processed.covariance` | `processed.returns` | `transform.py` |
| `output.weights` | `processed.covariance`, `processed.mean_returns` | `optimize.py` |
| `output.frontier` | `processed.covariance`, `processed.mean_returns` | `optimize.py` |
| `output.backtest` | `raw.klines.*` | `backtest.py` |
| `output.weights_trad` | `processed.covariance_trad`, `processed.mean_returns_trad` | `optimize.py` |
| `output.frontier_trad` | `processed.covariance_trad`, `processed.mean_returns_trad` | `optimize.py` |
| `output.backtest_trad` | `raw.trad.*` | `backtest.py` |
| `dwh.fact_prices` | `raw.klines.*` (via dbt) | `dbt_project/models/marts/fact_prices.sql` |
| `dwh.dim_symbol` | `raw.klines.*` (via dbt) | `dbt_project/models/marts/dim_symbol.sql` |
| `dwh.dim_date` | `raw.klines.*` (via dbt) | `dbt_project/models/marts/dim_date.sql` |

---

## 8. Cycle de vie des donnees

### 8.1 Politique de retention

| Zone | Retention | Archivage | Suppression |
|------|-----------|-----------|-------------|
| Bronze (batch) | 365 jours | Non | Automatique (script) |
| Bronze (streaming) | 30 jours | Non | Automatique |
| Silver | 365 jours | Non | Automatique |
| Gold | 30 jours | Non | Ecrasement a chaque execution |
| Reference | Permanent | Non | Manuelle |
| DWH (DuckDB) | Permanent | Non | Reconstruction via dbt |

### 8.2 Processus de suppression

```python
# Pseudo-code: data_lifecycle.py
def cleanup_old_data():
    """Suppression des donnees depassant la retention."""
    today = date.today()

    # Bronze batch: supprimer records > 1 an
    for file in glob("data/raw/klines/*.parquet"):
        df = read_parquet(file)
        df_filtered = df[df.timestamp > today - timedelta(days=365)]
        write_parquet(df_filtered, file)

    # Bronze streaming: supprimer fichiers > 30 jours
    for file in glob("data/streaming/**/*.parquet"):
        if file.mtime < today - timedelta(days=30):
            file.unlink()

    # Silver: idem 365 jours
    # Gold: garder uniquement le dernier fichier (ecrasement)
```

### 8.3 Conformite RGPD

| Critere | Statut | Justification |
|---------|--------|---------------|
| Donnees personnelles | N/A | Aucune donnee personnelle collectee |
| Consentement | N/A | Donnees publiques (Binance, Yahoo Finance) |
| Droit a l'oubli | N/A | Pas d'identification utilisateur |
| Minimisation | ✅ | Seules les donnees OHLCV necessaires |
| Limitation stockage | ✅ | Retention 1 an max (Bronze/Silver) |

---

## 9. Qualite et monitoring

### 9.1 Regles de qualite

| Dataset | Regle | Seuil | Action si violation |
|---------|-------|-------|---------------------|
| `raw.klines.*` | Completude | 100% colonnes | Alerte + retry |
| `raw.klines.*` | Fraicheur | < 24h | Alerte |
| `raw.klines.*` | Prix positifs | open, high, low, close, volume > 0 | Rejet du record |
| `raw.trad.*` | Schema identique | 6 colonnes OHLCV | Erreur pipeline |
| `processed.*` | Valeurs nulles | 0% | Erreur pipeline |
| `processed.correlation` | Symetrie | `corr[i,j] == corr[j,i]` | Erreur pipeline |
| `output.weights` | Somme weights | = 1.0 (tolerance 1e-6) | Erreur pipeline |
| `output.frontier` | Somme weights | = 1.0 par point | Erreur pipeline |
| `output.backtest` | 3 strategies | Presentes (strategy, equal_weight, btc_only) | Erreur pipeline |
| `dwh.fact_prices` | Volumes positifs | `volume > 0` | Test dbt echoue |

### 9.2 Metriques de monitoring

| Metrique | Source | Frequence | Seuil alerte |
|----------|--------|-----------|--------------|
| Nb records Bronze crypto | Parquet metadata | Quotidien | < 1 400 |
| Nb records Bronze trad | Parquet metadata | Quotidien | < 900 |
| Taille totale data/ | Filesystem | Quotidien | > 500 MB |
| Derniere mise a jour | File mtime | Quotidien | > 48h |
| Erreurs ingest | Logs Airflow | Temps reel | > 0 |
| Latence API | Prometheus | Temps reel | p99 > 2s |
| Taux d'erreur API | Prometheus | Temps reel | > 1% |

### 9.3 Alertes

| Evenement | Niveau | Canal | Action |
|-----------|--------|-------|--------|
| Echec ingest | CRITICAL | Log + Airflow alert | Retry auto (3 tentatives) |
| Donnees manquantes | WARNING | Log | Investigation manuelle |
| Espace disque > 80% | WARNING | Log | Cleanup automatique |
| Latence API elevee | WARNING | Grafana | Investigation |
| Test dbt echoue | ERROR | Log dbt | Pipeline bloque |

---

## 10. Acces et securite

### 10.1 Matrice des acces

| Role | Bronze | Silver | Gold | API | Dashboard | DWH | Streaming |
|------|--------|--------|------|-----|-----------|-----|-----------|
| Data Engineer | RW | RW | RW | RW | RW | RW | RW |
| Analyste | R | R | R | R | R | R | R |
| Application | - | - | R | R | - | - | - |

### 10.2 Methodes d'acces

| Methode | Protocole | Authentification |
|---------|-----------|------------------|
| Fichiers Parquet | Filesystem | OS permissions |
| DuckDB SQL | In-process | N/A |
| API REST (FastAPI) | HTTP/JSON | Aucune (MVP) |
| Dashboard (Streamlit) | HTTP | Aucune |
| Redpanda Console | HTTP | Aucune |
| Prometheus/Grafana | HTTP | Login basique |
| Delta Lake | Filesystem | OS permissions |
| MinIO (S3) | HTTP S3 API | Access key / Secret key |

---

## 11. Dictionnaire de donnees consolide

| Terme technique | Terme metier | Definition |
|-----------------|--------------|------------|
| timestamp | Date | Date de la bougie (YYYY-MM-DD) |
| open | Ouverture | Premier prix de la periode |
| high | Plus haut | Prix maximum de la periode |
| low | Plus bas | Prix minimum de la periode |
| close | Cloture | Dernier prix de la periode |
| volume | Volume | Quantite echangee (quote asset) |
| return / value | Rendement | Variation relative du close |
| volatility | Volatilite | Risque (ecart-type annualise) |
| correlation | Correlation | Co-mouvement entre actifs [-1, 1] |
| covariance | Covariance | Variance conjointe |
| weight | Poids | Allocation dans le portefeuille [0, 1] |
| sharpe_ratio | Ratio de Sharpe | Rendement excedentaire / risque |
| best_bid | Meilleur acheteur | Prix le plus eleve d'achat dans le carnet |
| best_ask | Meilleur vendeur | Prix le plus bas de vente dans le carnet |
| spread | Ecart | Difference entre best_ask et best_bid |
| imbalance | Desequilibre | Ratio de la profondeur bids vs asks |
| event_time | Heure de reception | Horodatage de l'evenement streaming |
| asset_class | Classe d'actif | `crypto` ou `traditional` |

---

## 12. Comparaison des approches de catalogage

Le referentiel C20 exige de proposer et comparer plusieurs approches de catalogue de donnees.

| Critere | Markdown (choisi) | Apache Atlas | DataHub (LinkedIn) |
|---------|-------------------|--------------|-------------------|
| Complexite de deploiement | Nulle (fichiers texte) | Elevee (JVM, HBase, Solr, Kafka) | Moyenne (Docker, Elasticsearch) |
| Decouverte automatique | Non (manuelle) | Oui (hooks Hive, Spark) | Oui (connecteurs multiples) |
| Lignage automatique | Non (diagrammes manuels) | Oui (lineage Hive/Spark) | Oui (lineage SQL, Airflow) |
| Recherche | Ctrl+F | API REST + UI | GraphQL + UI |
| Gouvernance (tags, glossaire) | Manuelle | Native (taxonomies, classifications) | Native (tags, domaines, glossaire) |
| Cout infrastructure | 0 | Eleve (~4 services) | Moyen (~3 services) |
| Adapte a notre echelle | ✅ Oui | ❌ Surdimensionne | ❌ Surdimensionne |

**Justification du choix Markdown :**

Ce projet compte ~100 datasets (84 Bronze + 10 Silver + 6 Gold + quelques DWH).
Le volume total est inferieur a 1 MB. L'equipe est composee d'une seule personne.
Dans ce contexte, deployer Apache Atlas (qui necessite HBase, Solr et Kafka)
ou DataHub (Elasticsearch, MySQL, Kafka) serait disproportionne.

Le catalogue Markdown offre :
- Zero dependance d'infrastructure
- Versionne avec le code (Git)
- Lisible sans outil specialise
- Suffisant pour documenter le lignage, les schemas et les regles de qualite

Pour un projet a l'echelle entreprise (>1 000 datasets, equipe >5 personnes),
DataHub serait le choix recommande grace a sa decouverte automatique et son lineage natif.

---

## 13. Conformite au referentiel C20

| Critere d'evaluation | Statut | Preuve |
|---------------------|--------|--------|
| Methodes d'alimentation justifiees | ✅ | Sections 2-4 (6 sources, schemas) |
| Scripts s'executent sans erreur | ✅ | Airflow DAG fonctionnel, 748 tests |
| Donnees importees correctement | ✅ | Sections 2-5 (schemas valides) |
| Metadonnees dans le catalogue | ✅ | Ce document complet |
| Procedures de suppression conformes | ✅ | Section 8 (cycle de vie, RGPD) |
| Monitorage conditions | ✅ | Section 9 (metriques, seuils) |
| Alertes rupture service | ✅ | Section 9.3 (alertes) |
| Catalogues compares et justifies | ✅ | Section 12 (Markdown vs Atlas vs DataHub) |
| Lignage des donnees documente | ✅ | Section 7 (graphe + matrice) |
| Dictionnaire de donnees | ✅ | Section 11 (18 termes) |
