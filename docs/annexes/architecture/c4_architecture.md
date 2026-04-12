# Architecture C4 -- Plateforme d'optimisation de portefeuille

## Presentation

Ce document decrit l'architecture du systeme selon le modele C4 (Context, Containers, Components, Code) de Simon Brown. Il couvre l'ensemble de la plateforme : ingestion multi-sources, pipeline analytique, streaming temps reel, stockage multi-couches, exposition API/dashboard, orchestration et observabilite.

---

## Niveau 1 : Contexte systeme

Le diagramme de contexte identifie les acteurs humains, les systemes externes et les frontieres du systeme.

```
                           SYSTEMES EXTERNES                    
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐     
    │ Binance API   │  │   yfinance    │  │  CoinGecko    │     
    │  (crypto      │  │ (33 actifs    │  │  (scraping    │     
    │   OHLCV)      │  │  trad: ETF,   │  │   rankings    │     
    │               │  │  actions,     │  │   marche)     │     
    │               │  │  matieres     │  │               │     
    │               │  │  premieres)   │  │               │     
    └───────┬───────┘  └───────┬───────┘  └───────┬───────┘     
            │                  │                  │             
    ┌───────┴───────┐  ┌───────┴───────┐  ┌───────┴───────┐     
    │  PostgreSQL   │  │ Fichier CSV   │  │ Fichier JSON  │     
    │ (benchmarks   │  │ (metadonnees  │  │ (config       │     
    │  historiques) │  │  symboles)    │  │  portefeuille)│     
    └───────┬───────┘  └───────┬───────┘  └───────┬───────┘     
            │                  │                  │             
            └──────────────────┼──────────────────┘             
                               │                                
                               ▼                                
    ┌──────────────────────────────────────────────────────────┐
    │                                                          │
    │       PLATEFORME D'OPTIMISATION DE PORTEFEUILLE          │
    │                                                          │
    │   Ingestion multi-sources, transformation, 6 strategies  │
    │   d'optimisation, backtesting, streaming temps reel,     │
    │   analyses de risque avancees, exposition API/dashboard  │
    │                                                          │
    └────────────────────────┬─────────────────────────────────┘
                             │                                  
             ┌───────────────┼───────────────┐                  
             │               │               │                  
             ▼               ▼               ▼                  
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        
    │   Analyste   │  │ Gestionnaire │  │   Equipe     │        
    │  de donnees  │  │     de       │  │   trading    │        
    │  (Sophie     │  │ portefeuille │  │              │        
    │   Bernard)   │  │              │  │              │        
    └──────────────┘  └──────────────┘  └──────────────┘        
            UTILISATEURS                                        
```

### Description du contexte

| Acteur / Systeme | Type | Description |
|---|---|---|
| Binance API | Systeme externe | Donnees OHLCV historiques et temps reel pour les cryptomonnaies (WebSocket + REST) |
| yfinance (Yahoo Finance) | Systeme externe | 33 actifs traditionnels : actions, ETF, matieres premieres, obligations |
| CoinGecko | Systeme externe | Rankings et metadonnees de marche via web scraping |
| PostgreSQL (benchmarks) | Systeme externe | Indices de reference historiques (S&P 500, indice BTC, etc.) |
| Fichier CSV | Source statique | Metadonnees des symboles (`symbols_metadata.csv`) |
| Fichier JSON | Source statique | Configuration du portefeuille (`portfolio_config.json`) |
| Plateforme | Systeme interne | Pipeline ETL, optimisation, backtesting, streaming, exposition |
| Analyste de donnees | Utilisateur | Requetes ad hoc, validation des metriques, exploration du dashboard |
| Gestionnaire de portefeuille | Utilisateur | Consultation des allocations optimales, rapports PDF, signaux |
| Equipe trading | Utilisateur | Signaux de trading, regimes de marche, paires cointegrees |

---

## Niveau 2 : Diagramme de conteneurs

