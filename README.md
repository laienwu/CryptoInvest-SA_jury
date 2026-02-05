# Binance Portfolio Optimization

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-124%20passed-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-43%25-yellow.svg)]()

A production-ready data engineering platform for cryptocurrency portfolio optimization using Binance market data. Built as a certification project demonstrating modern data engineering practices.

## Features

- **Multi-Source Data Ingestion** - 5 source types: REST API, CSV, JSON, Web Scraping, PostgreSQL
- **Medallion Architecture** - Bronze/Silver/Gold data zones with Parquet storage
- **Star Schema Warehouse** - DuckDB-powered analytical queries
- **Markowitz Optimization** - Mean-variance portfolio optimization maximizing Sharpe ratio
- **REST API** - FastAPI with automatic OpenAPI documentation
- **Interactive Dashboard** - Streamlit visualization with Plotly charts
- **Orchestration** - Airflow DAG for scheduled pipeline execution

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

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Docker & Docker Compose (optional)

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

### Run with Docker (Recommended)

```bash
# Start API + Dashboard
docker compose up api streamlit

# Access:
# - API: http://localhost:8000/docs
# - Dashboard: http://localhost:8501
```

### Run Locally

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

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check |
| `GET /symbols` | List available symbols |
| `GET /klines/{symbol}` | Raw OHLCV data |
| `GET /metrics` | Available metrics |
| `GET /metrics/{name}` | Specific metric (returns, volatility, correlation, covariance) |
| `GET /portfolio` | Optimal portfolio weights |
| `GET /portfolio/summary` | Portfolio KPIs |

## Dashboard

The Streamlit dashboard provides:

- **KPI Cards** - Expected return, volatility, Sharpe ratio
- **Allocation Chart** - Portfolio weights pie chart
- **Price Charts** - OHLCV data per symbol
- **Correlation Heatmap** - Asset correlation matrix
- **Volatility Comparison** - Bar chart by symbol

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=term-missing

# Results: 124 tests, 43% coverage
```

## Project Structure

```
src/
├── pipeline/                # ETL modules
│   ├── ingest.py           # Binance API extraction
│   ├── ingest_sources.py   # Multi-source orchestration
│   ├── transform.py        # Financial metrics calculation
│   └── optimize.py         # Markowitz optimization
├── storage/                 # Data layer
│   ├── base.py             # Abstract interface
│   ├── parquet.py          # Data lake storage
│   └── duckdb.py           # Data warehouse
├── api/                     # REST API
│   └── main.py             # FastAPI endpoints
└── dashboard/               # Visualization
    └── app.py              # Streamlit app

tests/                       # Test suite (124 tests)
dags/                        # Airflow DAGs
docs/                        # Documentation
data/                        # Data zones (bronze/silver/gold)
```

## Configuration

Edit `config.toml`:

```toml
[portfolio]
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
interval = "1d"
period_days = 90

[optimization]
risk_free_rate = 0.05
```

## Key Technologies

| Component | Technology |
|-----------|------------|
| Storage | Apache Parquet, DuckDB |
| API | FastAPI, Uvicorn |
| Dashboard | Streamlit, Plotly |
| Orchestration | Apache Airflow |
| Data Processing | PyArrow (no pandas) |
| Containerization | Docker, Docker Compose |

## Documentation

- [Architecture (C4 Model)](docs/architecture/c4_architecture.md)
- [API Specification (OpenAPI)](docs/architecture/api_specification.yaml)
- [Data Catalog](docs/rapport/09_catalogue_donnees.md)
- [RGPD Compliance](docs/rapport/07_rgpd.md)

### Architecture Decision Records

- [ADR-001: Parquet Storage](docs/architecture/adr/001_storage_parquet.md)
- [ADR-002: DuckDB Warehouse](docs/architecture/adr/002_duckdb_warehouse.md)
- [ADR-003: PyArrow over Pandas](docs/architecture/adr/003_no_pandas.md)
- [ADR-004: FastAPI](docs/architecture/adr/004_fastapi_exposure.md)
- [ADR-005: Airflow Orchestration](docs/architecture/adr/005_airflow_orchestration.md)

## Financial Formulas

**Log Returns:**
```
r_t = ln(P_t / P_{t-1})
```

**Annualized Volatility:**
```
σ = std(r) × √365
```

**Sharpe Ratio:**
```
S = (E[R] - Rf) / σ
```

**Portfolio Variance:**
```
σ²_p = w' × Cov × w
```

## License

This project is part of a Data Engineer certification (RNCP Level 7).

## Author

Data Engineer Certification Project - 2025
