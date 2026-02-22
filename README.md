# Optimisation du portefeuille Binance

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com/)
 [![Tests](https://img.shields.io/badge/tests-254%20passed-brightgreen.svg)]()
[![Couverture](https://img.shields.io/badge/coverage-53%25-yellow.svg)]()

A plate-forme d'ingénierie de données prête pour la production pour l'optimisation du portefeuille de crypto-monnaies à l'aide des données de marché Binance. Construit comme un projet de certification démontrant des pratiques modernes d'ingénierie des données.

## Caractéristiques

- **Ingestion de données multi-sources** - 5 types de sources : API REST, CSV, JSON, Web Scraping, PostgreSQL
- **Architecture médaillon** - Zones de données Bronze/Argent/Or avec Parquet stockage
- **Star Schema Warehouse** - Requêtes analytiques basées sur DuckDB
- **Optimisation de Markowitz** - Optimisation du portefeuille à variance moyenne maximisant le ratio de Sharpe
- **API REST** - FastAPI avec documentation OpenAPI automatique
- **Tableau de bord interactif** - Visualisation rationalisée avec Plotly charts
- **Orchestration** – DAG Airflow pour l'exécution planifiée du pipeline

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                           │
│   [Binance API] [CSV] [JSON] [Web Scraping] [PostgreSQL]   │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       DATA LAKE                             │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│   │ BRONZE  │───▶│ SILVER  │───▶│  GOLD   │                │
│   │  (raw)  │    │(metrics)│    │(weights)│                │
│   └─────────┘    └─────────┘    └─────────┘                │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA WAREHOUSE                           │
│        fact_prices │ dim_symbol │ dim_date                  │
│                    DuckDB + Star Schema                     │
└───────────────────────────┬─────────────────────────────────┘
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

The `.env` file contains Airflow and PostgreSQL credentials. See `.env.example` for required variables.

### Exécuter avec Docker (recommandé)

```bash
# Start API + Dashboard
docker compose up api streamlit

# Access:
# - API: http://localhost:8000/docs
# - Dashboard: http://localhost:8501
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

## Tableau de bord

Le tableau de bord Streamlit fournit :

- **Cartes KPI** - Rendement attendu, volatilité, ratio de Sharpe
- **Tableau d'allocation** - Graphique des pondérations du portefeuille chart
- **Graphiques de prix** - Données OHLCV par symbole
- **Carte thermique de corrélation** - Matrice de corrélation des actifs
- **Comparaison de volatilité** - Graphique à barres par symbole

## Test

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=term-missing

# Results: 254 tests
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
│   ├── transform.py        # Financial metrics calculation
│   ├── optimize.py         # Markowitz optimization + efficient frontier
│   └── backtest.py         # Walk-forward backtesting engine
├── storage/                 # Data layer
│   ├── base.py             # Abstract interface
│   ├── _utils.py           # Shared storage utilities
│   ├── parquet.py          # Data lake storage
│   └── duckdb.py           # Data warehouse
├── api/                     # REST API
│   ├── main.py             # FastAPI endpoints
│   └── schemas.py          # Pydantic response models
└── dashboard/               # Visualization
    └── app.py              # Streamlit app

tests/                       # Test suite (254 tests)
dags/                        # Airflow DAGs
docs/                        # Documentation
data/                        # Data zones (bronze/silver/gold)
```

## Configuration

Modifier `config.toml` :

```toml
[portfolio]
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
interval = "1d"
period_days = 90
```

## Technologies clés

| Composant | Technologie |
|-----------|------------|
| Stockage | Parquet Apache, DuckDB |
| API | FastAPI, Uvicorn |
| Tableau de bord | Streamlit, Plotly |
| Orchestration | Apache Airflow |
| Traitement des données | PyArrow (pas de pandas) |
| Conteneurisation | Docker, Docker Compose |

## Documentation

- [Architecture (modèle C4)](docs/architecture/c4_architecture.md)
- [Spécification API (OpenAPI)](docs/architecture/api_specification.yaml)
- [Données Catalogue](docs/rapport/09_catalogue_donnees.md)
- [Conformité RGPD](docs/rapport/07_rgpd.md)

### Enregistrements de décisions d'architecture

- [ADR-001 : Stockage Parquet](docs/architecture/adr/001_storage_parquet.md)
- [ADR-002 : DuckDB Warehouse](docs/architecture/adr/002_duckdb_warehouse.md)
- [ADR-003 : PyArrow sur Pandas](docs/architecture/adr/003_no_pandas.md)
- [ADR-004 : FastAPI](docs/architecture/adr/004_fastapi_exposure.md)
- [ADR-005 : Flux d'air Orchestration](docs/architecture/adr/005_airflow_orchestration.md)

## Formules financières

**Renvois de journaux :**
```
r_t = ln(P_t / P_{t-1})
```

**Volatilité annualisée :**
```
σ = std(r) × √365
```

**Rapport de netteté :**
```
S = (E[R] - Rf) / σ
```

**Écart de portefeuille :**
```
σ²_p = w' × Cov × w
```

## Licence

Ce projet fait partie d'une certification Data Engineer (RNCP Niveau 7).

## Auteur

Projet de certification Data Engineer - 2025