Chaque conteneur correspond a un service Docker (ou groupe de services) deployable independamment.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                      PLATEFORME D'OPTIMISATION DE PORTEFEUILLE                       │
│──────────────────────────────────────────────────────────────────────────────────────│
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │                    COUCHE ORCHESTRATION (profil airflow)                       │  │
│  │                                                                                │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │  │
│  │  │ Scheduler       │  │ Webserver       │  │ PostgreSQL      │                 │  │
│  │  │ (Airflow)       │  │ :8081           │  │ (metadonnees    │                 │  │
│  │  │                 │  │ Interface de    │  │  Airflow)       │                 │  │
│  │  │ 12 taches,      │  │ surveillance    │  │                 │                 │  │
│  │  │ 2 branches      │  │                 │  │                 │                 │  │
│  │  │ paralleles      │  │                 │  │                 │                 │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                 │  │
│  │           │ declenche                                                          │  │
│  └───────────┼────────────────────────────────────────────────────────────────────┘  │
│              │                                                                       │
│              ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │                    COUCHE TRAITEMENT BATCH (profil pipeline)                   │  │
│  │                                                                                │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │  │
│  │  │ Pipeline        │  │ PySpark         │  │     dbt         │                 │  │
│  │  │ (Python)        │  │ (profil         │  │ (dbt-duckdb)    │                 │  │
│  │  │                 │  │  spark)         │  │                 │                 │  │
│  │  │ 40+ modules :   │  │ Correlation     │  │ 6 modeles SQL   │                 │  │
│  │  │ ingest,         │  │ rolling,        │  │ (staging +      │                 │  │
│  │  │ transform,      │  │ volatilite,     │  │  marts)         │                 │  │
│  │  │ optimisation    │  │ volume          │  │                 │                 │  │
│  │  │ (6 strategies)  │  │                 │  │                 │                 │  │
│  │  │ backtest,       │  │                 │  │                 │                 │  │
│  │  │ analytics       │  │                 │  │                 │                 │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                 │  │
│  │           │                                                                    │  │
│  └───────────┼────────────────────────────────────────────────────────────────────┘  │
│              │                                                                       │
│              ▼                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │                 COUCHE STREAMING (profil streaming)                            │  │
│  │                                                                                │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │  │
│  │  │ Redpanda        │  │ stream-producer │  │ stream-consumer │                 │  │
│  │  │ :9092           │  │                 │  │                 │                 │  │
│  │  │ (Kafka          │  │ WebSocket       │  │ Kafka →         │                 │  │
│  │  │  compatible)    │  │ Binance →       │  │ micro-batch     │                 │  │
│  │  │                 │  │ Kafka (klines   │  │ Parquet         │                 │  │
│  │  │ Console :8080   │  │ + order book)   │  │ (Bronze)        │                 │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘                 │  │
│  │                                                                                │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │                       COUCHE STOCKAGE                                          │  │
│  │                                                                                │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐        │  │
│  │  │              DATA LAKE (systeme de fichiers)                       │        │  │
│  │  │                                                                    │        │  │
│  │  │  ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌───────────┐       │        │  │
│  │  │  │  BRONZE  │─▶│  SILVER   │─▶ │   GOLD   │   │ STREAMING │       │        │  │
│  │  │  │ data/raw/│   │  data/    │   │  data/   │   │  data/raw/│       │        │  │
│  │  │  │ .parquet │   │processed/ │   │ output/  │   │ streaming/│       │        │  │
│  │  │  │          │   │ .parquet  │   │ .json    │   │ .parquet  │       │        │  │
│  │  │  └──────────┘   └───────────┘   └──────────┘   └───────────┘       │        │  │
│  │  │                                                                    │        │  │
│  │  │  ┌────────────────────────┐  ┌────────────────────────┐            │        │  │
│  │  │  │ REFERENCE              │  │ Delta Lake (optionnel) │            │        │  │
│  │  │  │ data/reference/        │  │ ACID, time travel      │            │        │  │
│  │  │  │ .csv, .json            │  │ via delta-rs           │            │        │  │
│  │  │  └────────────────────────┘  └────────────────────────┘            │        │  │
│  │  └────────────────────────────────────────────────────────────────────┘        │  │
│  │                                                                                │  │
│  │  ┌────────────────────────────────┐  ┌──────────────────────────────┐          │  │
│  │  │ DATA WAREHOUSE (DuckDB)        │  │ MinIO (optionnel, :9000)     │          │  │
│  │  │                                │  │                              │          │  │
│  │  │ Schema en etoile :             │  │ Stockage S3-compatible       │          │  │
│  │  │ fact_prices, dim_symbol,       │  │ pour objets volumineux       │          │  │
│  │  │ dim_date + dbt models          │  │                              │          │  │
│  │  └────────────────────────────────┘  └──────────────────────────────┘          │  │
│  │                                                                                │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │                       COUCHE EXPOSITION                                        │  │
│  │                                                                                │  │
│  │  ┌──────────────────────────────────┐  ┌──────────────────────────┐            │  │
│  │  │ FastAPI :8000                    │  │ Streamlit :8501          │            │  │
│  │  │                                  │  │                          │            │  │
│  │  │ 45 endpoints REST                │  │ 30 pages interactives    │            │  │
│  │  │ Cache Redis, Pydantic models     │  │ 6 sections : Overview,   │            │  │
│  │  │ OpenAPI /docs + /redoc           │  │ Optimization, Risk,      │            │  │
│  │  │ Metriques Prometheus             │  │ Backtest, Trading, Portf.│            │  │
│  │  └──────────────────────────────────┘  └──────────────────────────┘            │  │
│  │                                                                                │  │
│  │  ┌──────────────────────────────────┐                                          │  │
│  │  │ Redis :6379 (profil cache)       │                                          │  │
│  │  │ Cache TTL pour les reponses API  │                                          │  │
│  │  └──────────────────────────────────┘                                          │  │
│  │                                                                                │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │                 COUCHE OBSERVABILITE (profil monitoring)                       │  │
│  │                                                                                │  │
│  │  ┌──────────────────────────────────┐  ┌──────────────────────────┐            │  │
│  │  │ Prometheus :9090                 │  │ Grafana :3000            │            │  │
│  │  │                                  │  │                          │            │  │
│  │  │ Scrape /prom/metrics             │  │ Dashboards : latence,    │            │  │
│  │  │ Regles d'alerte                  │  │ taux d'erreur, debit API │            │  │
│  │  └──────────────────────────────────┘  └──────────────────────────┘            │  │
│  │                                                                                │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Description des conteneurs

