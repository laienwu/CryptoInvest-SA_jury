# Optimisation du portefeuille Binance

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1+-FFF000.svg?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![Apache Airflow](https://img.shields.io/badge/Airflow-2.10+-017CEE.svg?logo=apacheairflow&logoColor=white)](https://airflow.apache.org/)
[![dbt](https://img.shields.io/badge/dbt-1.9+-FF694A.svg?logo=dbt&logoColor=white)](https://www.getdbt.com/)
[![Apache Kafka](https://img.shields.io/badge/Kafka-Redpanda-231F20.svg?logo=apachekafka&logoColor=white)](https://redpanda.com/)
[![Apache Spark](https://img.shields.io/badge/PySpark-3.5+-E25A1C.svg?logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![Delta Lake](https://img.shields.io/badge/Delta_Lake-0.22+-00ADD4.svg?logo=databricks&logoColor=white)](https://delta.io/)
[![Apache Parquet](https://img.shields.io/badge/Parquet-PyArrow-50ABF1.svg?logo=apacheparquet&logoColor=white)](https://parquet.apache.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-DC382D.svg?logo=redis&logoColor=white)](https://redis.io/)
[![MinIO](https://img.shields.io/badge/MinIO-S3-C72E49.svg?logo=minio&logoColor=white)](https://min.io/)
[![Prometheus](https://img.shields.io/badge/Prometheus-2.x-E6522C.svg?logo=prometheus&logoColor=white)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-10+-F46800.svg?logo=grafana&logoColor=white)](https://grafana.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-2.x-E92063.svg?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Plotly](https://img.shields.io/badge/Plotly-5+-3F4F75.svg?logo=plotly&logoColor=white)](https://plotly.com/python/)
[![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64.svg?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![mypy](https://img.shields.io/badge/types-mypy_strict-2A6DB2.svg)](https://mypy-lang.org/)
[![pytest](https://img.shields.io/badge/tests-pytest_748-0A9EDC.svg?logo=pytest&logoColor=white)](https://pytest.org/)
[![GitHub Actions](https://img.shields.io/badge/CI-GitHub_Actions-2088FF.svg?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Project
Data Engineer certification project (RNCP Level 7 - Expert en infrastructures de données massives).
Plate-forme d'ingenierie de donnees pour l'optimisation de portefeuille crypto + actifs traditionnels. Projet de certification Data Engineer (RNCP Niveau 7 - Expert en infrastructures de donnees massives).

## Caracteristiques

- **Ingestion multi-sources** - 6 types : API REST (Binance), CSV, JSON, Web Scraping (CoinGecko), PostgreSQL, yfinance (33 actifs traditionnels)
- **Streaming temps reel** - Binance WebSocket → Kafka (Redpanda) → micro-batch Parquet (klines + order book depth)
- **Architecture medallion** - Zones Bronze/Silver/Gold avec Parquet partitionne
- **Delta Lake** - Stockage ACID optionnel (delta-rs, sans JVM, time travel)
- **Star Schema Warehouse** - DuckDB OLAP embarque (fact_prices, dim_symbol, dim_date)
- **dbt transforms** - 6 modeles SQL staging/marts avec tests et lineage (dbt-duckdb)
- **PySpark analytics** - Rolling correlation, volatility surface, volume analysis
- **6 strategies d'optimisation** - Markowitz, HRP, Risk Parity, Black-Litterman, Min Variance, Max Diversification
- **45 endpoints REST** - FastAPI avec OpenAPI, cache Redis, metriques Prometheus
- **31 pages dashboard** - Streamlit avec graphiques Plotly interactifs
- **Orchestration** - Airflow DAG (12 taches, 2 branches paralleles crypto + trad)
- **Stockage S3** - MinIO (S3-compatible) via Storage ABC
- **Cache API** - Redis avec TTL et fallback gracieux
- **Monitoring** - Prometheus + Grafana (metriques metier, alertes, dashboards)
- **Qualite des donnees** - Validation bronze/silver/gold (contrats de donnees)
- **CI/CD** - GitHub Actions (ruff, mypy, pytest, coverage, bandit, pip-audit)

## Status: ✅ 21 COMPETENCES COMPLETES

### Bloc 1: Pilotage projet (C1-C7)
| ID | Compétence | Status | Implementation |
|----|------------|--------|----------------|
| C1-C4 | Analyse besoin, cartographie, cadre technique, veille | ✅ | `docs/rapport/01-04` |
| C5-C7 | Planifier, superviser, communiquer | ✅ | `docs/rapport/05-06` + business docs |

### Bloc 2: Collecte, stockage, mise à disposition (C8-C12)
| ID | Compétence | Status | Implementation |
|----|------------|--------|----------------|
| C8 | Automatiser extraction (API, scraping, fichier, BDD, big data) | ✅ | 6 sources: API, CSV, JSON, Scraping, PostgreSQL, yfinance |
| C9 | Requêtes SQL d'extraction | ✅ | `storage/duckdb.py` SQL queries |
| C10 | Règles d'agrégation multi-sources | ✅ | `ingest_sources.py` + `transform.py` |
| C11 | Créer base de données (MERISE, RGPD) | ✅ | `docs/rapport/10_merise.md` (MCD/MLD/MPD) |
| C12 | Partager via API REST | ✅ | `src/api/main.py` FastAPI |

### Bloc 3: Data Warehouse (C13-C17)
| ID | Compétence | Status | Implementation |
|----|------------|--------|----------------|
| C13 | Modéliser faits/dimensions | ✅ | `fact_prices`, `dim_symbol`, `dim_date` |
| C14 | Créer entrepôt | ✅ | `storage/duckdb.py` DuckDB adapter |
| C15 | Intégrer ETL in/out | ✅ | Airflow DAG `dags/portfolio_dag.py` |
| C16 | Gérer l'entrepôt | ✅ | Airflow monitoring, scheduling |
| C17 | Variations dimensions | ✅ | `docs/rapport/08_scd_dimensions.md` |

### Bloc 4: Data Lake (C18-C21)
| ID | Compétence | Status | Implementation |
|----|------------|--------|----------------|
| C18 | Concevoir architecture | ✅ | `data/` zones + Docker |
| C19 | Intégrer composants | ✅ | Parquet + DuckDB + Docker Compose |
| C20 | Gérer catalogue | ✅ | `docs/rapport/09_catalogue_donnees.md` |
| C21 | Règles gouvernance (RGPD) | ✅ | `docs/rapport/07_rgpd.md` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES (6)                             │
│  [Binance API] [CSV] [JSON] [Scraping] [PostgreSQL] [yfinance]      │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STREAMING (optionnel)                            │
│    Binance WebSocket → Kafka (Redpanda) → Consumer → Parquet        │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA LAKE                                   │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                          │
│  │ BRONZE  │───▶│ SILVER  │───▶│  GOLD   │  + Delta Lake (ACID)     │
│  │  (raw)  │    │(metrics)│    │(weights)│                          │
│  └─────────┘    └─────────┘    └─────────┘                          │
└──────────┬──────────────────────────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA WAREHOUSE                                 │
│   fact_prices │ dim_symbol │ dim_date │ dbt models (staging+marts)  │
│                        DuckDB + Star Schema                         │
└──────────┬──────────────────────────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         EXPOSURE                                    │
│   FastAPI (:8000) │ Streamlit (:8501) │ Prometheus+Grafana (:9090)  │
└─────────────────────────────────────────────────────────────────────┘
```

## Demarrage rapide

### Prerequis

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommande) ou pip
- Docker & Docker Compose (facultatif)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/binance-portfolio.git
cd binance-portfolio

# Install dependencies
uv sync

# Or with pip
pip install -e .
```

### Configuration

```bash
# Copy environment template and adjust values
cp .env.example .env
```

Le fichier `.env` contient les identifiants Airflow, PostgreSQL et Kafka. Voir `.env.example` pour les variables requises.

### Executer avec Docker (recommande)

```bash
# Start API + Dashboard (services par defaut)
docker compose up

# Access:
# - API: http://localhost:8000/docs
# - Dashboard: http://localhost:8501

# Start streaming ingestion (Kafka)
docker compose --profile streaming up -d
# - Redpanda Console: http://localhost:8080

# Start Airflow (orchestration planifiee)
docker compose --profile airflow up -d
# - Airflow UI: http://localhost:8081

# Start monitoring
docker compose --profile monitoring up -d
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000

# Stack complete
docker compose --profile full up -d
```

### Executer localement

```bash
# 1. Run the pipeline
uv run python -c "
from src.pipeline import ingest_data, transform_data, optimize_portfolio
from src.storage import get_storage

storage = get_storage()
data = ingest_data()
storage.save_raw(data)
transform_data()
optimize_portfolio()
"

# 2. Start the API
uv run uvicorn src.api.main:app --reload

# 3. Start the Dashboard (separate terminal)
uv run streamlit run src/dashboard/app.py
```

## Points de terminaison de l'API (45 endpoints)

### General (5)

| Endpoint | Description |
|----------|-------------|
| `GET /` | Bilan de sante |
| `GET /symbols` | Liste des symboles disponibles |
| `GET /klines/{symbol}` | Donnees brutes OHLCV |
| `GET /metrics` | Metriques disponibles |
| `GET /metrics/{name}` | Metrique specifique (rendements, volatilite, correlation, covariance) |

### Portefeuille (7)

| Endpoint | Description |
|----------|-------------|
| `GET /portfolio` | Ponderations optimales du portefeuille |
| `GET /portfolio/summary` | KPI du portefeuille |
| `GET /portfolio/frontier` | Frontiere efficiente |
| `GET /portfolio/backtest` | Resultats du backtest walk-forward |
| `GET /portfolio/trad` | Portefeuille traditionnel (actions, ETF, matieres premieres) |
| `GET /portfolio/trad/frontier` | Frontiere efficiente actifs traditionnels |
| `GET /portfolio/trad/backtest` | Backtest actifs traditionnels (benchmark SPY) |

### Analyse (14)

| Endpoint | Description |
|----------|-------------|
| `GET /portfolio/monte-carlo` | Simulation Monte Carlo (VaR, CVaR, percentiles) |
| `GET /portfolio/rolling-correlation` | Correlation glissante entre paires d'actifs |
| `GET /portfolio/risk-contribution` | Contribution marginale au risque par actif |
| `GET /portfolio/combined` | Portefeuille combine crypto + traditionnel |
| `GET /portfolio/rebalance` | Alertes de reequilibrage et trades suggeres |
| `GET /portfolio/signals` | Signaux de trading (SMA crossover, RSI, MACD, Bollinger) |
| `GET /portfolio/risk-parity` | Portefeuille risk parity (contribution egale au risque) |
| `GET /portfolio/position-sizing` | Dimensionnement des positions (Kelly, vol-target, fractional) |
| `GET /portfolio/cost-analysis` | Analyse des couts de transaction (frais, slippage) |
| `GET /portfolio/alpha-beta` | Analyse CAPM alpha/beta vs benchmark |
| `GET /portfolio/regime` | Detection de regime de marche (bull/bear/sideways) |
| `GET /portfolio/sortino` | Ratio de Sortino, risque baissier, capture ratios |
| `GET /portfolio/factors` | Exposition multi-facteurs (marche, momentum, volatilite) |
| `GET /portfolio/tail-risk` | Moments superieurs (skewness, kurtosis, Omega, Calmar) |

### Optimisation (7)

| Endpoint | Description |
|----------|-------------|
| `POST /portfolio/constrained` | Optimisation sous contraintes (poids min/max, groupes) |
| `GET /portfolio/black-litterman` | Optimisation bayesienne Black-Litterman |
| `GET /portfolio/hrp` | Hierarchical Risk Parity (allocation par clustering) |
| `GET /portfolio/var` | Comparaison VaR (historique, parametrique, Cornish-Fisher) |
| `GET /portfolio/shrinkage` | Estimation Ledoit-Wolf de la covariance |
| `GET /portfolio/max-diversification` | Maximisation du ratio de diversification |
| `GET /portfolio/min-variance` | Portefeuille de variance minimale globale |

### Avance (7)

| Endpoint | Description |
|----------|-------------|
| `GET /portfolio/decay` | Derive des poids du portefeuille dans le temps |
| `GET /portfolio/pairs` | Analyse de cointegration Engle-Granger |
| `GET /portfolio/compare-strategies` | Comparaison des 6 strategies d'optimisation |
| `GET /portfolio/backtest/multi` | Backtest multi-strategies (courbes d'equity) |
| `POST /portfolio/custom` | Evaluation de portefeuille personnalise |
| `GET /portfolio/report` | Telecharger rapport PDF du portefeuille |
| `GET /portfolio/stress-test` | Test de stress (5 scenarios + custom) |

### Donnees et monitoring (5)

| Endpoint | Description |
|----------|-------------|
| `GET /portfolio/scenarios` | Liste des scenarios de stress disponibles |
| `GET /portfolio/drawdown` | Analyse des drawdowns et recuperation |
| `GET /portfolio/attribution` | Attribution de performance par actif |
| `GET /prices/live` | Prix en temps reel (Binance 24h ticker) |
| `GET /data/metrics` | Metriques de volume de donnees (tailles, fraicheur) |

*Documentation automatique : `/docs` (Swagger) et `/redoc` (ReDoc)*

## Tableau de bord (31 pages)

- **Dashboard** - Cartes KPI, allocation pie chart, correlation heatmap
- **Symbols** - Graphiques OHLCV par symbole
- **Metrics** - Exploration des metriques brutes
- **Frontier** - Frontiere efficiente interactive
- **Backtest** - Resultats du walk-forward backtesting
- **Monte Carlo** - Fan chart des simulations, histogramme, VaR/CVaR
- **Live Prices** - Prix en temps reel avec variation 24h
- **Rebalancing** - Alertes et suggestions de reequilibrage
- **Signals** - Signaux de trading (SMA, RSI, MACD, Bollinger)
- **Regime** - Detection de regime de marche (bull/bear/sideways)
- **Cost Analysis** - Modele de couts de transaction (frais, slippage)
- **Alpha/Beta** - Analyse CAPM vs benchmarks
- **Sortino Risk** - Metriques de risque baissier (Sortino, downside deviation)
- **Comparison** - Comparaison crypto vs traditionnel
- **Constrained** - Optimisation sous contraintes (min/max poids, groupes)
- **Correlation Network** - Correlations glissantes par paires
- **Position Sizing** - Kelly, vol-target, fixed-fractional
- **Stress Test** - Scenarios de stress du portefeuille
- **Drawdown** - Analyse des drawdowns et recuperation
- **Attribution** - Decomposition de la performance par actif
- **Black-Litterman** - Optimisation bayesienne avec vues investisseur
- **HRP** - Hierarchical Risk Parity (allocation par clustering)
- **VaR Comparison** - Historique, Parametrique, Cornish-Fisher
- **Shrinkage** - Estimation Ledoit-Wolf de la covariance
- **Max Diversification** - Maximisation du ratio de diversification
- **Min Variance** - Portefeuille de variance minimale globale
- **Factor Analysis** - Exposition multi-facteurs (marche, momentum, volatilite)
- **Tail Risk** - Moments superieurs (skewness, kurtosis, Jarque-Bera, Omega, Calmar)
- **Decay** - Derive des poids du portefeuille dans le temps
- **Pairs Trading** - Analyse de cointegration Engle-Granger
- **Strategy Showdown** - Comparaison cote a cote des 6 strategies d'optimisation

## Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=term-missing

# Results: 1201 tests across 53 files (100% passing)
```

## Structure du projet

```
src/
├── config.py                    # PipelineConfig centralise + load_config()
├── pipeline/                    # 42 modules ETL + analytics
│   ├── ingest.py               # Extraction Binance API
│   ├── ingest_sources.py       # Orchestrateur multi-sources (DataSource ABC)
│   ├── ingest_scraping.py      # Web scraping CoinGecko
│   ├── ingest_postgres.py      # Benchmarks PostgreSQL
│   ├── ingest_yfinance.py      # Yahoo Finance (33 actifs traditionnels)
│   ├── transform.py            # Rendements, volatilite, correlation, covariance
│   ├── optimize.py             # Markowitz + frontiere efficiente
│   ├── backtest.py             # Walk-forward backtesting
│   ├── monte_carlo.py          # Simulation Monte Carlo (VaR/CVaR)
│   ├── strategy_compare.py     # Comparaison des 6 strategies
│   ├── risk_parity.py          # Parite de risque
│   ├── black_litterman.py      # Optimisation bayesienne
│   ├── hrp.py                  # Hierarchical Risk Parity
│   ├── min_variance.py         # Variance minimale globale
│   ├── max_diversification.py  # Diversification maximale
│   ├── constrained.py          # Optimisation sous contraintes
│   ├── signals.py              # Signaux (SMA, RSI, MACD, Bollinger)
│   ├── regime.py               # Detection de regime de marche
│   ├── pairs.py                # Cointegration Engle-Granger
│   ├── stream_producer.py      # Binance WebSocket → Kafka
│   ├── stream_consumer.py      # Kafka → micro-batch Parquet
│   ├── spark_transforms.py     # PySpark analytics
│   ├── data_metrics.py         # Metriques de volume de donnees
│   ├── validation.py           # Validation qualite des donnees
│   └── ...                     # +18 modules (voir CLAUDE.md)
├── storage/                     # Couche stockage
│   ├── base.py                 # Interface abstraite (Storage ABC)
│   ├── parquet.py              # Data Lake (Bronze/Silver/Gold)
│   ├── duckdb.py               # Data Warehouse (schema en etoile)
│   ├── delta.py                # Delta Lake (ACID, time travel)
│   └── minio.py                # MinIO (S3-compatible)
├── api/                         # API REST
│   ├── main.py                 # FastAPI (45 endpoints, Depends injection)
│   ├── cache.py                # Cache Redis (TTL, fallback)
│   ├── metrics.py              # Metriques Prometheus metier
│   └── schemas.py              # Modeles de reponse Pydantic
└── dashboard/                   # Visualisation
    └── app.py                  # Streamlit (31 pages, Plotly)

tests/                           # 1201 tests across 53 files
dags/                            # Airflow DAG (12 taches, 2 branches paralleles)
dbt_project/                     # dbt-duckdb (6 modeles SQL, tests, lineage)
docs/                            # Documentation (architecture, rapport, operations)
data/                            # Zones de donnees (bronze/silver/gold/reference)
monitoring/                      # Prometheus + Grafana (alertes, dashboards)
```

## Configuration

Modifier `config.toml` :

```toml
[portfolio]
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
interval = "1d"
period_days = 30

[yfinance]
symbols = ["SPY", "EFA", "GLD", "SLV", "TLT", "AAPL", "MSFT", "ASML.AS", "MC.PA", "SAP"]
trading_days_per_year = 252
period_days = 365
```

## Technologies cles

| Composant | Technologie |
|-----------|------------|
| Stockage | Apache Parquet, Delta Lake (delta-rs) |
| Entrepot | DuckDB (OLAP embarque, schema en etoile) |
| Transforms SQL | dbt-duckdb (staging + marts, tests, lineage) |
| API | FastAPI, Uvicorn, Pydantic |
| Tableau de bord | Streamlit, Plotly |
| Orchestration | Apache Airflow 2.8.1 |
| Streaming | Kafka (Redpanda), WebSocket Binance |
| Stockage objet | MinIO (S3-compatible) |
| Cache | Redis (TTL, fallback gracieux) |
| Monitoring | Prometheus, Grafana |
| Traitement | PyArrow (pas de pandas — ADR-003) |
| Distribue | PySpark (correlation rolling, volatilite) |
| CI/CD | GitHub Actions (ruff, mypy, pytest, bandit) |
| Conteneurisation | Docker, Docker Compose (9 profils) |

## Docker Compose Profiles

| Profil | Services | Usage |
|--------|----------|-------|
| *(default)* | api, streamlit | Services de base (API + dashboard) |
| `pipeline` | pipeline | Bootstrap one-shot (ingestion initiale) |
| `airflow` | postgres, airflow-init, webserver, scheduler | Orchestration planifiee (:8081) |
| `streaming` | redpanda, redpanda-init, producer, consumer, console | Ingestion temps reel (:8080) |
| `storage` | minio | Stockage objet S3-compatible (:9000) |
| `cache` | redis | Cache API (TTL 300s) |
| `monitoring` | prometheus, grafana | Observabilite (:9090, :3000) |
| `benchmarks` | postgres-benchmarks | Base de donnees benchmarks (:5433) |
| `spark` | spark | Transformations PySpark |
| `full` | Tous les services ci-dessus | Stack complete |

## Documentation

- [Architecture C4](docs/architecture/c4_architecture.md)
- [Specification API (OpenAPI 3.0)](docs/architecture/api_specification.yaml)
- [Catalogue de donnees](docs/rapport/09_catalogue_donnees.md)
- [Conformite RGPD](docs/rapport/07_rgpd.md)

### Decisions d'architecture (ADR)

- [ADR-001 : Stockage Parquet](docs/architecture/adr/001_storage_parquet.md)
- [ADR-002 : DuckDB Warehouse](docs/architecture/adr/002_duckdb_warehouse.md)
- [ADR-003 : PyArrow (pas de pandas)](docs/architecture/adr/003_no_pandas.md)
- [ADR-004 : FastAPI](docs/architecture/adr/004_fastapi_exposure.md)
- [ADR-005 : Airflow Orchestration](docs/architecture/adr/005_airflow_orchestration.md)
- [ADR-006 : Delta Lake](docs/architecture/adr/006_delta_lake.md)
- [ADR-007 : dbt Transforms](docs/architecture/adr/007_dbt_transforms.md)

## Formules financieres

**Rendements logarithmiques :**
```
r_t = ln(P_t / P_{t-1})
```

**Volatilite annualisee :**
```
sigma = std(r) * sqrt(365)
```

**Ratio de Sharpe :**
```
S = (E[R] - Rf) / sigma
```

**Variance du portefeuille :**
```
sigma^2_p = w' * Cov * w
```

---

## Commandes rapides


```bash
# 1. Start infrastructure
docker compose --profile full up -d
docker compose up -d streamlit

# 2. Show multi-source ingestion (C8)
python -c "from src.pipeline import ingest_all_sources; ingest_all_sources()"

# 3. Show transformation (C10)
python -c "from src.pipeline import transform_data; transform_data()"

# 4. Show optimization
python -c "from src.pipeline import optimize_portfolio; optimize_portfolio()"

# 5. Show efficient frontier
python -c "from src.pipeline.optimize import compute_and_save_frontier; compute_and_save_frontier()"

# 6. Show backtesting
python -c "from src.pipeline.backtest import run_backtest; run_backtest()"

# 7. Show API (C12)
curl http://localhost:8000/portfolio
curl http://localhost:8000/portfolio/frontier
curl http://localhost:8000/portfolio/backtest
curl http://localhost:8000/portfolio/trad
curl http://localhost:8000/portfolio/trad/frontier
curl http://localhost:8000/portfolio/trad/backtest

# 8. Show Dashboard (C12)
# Open http://localhost:8501
# - Dashboard page: KPIs, Pie chart, Correlation heatmap
# - Symbols page: Price charts with symbol selector
# - Metrics page: Raw metrics exploration
# - Frontier page: Efficient frontier visualization
# - Backtest page: Walk-forward test results
# - Monte Carlo page: Simulation fan chart + histogram
# - Live Prices page: Real-time price ticker
# - Rebalancing page: Portfolio rebalancing alerts
# - Signals page: Trading signals (SMA, RSI, MACD, Bollinger)
# - Regime page: Market regime detection (bull/bear/sideways)
# - Cost Analysis page: Transaction cost model
# - Alpha/Beta page: CAPM analysis vs benchmarks
# - Sortino Risk page: Downside risk metrics
# - Comparison page: Crypto vs Traditional portfolio
# - Constrained page: Constrained optimization (min/max weights)
# - Correlation Network page: Rolling pairwise correlations
# - Position Sizing page: Kelly, vol-target, fixed-fractional
# - Stress Test page: Portfolio stress scenarios
# - Drawdown page: Drawdown analysis and recovery
# - Attribution page: Performance attribution decomposition
# - Black-Litterman page: Views-based Bayesian optimization
# - HRP page: Hierarchical Risk Parity (clustering allocation)
# - VaR page: Value-at-Risk comparison (3 methods)
# - Shrinkage page: Ledoit-Wolf covariance shrinkage
# - Max Diversification page: Diversification ratio maximization
# - Min Variance page: Global minimum volatility portfolio
# - Factors page: Multi-factor exposure analysis
# - Tail Risk page: Higher moments (skewness, kurtosis, JB, Omega, Calmar)
# - Decay page: Portfolio weight drift over time
# - Pairs page: Cointegration analysis and z-score signals
# - Strategy Showdown page: All 6 optimizers compared side-by-side
# - Multi Backtest page: Overlaid equity curves for all strategies

# 9. Show Airflow DAG (C15, C16)
# Open http://localhost:8081

# 10. Show DuckDB queries (C9, C14)
python -c "
import duckdb
conn = duckdb.connect('data/warehouse.duckdb')
print(conn.execute('SELECT * FROM fact_prices LIMIT 5').fetchall())
"
```


---

## Licence

Ce projet fait partie d'une certification Data Engineer (RNCP Niveau 7 — Expert en infrastructures de donnees massives).

## Auteur

Laien WU
