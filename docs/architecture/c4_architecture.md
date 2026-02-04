# C4 Architecture Model

## Overview

This document presents the system architecture using the C4 model (Context, Containers, Components, Code).

---

## Level 1: System Context

```
                                    ┌─────────────────────────────────────┐
                                    │         External Systems            │
                                    └─────────────────────────────────────┘
                                                     │
                    ┌────────────────────────────────┼────────────────────────────────┐
                    │                                │                                │
                    ▼                                ▼                                ▼
           ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
           │  Binance API  │              │   CoinGecko   │              │ Benchmark DB  │
           │   (prices)    │              │  (rankings)   │              │  (PostgreSQL) │
           └───────┬───────┘              └───────┬───────┘              └───────┬───────┘
                   │                              │                              │
                   │                              │                              │
                   └──────────────────────────────┼──────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│                         PORTFOLIO OPTIMIZATION PLATFORM                                 │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              Data Pipeline                                       │  │
│   │   [Ingest] ──▶ [Transform] ──▶ [Optimize] ──▶ [Store]                          │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                         │                                               │
│                                         ▼                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              REST API (FastAPI)                                  │  │
│   │                              http://localhost:8000                               │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    │                             │                             │
                    ▼                             ▼                             ▼
           ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
           │    Analyst    │              │   Portfolio   │              │   Trading     │
           │   (Sophie)    │              │    Manager    │              │    System     │
           │               │              │    (Claire)   │              │   (future)    │
           └───────────────┘              └───────────────┘              └───────────────┘
                                    ┌─────────────────────────────────────┐
                                    │            Consumers                │
                                    └─────────────────────────────────────┘
```

### Context Description

| Actor/System | Type | Description |
|--------------|------|-------------|
| Binance API | External | Provides real-time and historical OHLCV price data |
| CoinGecko | External | Market rankings and metadata via web scraping |
| Benchmark DB | External | Historical benchmark indices (S&P500, BTC index) |
| Portfolio Platform | System | Our system - processes data and optimizes portfolios |
| Analyst | User | Runs ad-hoc queries, analyzes data |
| Portfolio Manager | User | Consumes portfolio recommendations |
| Trading System | Future | Will consume API for automated trading |

---

## Level 2: Container Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            PORTFOLIO OPTIMIZATION PLATFORM                               │
│─────────────────────────────────────────────────────────────────────────────────────────│
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              ORCHESTRATION LAYER                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                        Apache Airflow                                        │  │  │
│  │  │                                                                              │  │  │
│  │  │   [Scheduler] ────▶ [Worker] ────▶ [Webserver :8081]                        │  │  │
│  │  │                          │                                                   │  │  │
│  │  │                          ▼                                                   │  │  │
│  │  │                   [PostgreSQL Meta]                                          │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                          │                                              │
│                                          │ triggers                                     │
│                                          ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              PROCESSING LAYER                                      │  │
│  │                                                                                    │  │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │  │
│  │  │   Ingest     │───▶│  Transform   │───▶│   Optimize   │───▶│    Load      │    │  │
│  │  │   (Python)   │    │   (Python)   │    │   (Python)   │    │   (Python)   │    │  │
│  │  │              │    │              │    │              │    │              │    │  │
│  │  │ • API fetch  │    │ • Returns    │    │ • Markowitz  │    │ • DuckDB     │    │  │
│  │  │ • CSV read   │    │ • Volatility │    │ • Scipy      │    │ • JSON out   │    │  │
│  │  │ • Scraping   │    │ • Corr/Cov   │    │ • Weights    │    │              │    │  │
│  │  │ • Postgres   │    │              │    │              │    │              │    │  │
│  │  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    │  │
│  │         │                   │                   │                   │             │  │
│  │         └───────────────────┴───────────────────┴───────────────────┘             │  │
│  │                                         │                                          │  │
│  └─────────────────────────────────────────┼──────────────────────────────────────────┘  │
│                                            │                                             │
│                                            ▼                                             │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              STORAGE LAYER                                         │  │
│  │                                                                                    │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                           DATA LAKE (File System)                            │  │  │
│  │  │  ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐        │  │  │
│  │  │  │  BRONZE   │────▶│  SILVER   │────▶│   GOLD    │     │ REFERENCE │        │  │  │
│  │  │  │ data/raw/ │     │data/proc/ │     │data/output│     │data/ref/  │        │  │  │
│  │  │  │ .parquet  │     │ .parquet  │     │  .json    │     │ .csv/.json│        │  │  │
│  │  │  └───────────┘     └───────────┘     └───────────┘     └───────────┘        │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                                    │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                        DATA WAREHOUSE (DuckDB)                               │  │  │
│  │  │                                                                              │  │  │
│  │  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                     │  │  │
│  │  │  │ fact_prices  │   │  dim_symbol  │   │   dim_date   │                     │  │  │
│  │  │  └──────────────┘   └──────────────┘   └──────────────┘                     │  │  │
│  │  │                      data/warehouse.duckdb                                   │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                                    │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                            │                                             │
│                                            │                                             │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              EXPOSURE LAYER                                        │  │
│  │                                                                                    │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                        FastAPI Application                                   │  │  │
│  │  │                          localhost:8000                                      │  │  │
│  │  │                                                                              │  │  │
│  │  │   GET /symbols    GET /klines/{s}    GET /metrics    GET /portfolio         │  │  │
│  │  │                                                                              │  │  │
│  │  │   ┌────────────────────────────────────────────────────────────────────┐    │  │  │
│  │  │   │  OpenAPI Documentation: /docs (Swagger) | /redoc (ReDoc)           │    │  │  │
│  │  │   └────────────────────────────────────────────────────────────────────┘    │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                                    │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Container Descriptions