| Conteneur | Technologie | Port | Profil Docker | Role |
|---|---|---|---|---|
| API | FastAPI + Uvicorn | :8000 | default | 45 endpoints REST, cache Redis, metriques Prometheus |
| Dashboard | Streamlit | :8501 | default | 30 pages interactives (6 sections de navigation) |
| Pipeline | Python 3.13 | -- | pipeline | Execution one-shot du batch complet (chargement initial) |
| Scheduler Airflow | Apache Airflow | -- | airflow | Declenchement du DAG selon le planning |
| Webserver Airflow | Apache Airflow | :8081 | airflow | Interface de surveillance et declenchement manuel |
| PostgreSQL (Airflow) | PostgreSQL | -- | airflow | Base de metadonnees Airflow |
| PostgreSQL (benchmarks) | PostgreSQL | :5433 | benchmarks | Indices de reference historiques |
| Redpanda | Redpanda (Kafka) | :9092 | streaming | Broker de messages pour le streaming temps reel |
| Redpanda Console | Redpanda Console | :8080 | streaming | Interface web de surveillance Kafka |
| stream-producer | Python | -- | streaming | WebSocket Binance vers Kafka (klines + order book) |
| stream-consumer | Python | -- | streaming | Kafka vers micro-batch Parquet (zone Bronze) |
| Redis | Redis | :6379 | cache | Cache TTL pour les reponses API |
| MinIO | MinIO | :9000 | storage | Stockage objet S3-compatible (optionnel) |
| PySpark | PySpark (local) | -- | spark | Transformations distribuees (correlation rolling, volatilite) |
| Prometheus | Prometheus | :9090 | monitoring | Collecte de metriques (scrape FastAPI) |
| Grafana | Grafana | :3000 | monitoring | Tableaux de bord d'observabilite (latence, erreurs, debit) |
| DuckDB | DuckDB (embarque) | -- | -- | Entrepot de donnees OLAP, schema en etoile |
| dbt | dbt-duckdb | -- | -- | 6 modeles SQL (staging + marts), tests integres |
| Delta Lake | delta-rs | -- | -- | Stockage ACID avec time travel (optionnel via config) |

