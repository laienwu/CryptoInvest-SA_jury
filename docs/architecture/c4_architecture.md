# Modèle d'architecture C4

## Présentation

Ce document présente l'architecture du système à l'aide du modèle C4 (Contexte, Conteneurs, Composants, Code).

---

## Niveau 1 : Système Contexte

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

### Description du contexte

| Acteur/Système | Tapez | Description |
|--------------|------|-------------|
| API Binance | Externe | Fournit des données historiques et en temps réel sur les prix des OHLCV |
| CoinGecko | Externe | Classements de marché et métadonnées via le web scraping |
| Base de données de référence | Externe | Indices de référence historiques (S&P500, indice BTC) |
| Plateforme de portefeuille | Système | Notre système - traite les données et optimise les portefeuilles |
| Analyste | Utilisateur | Exécute des requêtes ad hoc, analyse les données |
| Gestionnaire de portefeuille | Utilisateur | Consomme les recommandations de portefeuille |
| Système commercial | Avenir | Consommera l'API pour le trading automatisé |

---

## Niveau 2 : Diagramme de conteneur

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
│  │  │   GET /symbols  GET /klines/{s}  GET /metrics  GET /portfolio              │  │  │
│  │  │   GET /portfolio/frontier       GET /portfolio/backtest                   │  │  │
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

### Descriptions des conteneurs

| Conteneur | Technologie | Objectif |
|-----------|------------|---------|
| Planificateur de flux d'air | Python/Flux d'air | Déclencheurs DAG s'exécute selon le calendrier |
| Serveur Web Airflow | Python/Flux d'air | Surveillance de l'interface utilisateur à : 8081 |
| Travailleurs des pipelines | Python | Exécuter des tâches d'ingestion/de transformation/d'optimisation |
| Lac de données | Limes pour parquet | Stockage des données brutes et traitées |
| Entrepôt de données | CanardDB | Requêtes analytiques sur schéma en étoile |
| API REST | FastAPI/Uvicorn | Exposition des données pour les consommateurs |

---

## Niveau 3 : diagramme de composants (pipeline)

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
│  │  │  • compute_efficient_frontier()  • _optimize_for_target_return()           │  │ │
│  │  │                                                                              │  │ │
│  │  │  ┌────────────────────────────────────────────────────────────────────────┐ │  │ │
│  │  │  │  optimize_portfolio() - Max Sharpe weights → weights.json             │ │  │ │
│  │  │  │  compute_and_save_frontier() - Efficient frontier → frontier.json     │ │  │ │
│  │  │  └────────────────────────────────────────────────────────────────────────┘ │  │ │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                                     │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│                                    │                                                     │
│                                    ▼                                                     │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              BACKTEST COMPONENT                                     │ │
│  │                                                                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │ │
│  │  │                           backtest.py                                        │  │ │
│  │  │                                                                              │  │ │
│  │  │  • _create_rolling_windows()     • _optimize_on_window()                   │  │ │
│  │  │  • _compute_portfolio_daily_returns()  • _compute_metrics()                │  │ │
│  │  │  • _cumulative_values()          • _max_drawdown()                          │  │ │
│  │  │                                                                              │  │ │
│  │  │  ┌────────────────────────────────────────────────────────────────────────┐ │  │ │
│  │  │  │  run_backtest() - Walk-forward validation → backtest.json             │ │  │ │
│  │  │  │    Train on window → optimize → test on next window → repeat          │ │  │ │
│  │  │  │    Compare: strategy vs equal-weight vs BTC-only                      │ │  │ │
│  │  │  └────────────────────────────────────────────────────────────────────────┘ │  │ │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                                     │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Niveau 3 : Diagramme de composants (stockage)

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

## Diagramme de flux de données

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
    │  (Optimize)     │  JSON   │   GOLD ZONE     │
    │  • weights.json │         │                 │
    │  • frontier.json│         │                 │
    └─────────────────┘         └────────┬────────┘
                                         │
    ┌─────────────────┐                  │
    │  backtest.py    │──── JSON ────────┤
    │  (Backtest)     │                  │
    │  • backtest.json│                  │
    └─────────────────┘                  │
          ▲                              │
          │ Read raw                     │ Load
          │ (Bronze)                     ▼
          │                     ┌─────────────────┐
          │                     │  DuckDB DWH     │
          │                     │  Star Schema    │
          │                     └────────┬────────┘
          │                              │
          │                              │ Query
          │                              ▼
          │                     ┌─────────────────┐
          │                     │   FastAPI       │
          │                     │  /portfolio     │
          │                     │  /portfolio/    │
          │                     │    frontier     │
          │                     │  /portfolio/    │
          │                     │    backtest     │
          │                     └────────┬────────┘
                                         │
                                         │ JSON Response
                                         ▼
                                ┌─────────────────┐
                                │    Consumers    │
                                │  (Analysts, UI) │
                                └─────────────────┘
```

---

## Résumé de la pile technologique

| Couche | Technologie | Objectif |
|-------|------------|---------|
| Orchestration | Apache Airflow 2.7 | Planification et surveillance DAG |
| Traitement | Python3.11 | Logique ETL, optimisation |
| Calculer | PyArrow, SciPy (facultatif) | Opérations matricielles, SLSQP (repli de recherche dans la grille) |
| Stockage (Lac) | Parquet Apache | Stockage de fichiers en colonnes |
| Stockage (ECS) | CanardDB | Base de données OLAP intégrée |
| Sérialisation | PyArrow | Gestion des données sans copie |
| API | FastAPI + Uvicorne | Points de terminaison REST |
| Conteneur | Docker, Composer | Déploiement |

---

*Version du document : 1.1*
*Dernière mise à jour : 2025-02-17*
*Auteur : Laien Wu (ingénieur de données)*