| Container | Technology | Purpose |
|-----------|------------|---------|
| Airflow Scheduler | Python/Airflow | Triggers DAG runs on schedule |
| Airflow Webserver | Python/Airflow | Monitoring UI at :8081 |
| Pipeline Workers | Python | Execute ingest/transform/optimize tasks |
| Data Lake | Parquet files | Raw and processed data storage |
| Data Warehouse | DuckDB | Analytical queries on star schema |
| REST API | FastAPI/Uvicorn | Data exposure for consumers |

---

## Level 3: Component Diagram (Pipeline)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              PIPELINE CONTAINER (src/pipeline/)                          │
│─────────────────────────────────────────────────────────────────────────────────────────│
│                                                                                         │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              INGEST COMPONENTS                                      │ │
│  │                                                                                     │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                 │ │
│  │  │  ingest.py       │  │ ingest_scraping  │  │ ingest_postgres  │                 │ │
│  │  │                  │  │      .py         │  │      .py         │                 │ │
│  │  │ • fetch_klines() │  │                  │  │                  │                 │ │
│  │  │ • load_csv()     │  │ • scrape_market  │  │ • load_benchmarks│                 │ │
│  │  │ • load_json()    │  │   _rankings()    │  │ • get_connection │                 │ │
│  │  │ • save_raw()     │  │                  │  │                  │                 │ │
│  │  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘                 │ │
│  │           │                     │                     │                            │ │
│  │           └─────────────────────┼─────────────────────┘                            │ │
│  │                                 │                                                   │ │
│  │                                 ▼                                                   │ │
│  │                    ┌────────────────────────┐                                       │ │
│  │                    │   ingest_sources.py    │                                       │ │
│  │                    │                        │                                       │ │
│  │                    │  ingest_all_sources()  │ ◄── Orchestration entry point        │ │
│  │                    │                        │                                       │ │
│  │                    └────────────┬───────────┘                                       │ │
│  │                                 │                                                   │ │
│  └─────────────────────────────────┼───────────────────────────────────────────────────┘ │
│                                    │                                                     │
│                                    ▼                                                     │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              TRANSFORM COMPONENT                                    │ │
│  │                                                                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │ │
│  │  │                           transform.py                                       │  │ │
│  │  │                                                                              │  │ │
│  │  │  • calculate_log_returns()    • calculate_volatility()                      │  │ │
│  │  │  • calculate_correlation()    • calculate_covariance()                      │  │ │
│  │  │                                                                              │  │ │
│  │  │  ┌────────────────────────────────────────────────────────────────────────┐ │  │ │
│  │  │  │  transform_data() - Main entry point                                   │ │  │ │
│  │  │  │    1. Read raw Parquet from Bronze                                     │ │  │ │
│  │  │  │    2. Calculate all metrics                                            │ │  │ │
│  │  │  │    3. Write processed Parquet to Silver                                │ │  │ │
│  │  │  └────────────────────────────────────────────────────────────────────────┘ │  │ │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                                     │ │
│  └─────────────────────────────────┬───────────────────────────────────────────────────┘ │
│                                    │                                                     │
│                                    ▼                                                     │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              OPTIMIZE COMPONENT                                     │ │
│  │                                                                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │ │
│  │  │                           optimize.py                                        │  │ │
│  │  │                                                                              │  │ │
│  │  │  • portfolio_variance()       • portfolio_return()                          │  │ │
│  │  │  • negative_sharpe()          • optimize_weights()                          │  │ │
│  │  │                                                                              │  │ │
│  │  │  ┌────────────────────────────────────────────────────────────────────────┐ │  │ │
│  │  │  │  optimize_portfolio() - Main entry point                               │ │  │ │
│  │  │  │    1. Read metrics from Silver                                         │ │  │ │
│  │  │  │    2. Run scipy.optimize.minimize (SLSQP)                              │ │  │ │
│  │  │  │    3. Write weights.json to Gold                                       │ │  │ │
│  │  │  └────────────────────────────────────────────────────────────────────────┘ │  │ │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                                     │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Level 3: Component Diagram (Storage)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              STORAGE CONTAINER (src/storage/)                            │
│─────────────────────────────────────────────────────────────────────────────────────────│
│                                                                                         │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              ABSTRACT INTERFACE                                     │ │
│  │                                                                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │ │
│  │  │                           base.py                                            │  │ │
│  │  │                                                                              │  │ │
│  │  │  class StorageAdapter(ABC):                                                  │  │ │
│  │  │      @abstractmethod                                                         │  │ │
│  │  │      def save(data, path) -> None                                           │  │ │
│  │  │      @abstractmethod                                                         │  │ │
│  │  │      def load(path) -> Table                                                │  │ │
│  │  │      @abstractmethod                                                         │  │ │
│  │  │      def query(sql) -> Table                                                │  │ │
│  │  │                                                                              │  │ │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │ │
│  │                                    ▲                                               │ │
│  │                                    │ implements                                    │ │
│  │                    ┌───────────────┴───────────────┐                              │ │
│  │                    │                               │                              │ │
│  │                    ▼                               ▼                              │ │
│  │  ┌─────────────────────────────┐  ┌─────────────────────────────┐                │ │
│  │  │       parquet.py            │  │        duckdb.py            │                │ │
│  │  │                             │  │                             │                │ │
│  │  │  class ParquetStorage:      │  │  class DuckDBStorage:       │                │ │
│  │  │    • save() → .parquet      │  │    • save() → DuckDB table  │                │ │
│  │  │    • load() → Arrow Table   │  │    • load() → Arrow Table   │                │ │
│  │  │    • query() → via DuckDB   │  │    • query() → SQL execute  │                │ │
│  │  │                             │  │                             │                │ │
│  │  │  Used for: Data Lake        │  │  Used for: Data Warehouse   │                │ │
│  │  │  (Bronze/Silver/Gold)       │  │  (Star Schema)              │                │ │
│  │  └─────────────────────────────┘  └─────────────────────────────┘                │ │
│  │                                                                                     │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              CONFIGURATION                                          │ │
│  │                                                                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │ │
│  │  │                           config.py                                          │  │ │
│  │  │                                                                              │  │ │
│  │  │  DATA_DIR = Path("data/")                                                   │  │ │
│  │  │  RAW_DIR = DATA_DIR / "raw"          # Bronze zone                          │  │ │
│  │  │  PROCESSED_DIR = DATA_DIR / "processed"  # Silver zone                      │  │ │
│  │  │  OUTPUT_DIR = DATA_DIR / "output"    # Gold zone                            │  │ │
│  │  │  WAREHOUSE_PATH = DATA_DIR / "warehouse.duckdb"                             │  │ │
│  │  │                                                                              │  │ │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                                     │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
    ┌─────────────────┐
    │  External APIs  │
    │  Binance, etc.  │
    └────────┬────────┘
             │
             │ HTTPS/REST
             ▼
    ┌─────────────────┐         ┌─────────────────┐
    │    ingest.py    │────────▶│  data/raw/      │
    │   (Extract)     │ Parquet │  BRONZE ZONE    │
    └─────────────────┘         └────────┬────────┘
                                         │
                                         │ Read
                                         ▼
    ┌─────────────────┐         ┌─────────────────┐
    │  transform.py   │────────▶│  data/processed/│
    │   (Transform)   │ Parquet │  SILVER ZONE    │
    └─────────────────┘         └────────┬────────┘
                                         │
                                         │ Read
                                         ▼
    ┌─────────────────┐         ┌─────────────────┐
    │   optimize.py   │────────▶│  data/output/   │
    │    (Analyze)    │  JSON   │   GOLD ZONE     │
    └─────────────────┘         └────────┬────────┘
                                         │
                                         │ Load
                                         ▼
                                ┌─────────────────┐
                                │  DuckDB DWH     │
                                │  Star Schema    │
                                └────────┬────────┘
                                         │
                                         │ Query
                                         ▼
                                ┌─────────────────┐
                                │   FastAPI       │
                                │   /portfolio    │
                                └────────┬────────┘
                                         │
                                         │ JSON Response
                                         ▼
                                ┌─────────────────┐
                                │    Consumers    │
                                │  (Analysts, UI) │
                                └─────────────────┘
```

---

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| Orchestration | Apache Airflow 2.7 | DAG scheduling, monitoring |
| Processing | Python 3.11 | ETL logic, optimization |
| Compute | NumPy, SciPy | Matrix operations, SLSQP |
| Storage (Lake) | Apache Parquet | Columnar file storage |
| Storage (DWH) | DuckDB | Embedded OLAP database |
| Serialization | PyArrow | Zero-copy data handling |
| API | FastAPI + Uvicorn | REST endpoints |
| Container | Docker, Compose | Deployment |

---

*Document version: 1.0*
*Last updated: 2025-02-17*
*Author: [Your Name] (Data Engineer)*
