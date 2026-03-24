# Optimisation du portefeuille Binance

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-342%20passed-brightgreen.svg)]()
[![CI](https://github.com/yourusername/binance-portfolio/actions/workflows/ci.yml/badge.svg)]()
[![Couverture](https://img.shields.io/badge/coverage-55%25-yellow.svg)]()

Plate-forme d'ingénierie de données prête pour la production pour l'optimisation du portefeuille de crypto-monnaies à l'aide des données de marché Binance. Construit comme un projet de certification démontrant des pratiques modernes d'ingénierie des données.

## Caractéristiques

- **Ingestion de données multi-sources** - 6 types de sources : API REST, CSV, JSON, Web Scraping, PostgreSQL, yfinance
- **Streaming temps réel** - Ingestion Kafka (Redpanda) via WebSocket Binance
- **Architecture médaillon** - Zones de données Bronze/Argent/Or avec Parquet stockage
- **Star Schema Warehouse** - Requêtes analytiques basées sur DuckDB
- **Optimisation de Markowitz** - Optimisation du portefeuille à variance moyenne maximisant le ratio de Sharpe
- **API REST** - FastAPI avec documentation OpenAPI automatique
- **Tableau de bord interactif** - Visualisation rationalisée avec Plotly charts
- **Orchestration** - DAG Airflow pour l'exécution planifiée du pipeline
- **Stockage S3** - MinIO (S3-compatible) via Storage ABC
- **Cache API** - Redis avec TTL et fallback gracieux
- **Monitoring** - Prometheus + Grafana (métriques, alertes)
- **Qualité des données** - Validation bronze/silver/gold (contrats de données)
- **CI/CD** - GitHub Actions (ruff, mypy, pytest, coverage, bandit, pip-audit)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                           │
│ [Binance API] [CSV] [JSON] [Scraping] [PostgreSQL] [yfinance] │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                  STREAMING (optional)                        │
│   Binance WebSocket → Kafka (Redpanda) → Consumer           │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                       DATA LAKE                             │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│   │ BRONZE  │───▶│ SILVER  │───▶│  GOLD   │                │
│   │  (raw)  │    │(metrics)│    │(weights)│                │
│   └─────────┘    └─────────┘    └─────────┘                │
└──────────┬──────────────────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA WAREHOUSE                           │
│        fact_prices │ dim_symbol │ dim_date                  │
│                    DuckDB + Star Schema                     │
└──────────┬──────────────────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────────────────┐
│                       EXPOSURE                              │
│          FastAPI (:8000)  │  Streamlit (:8501)             │
└─────────────────────────────────────────────────────────────┘
```

## Démarrage rapide

### Prérequis

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommandé) ou pip
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

The `.env` file contains Airflow, PostgreSQL, and Kafka credentials. See `.env.example` for required variables.

### Exécuter avec Docker (recommandé)

```bash
# Start API + Dashboard
docker compose --profile api up

# Access:
# - API: http://localhost:8000/docs
# - Dashboard: http://localhost:8501

# Start streaming ingestion (Kafka)
docker compose --profile streaming up -d
# - Redpanda Console: http://localhost:8080
```

### Exécuter localement

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

## Points de terminaison de l'API

| Point de terminaison | Description |
|----------|-------------|
| `GET /` | Bilan de santé |
| `GET /symbols` | Liste des symboles disponibles |
| `GET /klines/{symbol}` | Données brutes OHLCV |
| `GET /metrics` | Métriques disponibles |
| `GET /metrics/{name}` | Métrique spécifique (rendements, volatilité, corrélation, covariance) |
| `GET /portfolio` | Pondérations optimales du portefeuille |
| `GET /portfolio/summary` | KPI du portefeuille |
| `GET /portfolio/frontier` | Frontière efficiente |
| `GET /portfolio/backtest` | Résultats du backtest walk-forward |
| `GET /portfolio/trad` | Portefeuille traditionnel (actions, ETF, matières premières) |
| `GET /portfolio/trad/frontier` | Frontière efficiente actifs traditionnels |
| `GET /portfolio/trad/backtest` | Backtest actifs traditionnels (benchmark SPY) |
| `GET /portfolio/monte-carlo` | Simulation Monte Carlo (VaR, CVaR, percentiles) |
| `GET /portfolio/combined?crypto_weight=0.6` | Portefeuille combiné crypto + traditionnel |
| `GET /portfolio/rebalance?drift_threshold=0.05` | Alertes de rééquilibrage et trades suggérés |
| `GET /portfolio/report?portfolio_key=weights` | Télécharger rapport PDF du portefeuille |
| `GET /portfolio/risk-contribution` | Contribution marginale au risque par actif |
| `GET /portfolio/rolling-correlation?window=30` | Corrélation glissante entre paires d'actifs |
| `GET /portfolio/scenarios` | Liste des scénarios de stress test disponibles |
| `GET /portfolio/stress-test?scenario=crypto_crash` | Test de stress du portefeuille (5 scénarios prédéfinis + custom) |
| `GET /portfolio/drawdown?portfolio_key=backtest` | Analyse des drawdowns (séries, périodes, récupération) |
| `GET /portfolio/attribution?portfolio_key=weights` | Attribution de performance par actif (poids × rendement) |
| `POST /portfolio/custom` | Évaluation de portefeuille personnalisé (poids définis par l'utilisateur) |
| `GET /prices/live` | Prix en temps réel (Binance 24h ticker) |

## Tableau de bord

Le tableau de bord Streamlit fournit :

- **Cartes KPI** - Rendement attendu, volatilité, ratio de Sharpe
- **Tableau d'allocation** - Graphique des pondérations du portefeuille chart
- **Graphiques de prix** - Données OHLCV par symbole
- **Carte thermique de corrélation** - Matrice de corrélation des actifs
- **Comparaison de volatilité** - Graphique à barres par symbole
- **Monte Carlo** - Fan chart des simulations, histogramme des valeurs finales, VaR/CVaR
- **Live Ticker** - Prix en temps réel avec variation 24h, volume, high/low

## Test

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=term-missing

# Results: 364 tests (100% passing)
```

## Structure du projet

```
src/
├── config.py                # Centralized PipelineConfig + load_config()
├── pipeline/                # ETL modules
│   ├── ingest.py           # Binance API extraction
│   ├── ingest_sources.py   # Multi-source orchestration (DataSource ABC)
│   ├── ingest_scraping.py  # CoinGecko web scraping
│   ├── ingest_postgres.py  # PostgreSQL benchmarks
│   ├── ingest_yfinance.py  # Yahoo Finance (stocks, ETFs, commodities)
│   ├── transform.py        # Financial metrics calculation
│   ├── optimize.py         # Markowitz optimization + efficient frontier
│   ├── backtest.py         # Walk-forward backtesting engine
│   ├── monte_carlo.py      # Monte Carlo simulation (VaR/CVaR)
│   ├── stream_producer.py  # Binance WebSocket → Kafka producer
│   ├── stream_consumer.py  # Kafka → micro-batch Parquet consumer
│   └── validation.py       # Data quality validation (bronze/silver/gold)
├── storage/                 # Data layer
│   ├── base.py             # Abstract interface
│   ├── _utils.py           # Shared storage utilities
│   ├── parquet.py          # Data lake storage
│   ├── duckdb.py           # Data warehouse
│   └── minio.py            # MinIO (S3-compatible) storage
├── api/                     # REST API
│   ├── main.py             # FastAPI endpoints
│   ├── cache.py            # Redis cache (TTL, fallback)
│   ├── metrics.py          # Prometheus business metrics
│   └── schemas.py          # Pydantic response models
└── dashboard/               # Visualization
    └── app.py              # Streamlit app

tests/                       # Test suite (364 tests)
dags/                        # Airflow DAGs
docs/                        # Documentation
data/                        # Data zones (bronze/silver/gold)
```

## Configuration

Modifier `config.toml` :

```toml
[portfolio]
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
interval = "1d"
period_days = 30

[yfinance]
symbols = ["SPY", "EFA", "GLD", "SLV", "TLT", "AAPL", "MSFT", "ASML.AS", "MC.PA", "SAP.DE"]
trading_days_per_year = 252
period_days = 365
```

## Technologies clés

| Composant | Technologie |
|-----------|------------|
| Stockage | Parquet Apache, DuckDB |
| API | FastAPI, Uvicorn |
| Tableau de bord | Streamlit, Plotly |
| Orchestration | Apache Airflow |
| Streaming | Kafka (Redpanda), WebSocket |
| Stockage objet | MinIO (S3-compatible) |
| Cache | Redis (TTL, fallback gracieux) |
| Monitoring | Prometheus, Grafana |
| Qualité données | Validation custom (bronze/silver/gold) |
| Traitement des données | PyArrow (pas de pandas) |
| CI/CD | GitHub Actions (ruff, mypy, pytest) |
| Conteneurisation | Docker, Docker Compose |

## Docker Compose Profiles

| Profil | Services | Usage |
|--------|----------|-------|
| `api` | api, streamlit | Runtime par défaut |
| `pipeline` | pipeline | Bootstrap one-shot (ingestion initiale) |
| `airflow` | postgres, airflow-init, webserver, scheduler | Orchestration planifiée |
| `streaming` | redpanda, redpanda-init, producer, consumer, console | Ingestion temps réel |
| `storage` | minio | Stockage objet S3-compatible |
| `cache` | redis | Cache API (TTL 300s) |
| `monitoring` | prometheus, grafana | Observabilité (métriques, alertes) |
| `benchmarks` | postgres-benchmarks | Base de données benchmarks |
| `full` | Tous les services ci-dessus | Stack complète |

## Documentation

- [Architecture (modèle C4)](docs/architecture/c4_architecture.md)
- [Spécification API (OpenAPI)](docs/architecture/api_specification.yaml)
- [Données Catalogue](docs/rapport/09_catalogue_donnees.md)
- [Conformité RGPD](docs/rapport/07_rgpd.md)

### Enregistrements de décisions d'architecture

- [ADR-001 : Stockage Parquet](docs/architecture/adr/001_storage_parquet.md)
- [ADR-002 : DuckDB Warehouse](docs/architecture/adr/002_duckdb_warehouse.md)
- [ADR-003 : PyArrow sur Pandas](docs/architecture/adr/003_no_pandas.md)
- [ADR-004 : FastAPI](docs/architecture/adr/004_fastapi_exposure.md)
- [ADR-005 : Flux d'air Orchestration](docs/architecture/adr/005_airflow_orchestration.md)

## Formules financières

**Renvois de journaux :**
```
r_t = ln(P_t / P_{t-1})
```

**Volatilité annualisée :**
```
σ = std(r) × √365
```

**Rapport de netteté :**
```
S = (E[R] - Rf) / σ
```

**Écart de portefeuille :**
```
σ²_p = w' × Cov × w
```

## Licence

Ce projet fait partie d'une certification Data Engineer (RNCP Niveau 7).

## Auteur

Laien WU