---

## Niveau 3 : Diagramme de composants -- Pipeline (`src/pipeline/`)

Le pipeline comporte plus de 40 modules Python organises par fonction.

### Ingestion (6 sources, competence C8)

| Module | Fonction principale | Source |
|---|---|---|
| `ingest.py` | `fetch_klines()`, extraction incrementale | Binance API (REST) |
| `ingest_yfinance.py` | `ingest_yfinance_data()` | Yahoo Finance (33 actifs traditionnels) |
| `ingest_scraping.py` | `scrape_market_rankings()` | CoinGecko (web scraping) |
| `ingest_postgres.py` | `load_benchmarks()` | PostgreSQL (benchmarks) |
| `ingest_sources.py` | `ingest_all_sources()` -- orchestrateur | ABC `DataSource` + 6 implementations |
| `stream_producer.py` | WebSocket Binance vers Kafka | Binance WebSocket (klines + order book depth) |
| `stream_consumer.py` | Kafka vers micro-batch Parquet | Consommateur Kafka (zone Bronze) |

### Transformation et metriques

| Module | Fonction |
|---|---|
| `transform.py` | Rendements logarithmiques, volatilite, correlation, covariance |
| `validation.py` | Validation qualite des donnees (Bronze / Silver / Gold) |
| `data_metrics.py` | Metriques de volume (nombre d'enregistrements, taille, fraicheur) |
| `spark_transforms.py` | Correlation rolling, surface de volatilite, analyse de volume (PySpark) |

### Optimisation (6 strategies)

| Module | Strategie |
|---|---|
| `optimize.py` | Markowitz (maximisation du ratio de Sharpe) + frontiere efficiente |
| `risk_parity.py` | Parite de risque (contribution egale au risque) |
| `black_litterman.py` | Black-Litterman (optimisation bayesienne avec vues) |
| `hrp.py` | Hierarchical Risk Parity (allocation par clustering) |
| `max_diversification.py` | Maximisation du ratio de diversification |
| `min_variance.py` | Portefeuille de variance minimale globale |
| `constrained.py` | Optimisation sous contraintes (poids min/max, groupes) |
| `strategy_compare.py` | Comparaison des 6 strategies cote a cote |

### Backtesting et simulation

| Module | Fonction |
|---|---|
| `backtest.py` | Walk-forward validation, comparaison strategie vs equal-weight vs BTC-only |
| `monte_carlo.py` | Simulation Monte Carlo (VaR, CVaR, fan chart) |
| `combine.py` | Combinaison portefeuille crypto + traditionnel |

### Analyse de risque

| Module | Fonction |
|---|---|
| `var_models.py` | VaR : historique, parametrique, Cornish-Fisher |
| `tail_risk.py` | Moments superieurs (asymetrie, kurtosis, Jarque-Bera, Omega, Calmar) |
| `factor_analysis.py` | Exposition multi-facteurs (marche, momentum, volatilite) |
| `shrinkage.py` | Estimation de covariance Ledoit-Wolf |
| `alpha_beta.py` | Analyse CAPM alpha/beta vs benchmarks |
| `sortino.py` | Ratio de Sortino et risque baissier |
| `stress_test.py` | 5 scenarios de stress + chocs personnalises |
| `drawdown.py` | Analyse des drawdowns, periodes et reprise |

### Trading et signaux

| Module | Fonction |
|---|---|
| `signals.py` | Signaux : croisement SMA, RSI, MACD, bandes de Bollinger |
| `regime.py` | Detection de regime de marche (haussier / baissier / lateral) |
| `pairs.py` | Trading de paires, cointegration Engle-Granger, z-score |
| `position_sizing.py` | Dimensionnement : Kelly, cible de volatilite, fraction fixe |
| `costs.py` | Modele de couts de transaction (frais, slippage, rendements nets) |

### Analyses de portefeuille

| Module | Fonction |
|---|---|
| `attribution.py` | Attribution de performance (poids x rendement) |
| `rebalance.py` | Alertes de reequilibrage et suggestions de transactions |
| `decay.py` | Derive des poids du portefeuille dans le temps |
| `evaluate.py` | Evaluation personnalisee (poids definis par l'utilisateur) |
| `live_prices.py` | Cours en temps reel (Binance + yfinance) |
| `pdf_export.py` | Generation de rapports PDF (fpdf2) |

---

## Niveau 3 : Diagramme de composants -- Stockage (`src/storage/`)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              STORAGE (src/storage/)                              │
│──────────────────────────────────────────────────────────────────────────────────│
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                   Interface abstraite (base.py)                            │  │
│  │                                                                            │  │
│  │  class StorageAdapter(ABC):                                                │  │
│  │      save(data, path) -> None                                              │  │
│  │      load(path) -> Table                                                   │  │
│  │      query(sql) -> Table                                                   │  │
│  │                                                                            │  │
│  │  get_storage(backend) -> StorageAdapter    # Factory + registre            │  │
│  └──────────────────────────────┬─────────────────────────────────────────────┘  │
│                                 │ implemente                                     │
│             ┌───────────────────┼───────────────────┐                            │
│             │                   │                   │                            │
│             ▼                   ▼                   ▼                            │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐                  │
│  │  parquet.py      │ │   duckdb.py      │ │   delta.py       │                  │
│  │                  │ │                  │ │                  │                  │
│  │ ParquetStorage   │ │ DuckDBStorage    │ │ DeltaStorage     │                  │
│  │                  │ │                  │ │                  │                  │
│  │ Data Lake :      │ │ Data Warehouse : │ │ Delta Lake :     │                  │
│  │ Bronze/Silver/   │ │ schema en etoile │ │ ACID, time       │                  │
│  │ Gold zones       │ │ fact_prices,     │ │ travel, schema   │                  │
│  │ (fichiers        │ │ dim_symbol,      │ │ enforcement      │                  │
│  │  Parquet)        │ │ dim_date         │ │ (optionnel)      │                  │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘                  │
│             │                                                                    │
│             ▼                                                                    │
│  ┌──────────────────┐                                                            │
│  │   minio.py       │                                                            │
│  │                  │                                                            │
│  │ MinIOStorage     │                                                            │
│  │                  │                                                            │
│  │ S3-compatible,   │                                                            │
│  │ objets           │                                                            │
│  │ volumineux       │                                                            │
│  │ (optionnel)      │                                                            │
│  └──────────────────┘                                                            │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                   Configuration (config.py)                                │  │
│  │                                                                            │  │
│  │  PipelineConfig (frozen dataclass) via load_config()                       │  │
│  │  Chemins : data_dir, raw_dir, processed_dir, output_dir                    │  │
│  │  Source : TOML + variables d'environnement (layering)                      │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Niveau 3 : Diagramme de composants -- API (`src/api/`)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                  API (src/api/)                                  │
│──────────────────────────────────────────────────────────────────────────────────│
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                   main.py -- FastAPI Application                           │  │
│  │                                                                            │  │
│  │  45 endpoints (44 GET + 1 POST) organises en groupes :                     │  │
│  │                                                                            │  │
│  │  General (5)       /  /symbols  /klines/{s}  /metrics  /metrics/{n}        │  │
│  │                                                                            │  │
│  │  Portefeuille (7)  /portfolio  /portfolio/summary  /portfolio/frontier     │  │
│  │                    /portfolio/backtest  /portfolio/trad                    │  │
│  │                    /portfolio/trad/frontier  /portfolio/trad/backtest      │  │
│  │                                                                            │  │
│  │  Analyse (14)      /portfolio/monte-carlo  /portfolio/rolling-correl.      │  │
│  │                    /portfolio/risk-contribution  /portfolio/combined       │  │
│  │                    /portfolio/rebalance  /portfolio/signals                │  │
│  │                    /portfolio/risk-parity  /portfolio/position-sizing      │  │
│  │                    /portfolio/cost-analysis  /portfolio/alpha-beta         │  │
│  │                    /portfolio/regime  /portfolio/sortino                   │  │
│  │                    /portfolio/factors  /portfolio/tail-risk                │  │
│  │                                                                            │  │
│  │  Optimisation (7)  /portfolio/constrained (POST)                           │  │
│  │                    /portfolio/black-litterman  /portfolio/hrp              │  │
│  │                    /portfolio/var  /portfolio/shrinkage                    │  │
│  │                    /portfolio/max-diversification  /portfolio/min-var      │  │
│  │                                                                            │  │
│  │  Avance (7)        /portfolio/decay  /portfolio/pairs                      │  │
│  │                    /portfolio/compare-strategies                           │  │
│  │                    /portfolio/backtest/multi                               │  │
│  │                    /portfolio/custom (POST)  /portfolio/report             │  │
│  │                    /portfolio/stress-test  /portfolio/scenarios            │  │
│  │                                                                            │  │
│  │  Donnees (3)       /portfolio/drawdown  /portfolio/attribution             │  │
│  │                    /data/metrics                                           │  │
│  │                                                                            │  │
│  │  Monitoring (1)    /prom/metrics (Prometheus)                              │  │
│  │                                                                            │  │
│  │  Documentation     /docs (Swagger)  /redoc (ReDoc)                         │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐          │
│  │   schemas.py       │  │    cache.py        │  │   metrics.py       │          │
│  │                    │  │                    │  │                    │          │
│  │ Modeles Pydantic   │  │ Decorateur Redis   │  │ Metriques          │          │
│  │ de reponse pour    │  │ avec TTL           │  │ Prometheus         │          │
│  │ tous les endpoints │  │                    │  │ metier             │          │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘          │
│                                                                                  │
│  Injection de dependances : Storage via Depends(get_storage_dep)                 │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Diagramme de flux de donnees

Trois chemins de donnees coexistent : batch crypto, batch traditionnel, et streaming temps reel.

```
  ┌─────────────────────────────────────────────────────────────────────┐      
  │                     CHEMINS D'INGESTION                             │      
  └─────────────────────────────────────────────────────────────────────┘      
                                                                               
  BATCH CRYPTO                    BATCH TRADITIONNEL         STREAMING         
  ─────────────                   ──────────────────         ─────────         
  Binance API ─┐                  yfinance ─────────┐       Binance WebSocket  
  CoinGecko ───┤                                    │           │              
  CSV ─────────┤  ingest_sources.py                 │       stream_producer.py 
  JSON ────────┤  (orchestrateur)                   │           │              
  PostgreSQL ──┘       │                            │       Redpanda (Kafka)   
                       │                            │       :9092              
                       ▼                            ▼           │              
              ┌──────────────┐             ┌──────────────┐     │              
              │   BRONZE     │             │   BRONZE     │     ▼              
              │  data/raw/   │             │  data/raw/   │  stream_consumer.py
              │  klines/     │             │  yfinance/   │     │              
              │  .parquet    │             │  .parquet    │     ▼              
              └──────┬───────┘             └──────┬───────┘  ┌──────────────┐  
                     │                            │          │   BRONZE     │  
                     │                            │          │  data/raw/   │  
                     │                            │          │  streaming/  │  
                     │                            │          │  .parquet    │  
                     │                            │          └──────────────┘  
                     ▼                            ▼                            
              ┌──────────────┐             ┌──────────────┐                    
              │  transform   │             │  transform   │                    
              │  _data()     │             │  _yfinance   │                    
              │              │             │  _data()     │                    
              └──────┬───────┘             └──────┬───────┘                    
                     │                            │                            
                     ▼                            ▼                            
              ┌──────────────┐             ┌──────────────┐                    
              │   SILVER     │             │   SILVER     │                    
              │  data/       │             │  data/       │                    
              │  processed/  │             │  processed/  │                    
              │  returns,    │             │  trad_       │                    
              │  vol, corr,  │             │  returns,    │                    
              │  cov         │             │  vol, corr   │                    
              └──────┬───────┘             └──────┬───────┘                    
                     │                            │                            
                     ▼                            ▼                            
              ┌──────────────┐             ┌──────────────┐                    
              │  optimize +  │             │  optimize +  │                    
              │  frontier +  │             │  frontier +  │                    
              │  backtest    │             │  backtest    │                    
              │  (crypto)    │             │  (trad)      │                    
              └──────┬───────┘             └──────┬───────┘                    
                     │                            │                            
                     └──────────┬─────────────────┘                            
                                │                                              
                                ▼                                              
                     ┌────────────────────┐                                    
                     │       GOLD         │                                    
                     │   data/output/     │                                    
                     │                    │                                    
                     │  weights.json      │                                    
                     │  frontier.json     │                                    
                     │  backtest.json     │                                    
                     │  monte_carlo.json  │                                    
                     │  (+ equivalents    │                                    
                     │   trad)            │                                    
                     └─────────┬──────────┘                                    
                               │                                               
                    ┌──────────┼──────────┐                                    
                    │          │          │                                    
                    ▼          ▼          ▼                                    
             ┌──────────┐ ┌────────┐ ┌──────────┐                              
             │  DuckDB  │ │FastAPI │ │Streamlit │                              
             │   DWH    │ │ :8000  │ │  :8501   │                              
             │  schema  │ │        │ │          │                              
             │  etoile  │ │ 45 end-│ │ 30 pages │                              
             │  + dbt   │ │ points │ │          │                              
             └──────────┘ └───┬────┘ └──────────┘                              
                              │                                                
                    ┌─────────┼─────────┐                                      
                    │         │         │                                      
                    ▼         ▼         ▼                                      
              ┌──────────┐ ┌──────┐ ┌──────────┐                               
              │ Analyste │ │Gest. │ │  Equipe  │                               
              │          │ │portf.│ │ trading  │                               
              └──────────┘ └──────┘ └──────────┘                               
```

---

## Orchestration Airflow -- DAG `portfolio_dag`

Le DAG comporte 12 taches organisees en deux branches paralleles (crypto et traditionnel), suivies de taches de consolidation.

```
                    ┌──────────────────────┐                
                    │    ingest_crypto     │                
                    └──────────┬───────────┘                
                               │                            
                    ┌──────────┴───────────┐                
                    │  transform_crypto    │                
                    └──────────┬───────────┘                
                               │                            
                    ┌──────────┴───────────┐                
                    │   optimize_crypto    │                
                    └──────────┬───────────┘                
                               │                            
                    ┌──────────┴───────────┐            
                    │   frontier_crypto    │                
                    └──────────┬───────────┘                
                               │                            
                    ┌──────────┴───────────┐                
                    │   backtest_crypto    │                
                    └──────────┬───────────┘                
                               │                            
              ┌────────────────┼────────────────┐           
              │                                 │           
   ┌──────────┴──────────┐           ┌──────────┴──────────┐
   │    monte_carlo      │           │      dbt_run        │
   └─────────────────────┘           └─────────────────────┘
                                                            
                                                            
  (branche parallele)                                       
                                                            
                    ┌──────────────────────┐                
                    │    ingest_trad       │                
                    └──────────┬───────────┘                
                               │                            
                    ┌──────────┴───────────┐                
                    │   transform_trad     │                
                    └──────────┬───────────┘                
                               │                            
                    ┌──────────┴───────────┐                
                    │    optimize_trad     │                
                    └──────────┬───────────┘                
                               │                            
                    ┌──────────┴───────────┐                
                    │   frontier_trad      │                
                    └──────────┬───────────┘                
                               │                            
                    ┌──────────┴───────────┐                
                    │   backtest_trad      │                
                    └──────────┬───────────┘                
```

Les deux branches s'executent en parallele. Les taches `monte_carlo` et `dbt_run` se declenchent apres la fin de la branche crypto.

---

## Resume de la pile technologique

| Couche | Technologie | Role |
|---|---|---|
| **Orchestration** | Apache Airflow 2.x | Planification du DAG (12 taches), surveillance, declenchement |
| **Traitement batch** | Python 3.13+, PyArrow, SciPy | 40+ modules pipeline (ETL, optimisation, analytics) |
| **Traitement distribue** | PySpark (local) | Correlation rolling, surface de volatilite, analyse de volume |
| **Transformations SQL** | dbt-duckdb | 6 modeles (staging + marts), tests integres, lineage |
| **Streaming** | Redpanda (Kafka-compatible) | Ingestion temps reel via WebSocket Binance |
| **Data Lake** | Apache Parquet | Stockage en colonnes, compresse (Bronze / Silver / Gold) |
| **Data Lake (option)** | Delta Lake (delta-rs) | Transactions ACID, time travel, schema enforcement |
| **Data Warehouse** | DuckDB | Base OLAP embarquee, schema en etoile |
| **Stockage objet** | MinIO (S3-compatible) | Stockage d'objets volumineux (optionnel) |
| **Cache** | Redis | Cache TTL pour les reponses API |
| **API** | FastAPI + Uvicorn | 45 endpoints REST, injection Depends(), modeles Pydantic |
| **Dashboard** | Streamlit | 30 pages interactives, graphiques Plotly |
| **Monitoring** | Prometheus + Grafana | Metriques, alertes, tableaux de bord d'observabilite |
| **Conteneurisation** | Docker, Docker Compose | 16 services, 8 profils |
| **CI/CD** | GitHub Actions | Tests, lint (ruff), type-check (mypy) |
| **Serialisation** | PyArrow (pas de pandas) | Manipulation memoire efficace, typage strict (ADR-003) |

---

## Profils Docker Compose

| Profil | Services | Usage |
|---|---|---|
| *(default)* | api, streamlit | Services de base : API + dashboard |
| `pipeline` | pipeline | Chargement initial one-shot (batch complet) |
| `airflow` | webserver, scheduler, postgres, airflow-init | Orchestration planifiee |
| `streaming` | redpanda, redpanda-init, stream-producer, stream-consumer, redpanda-console | Ingestion temps reel |
| `monitoring` | prometheus, grafana | Observabilite |
| `benchmarks` | postgres-benchmarks | Indices de reference historiques |
| `cache` | redis | Cache API |
| `storage` | minio | Stockage S3-compatible |
| `spark` | spark | Transformations PySpark |
| `full` | Tous les profils ci-dessus | Stack complete |

---

## Decisions d'architecture (ADR)

| Decision | Justification | Reference |
|---|---|---|
| Stockage Parquet | Format en colonnes, compresse, schema auto-descriptif | ADR-001 |
| DuckDB pour le DWH | OLAP embarque, pas de serveur, integration PyArrow native | ADR-002 |
| PyArrow sans pandas | Memoire efficace, typage strict, zero copie | ADR-003 |
| FastAPI pour l'exposition | Documentation OpenAPI automatique, asynchrone, injection | ADR-004 |
| Airflow pour l'orchestration | Standard industriel, DAG declaratifs, surveillance integree | ADR-005 |
| Delta Lake | Transactions ACID, time travel, schema enforcement | ADR-006 |
| dbt-duckdb | Transformations SQL testables, lineage, documentation | ADR-007 |
| Redpanda (Kafka) | Streaming temps reel, decouplage producteur/consommateur | -- |
| Prometheus + Grafana | Observabilite standard, alertes configurables | -- |
| Streamlit | Prototypage rapide, graphiques Plotly, Python natif | -- |

---

*Version du document : 2.0*
*Derniere mise a jour : 2026-04-09*
*Auteur : Laien Wu (ingenieur de donnees)*
