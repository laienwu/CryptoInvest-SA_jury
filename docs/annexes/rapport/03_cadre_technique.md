# Cadre Technique d'Exploitation (C3)

## 1. Analyse fonctionnelle

### 1.1 Que fait le systeme ?

Le systeme **Portfolio Optimization Platform** realise les fonctions suivantes :

1. **Collecte multi-source** : extraction automatisee depuis 6 sources (API Binance, CSV, JSON, scraping CoinGecko, PostgreSQL, yfinance) ainsi qu'un flux temps reel via WebSocket Binance
2. **Stockage en Data Lake** : organisation Bronze / Silver / Gold en fichiers Parquet (backend par defaut), avec Delta Lake optionnel pour les garanties ACID
3. **Transformation** : calcul de metriques financieres (rendements, volatilite, correlation, covariance) via PyArrow et dbt-duckdb (transforms SQL)
4. **Entrepot de donnees** : schema en etoile (fact_prices, dim_symbol, dim_date) dans DuckDB
5. **Optimisation de portefeuille** : 6 strategies (Markowitz, Risk Parity, HRP, Black-Litterman, Max Diversification, Min Variance)
6. **Backtesting** : walk-forward multi-strategy avec analyse Monte Carlo, stress test, drawdown, attribution
7. **Exposition** : API REST FastAPI (46 endpoints) et tableau de bord Streamlit (32 pages)
8. **Streaming** : ingestion temps reel via Kafka (Redpanda) pour klines et carnet d'ordres
9. **Orchestration** : DAG Airflow (12 taches, branches crypto + traditionnelle, integration dbt)
10. **Observabilite** : metriques Prometheus + tableaux de bord Grafana

### 1.2 Contraintes metiers

| Contrainte | Impact sur l'architecture |
|------------|---------------------------|
| Budget limite | Solutions open-source exclusivement (pas de licence) |
| Pas d'infrastructure cloud | Deploiement local via Docker Compose |
| Equipe reduite (1 personne) | Architecture modulaire, maintenable, bien documentee |
| Donnees publiques uniquement | Pas de chiffrement au repos, pas de PII |
| Volume modere (<100 symboles) | PySpark en mode local suffit, pas de cluster distribue |

---

## 2. Besoins non-fonctionnels

| Besoin | Exigence | Solution retenue |
|--------|----------|------------------|
| **Performance** | Traitement < 2 min pour 10 symboles, 6 strategies | DuckDB (OLAP) + Parquet (columnar) + PyArrow (zero-copy) |
| **Disponibilite** | 99% (non critique, usage interne) | Docker `restart: unless-stopped`, healthchecks sur chaque service |
| **Scalabilite** | Jusqu'a 100 symboles, ajout de backends | Storage ABC + factory (Parquet, DuckDB, Delta, MinIO), profils Docker |
| **Maintenabilite** | Code lisible, testable, type-safe | Python 3.13, typing strict (mypy), 748 tests, ruff linting |
| **Portabilite** | Deployable sur tout OS | Docker Compose, pas de dependance systeme hors Docker |
| **Observabilite** | Metriques API et pipeline | Prometheus scrape, Grafana dashboards, alertes (latence, erreurs) |
| **Securite** | Variables sensibles externalisees | `.env` + Docker secrets, pas de mot de passe dans le code |
| **Temps reel** | Ingestion streaming optionnelle | Kafka (Redpanda) + WebSocket Binance, micro-batch vers Bronze |

---

## 3. Representation fonctionnelle

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                       PORTFOLIO OPTIMIZATION PLATFORM                              │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                           SOURCES (C8 — 6 types)                             │  │
│  │  [Binance API] [CSV] [JSON] [Scraping] [PostgreSQL] [yfinance]               │  │
│  │               + [WebSocket Binance → Kafka temps reel]                       │  │
│  └────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                   │                                                │
│                                   ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                         DATA LAKE (Bronze → Silver → Gold)                   │  │
│  │  ┌──────────┐   ┌──────────────┐   ┌──────────┐                              │  │
│  │  │ BRONZE   │──▶│    SILVER    │──▶│  GOLD    │                              │  │
│  │  │ (raw/)   │   │ (processed/) │   │(output/) │                              │  │
│  │  │ Parquet  │   │ Returns/Vol  │   │ Weights  │                              │  │
│  │  └──────────┘   │ Corr/Cov     │   │ Frontier │                              │  │
│  │                 └──────────────┘   │ Backtest │                              │  │
│  │                                    └──────────┘                              │  │
│  └────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                   │                                                │
│                                   ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                 DATA WAREHOUSE — DuckDB (schema etoile)                      │  │
│  │  [fact_prices]  [dim_symbol]  [dim_date]  + dbt models                       │  │
│  └────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                   │                                                │
│               ┌───────────────────┼───────────────────┐                            │
│               ▼                   ▼                   ▼                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                  │
│  │  API REST (C12)  │  │ Dashboard (C12)  │  │  PDF Export      │                  │
│  │  FastAPI :8000   │  │ Streamlit :8501  │  │  fpdf2 rapports  │                  │
│  │  46 endpoints    │  │  32 pages        │  │                  │                  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘                  │
│                                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                        ORCHESTRATION + MONITORING                            │  │
│  │  Airflow DAG (12 taches) │ Prometheus :9090 │ Grafana :3000                  │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Representation applicative

### 4.1 Composants logiciels

| Composant | Technologie | Role |
|-----------|-------------|------|
| **Ingestion batch** | Python + httpx, yfinance, BeautifulSoup | Extraction multi-source (6 types) |
| **Ingestion streaming** | Binance WebSocket + kafka-python | Klines + order book temps reel |
| **Transformation Python** | PyArrow (pas de pandas — ADR-003) | Rendements, volatilite, correlation, covariance |
| **Transformation SQL** | dbt-duckdb (ADR-007) | Staging, faits, dimensions, aggregats |
| **Optimisation** | scipy.optimize + numpy | 6 strategies (Markowitz, HRP, BL, RP, MaxDiv, MinVar) |
| **Backtesting** | Python pur | Walk-forward, Monte Carlo, stress test, drawdown |
| **Stockage Lake** | PyArrow Parquet (ADR-001) | Bronze / Silver / Gold |
| **Stockage Delta** | delta-rs (ADR-006) | ACID, time travel (backend optionnel) |
| **Entrepot** | DuckDB (ADR-002) | Star schema SQL, OLAP analytique |
| **API REST** | FastAPI (ADR-004) + Pydantic | 46 endpoints, Depends() injection, OpenAPI auto |
| **Cache API** | Redis | TTL configurable, decorateur cache |
| **Dashboard** | Streamlit + Plotly | 32 pages interactives |
| **Orchestration** | Airflow (ADR-005) | DAG quotidien, 12 taches, 2 branches |
| **Message broker** | Redpanda (Kafka-compatible) | Streaming decoupled, topics partitionnes |
| **Metriques** | prometheus-client | Compteurs, histogrammes metier |
| **Tableaux de bord ops** | Grafana | Dashboards API (taux, latence, erreurs) |
| **Transforms distribues** | PySpark (mode local) | Rolling correlation, volatility surface, volume |
| **Object storage** | MinIO (S3-compatible) | Backend optionnel cloud-native |

### 4.2 Matrice des flux applicatifs

| # | Source | Cible | Protocole | Port | Donnees | Frequence |
|---|--------|-------|-----------|------|---------|-----------|
| F1 | ingest.py | Binance API | HTTPS | 443 | JSON klines OHLCV | Quotidien (Airflow) |
| F2 | ingest_yfinance.py | Yahoo Finance | HTTPS | 443 | JSON prix actions/ETF | Quotidien (Airflow) |
| F3 | ingest_scraping.py | CoinGecko | HTTPS | 443 | HTML scrape marketcap | Quotidien |
| F4 | ingest_postgres.py | postgres-benchmarks | TCP | 5432 | SQL benchmarks | A la demande |
| F5 | ingest_sources.py | CSV/JSON locaux | Filesystem | — | Fichiers reference | Au bootstrap |
| F6 | stream_producer | Binance WebSocket | WSS | 443 | Klines + order book | Continu |
| F7 | stream_producer | Redpanda | TCP (Kafka) | 9092 | Messages klines-raw | Continu |
| F8 | stream_consumer | Redpanda | TCP (Kafka) | 9092 | Consommation micro-batch | Continu |
| F9 | Pipeline Python | data/ (Parquet) | Filesystem | — | Bronze/Silver/Gold | Par etape |
| F10 | dbt-duckdb | DuckDB warehouse | In-process | — | SQL transforms | Quotidien (Airflow) |
| F11 | FastAPI | Storage (Parquet/DuckDB) | In-process | — | Lecture donnees | A chaque requete |
| F12 | FastAPI | Redis | TCP | 6379 | Cache reponses | A chaque requete |
| F13 | Streamlit | FastAPI | HTTP | 8000 | JSON API responses | Interaction utilisateur |
| F14 | Client externe | FastAPI | HTTP | 8000 | JSON REST | A la demande |
| F15 | Prometheus | FastAPI /prom/metrics | HTTP | 8000 | Metriques Prometheus | Toutes les 15s |
| F16 | Grafana | Prometheus | HTTP | 9090 | PromQL queries | Continue |
| F17 | Airflow | Pipeline Python | Subprocess | — | Taches DAG | Quotidien 00:00 |
| F18 | Airflow | PostgreSQL metadata | TCP | 5432 | State DAG/tasks | Continue |

### 4.3 Diagramme des flux

```
                            ┌───────────────────┐
                            │  Sources externes │
                            │  Binance, Yahoo,  │
                            │  CoinGecko, PG    │
                            └────────┬──────────┘
                                     │ F1-F6 (HTTPS/WSS/TCP)
                                     ▼
┌─────────┐  F7   ┌──────────┐  F8  ┌───────────────┐  F9  ┌──────────┐
│WebSocket│─────▶│ Redpanda │────▶│ Consumer      │─────▶│ Bronze   │
│Producer │       │ (Kafka)  │      │ (micro-batch) │      │ data/raw │
└─────────┘       └──────────┘      └───────────────┘      └────┬─────┘
                                                                │
┌─────────────────────────────────────────────┐                 │ F9
│         Airflow DAG (F17)                   │                 ▼
│  ingest → transform → optimize → backtest   │           ┌──────────┐
│  crypto branch + trad branch + dbt_run      │           │ Silver   │
└─────────────────────────────────────────────┘           │processed │
                                                          └────┬─────┘
          ┌──────────────────────────────────┐                 │ F9
          │  dbt-duckdb (F10)                │                 ▼
          │  stg_klines → fact_prices        │           ┌──────────┐
          │  dim_symbol, dim_date            │           │  Gold    │
          └──────────────┬───────────────────┘           │ output   │
                         │                               └────┬─────┘
                         ▼                                    │
                   ┌──────────┐           ┌───────────┐       │ F11
                   │  DuckDB  │◀──────────│  FastAPI  │◀──────┘
                   │  (DWH)   │   F11     │  :8000    │
                   └──────────┘           └─────┬─────┘
                                                │ F13, F14, F15
                              ┌─────────────────┼─────────────────┐
                              ▼                 ▼                 ▼
                        ┌──────────┐     ┌──────────┐     ┌──────────┐
                        │Streamlit │     │ Client   │     │Prometheus│
                        │ :8501    │     │ externe  │     │ :9090    │
                        └──────────┘     └──────────┘     └────┬─────┘
                                                               │ F16
                                                               ▼
                                                         ┌──────────┐
                                                         │ Grafana  │
                                                         │ :3000    │
                                                         └──────────┘
```

---

## 5. Representation d'infrastructure

### 5.1 Architecture Docker Compose

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Docker Host                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─── Defaut (pas de profil) ───────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  ┌──────────────────┐       ┌──────────────────┐                     │    │
│  │  │  api (FastAPI)   │◀───── │  streamlit       │                     │    │
│  │  │  Port 8000       │       │  Port 8501       │                     │    │
│  │  │  healthcheck     │       │  healthcheck     │                     │    │
│  │  └──────────────────┘       └──────────────────┘                     │    │
│  │                                                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─── Profil: pipeline ──────┐   ┌─── Profil: airflow ─────────────────┐     │
│  │                           │   │                                     │     │
│  │  ┌─────────────────────┐  │   │  ┌────────────────┐  ┌────────────┐ │     │
│  │  │  pipeline (one-shot)│  │   │  │ airflow-       │  │ airflow-   │ │     │
│  │  │  bootstrap.py       │  │   │  │ webserver      │  │ scheduler  │ │     │
│  │  └─────────────────────┘  │   │  │ Port 8081      │  │            │ │     │
│  │                           │   │  └───────┬────────┘  └─────┬──────┘ │     │
│  └───────────────────────────┘   │          │                 │        │     │
│                                  │          └────────┬────────┘        │     │
│                                  │                   ▼                 │     │
│                                  │         ┌────────────────┐          │     │
│                                  │         │ postgres       │          │     │
│                                  │         │ (metadata)     │          │     │
│                                  │         │ Port 5432      │          │     │
│                                  │         └────────────────┘          │     │
│                                  └─────────────────────────────────────┘     │
│                                                                              │
│  ┌─── Profil: streaming ────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │    │
│  │  │ redpanda     │  │ stream-      │  │ stream-      │                │    │
│  │  │ (Kafka)      │  │ producer     │  │ consumer     │                │    │
│  │  │ Port 19092   │  │              │  │              │                │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                │    │
│  │  ┌──────────────┐                                                    │    │
│  │  │ redpanda-    │                                                    │    │
│  │  │ console      │                                                    │    │
│  │  │ Port 8080    │                                                    │    │
│  │  └──────────────┘                                                    │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─── Profil: monitoring ──────────────┐   ┌─── Profils optionnels ─────┐    │
│  │                                     │   │                            │    │
│  │  ┌──────────────┐  ┌──────────────┐ │   │  ┌─────────────────────┐   │    │
│  │  │ prometheus   │  │ grafana      │ │   │  │ redis (cache)       │   │    │
│  │  │ Port 9090    │──│ Port 3000    │ │   │  │ Port 6379           │   │    │
│  │  └──────────────┘  └──────────────┘ │   │  ├─────────────────────┤   │    │
│  │                                     │   │  │ minio (S3)          │   │    │
│  └─────────────────────────────────────┘   │  │ Port 9000/9001      │   │    │
│                                            │  ├─────────────────────┤   │    │
│  ┌─── Profil: benchmarks ──────────────┐   │  │ postgres-benchmarks │   │    │
│  │  ┌──────────────────────────────┐   │   │  │ Port 5433           │   │    │
│  │  │ postgres-benchmarks          │   │   │  └─────────────────────┘   │    │
│  │  │ Port 5433                    │   │   │                            │    │
│  │  └──────────────────────────────┘   │   └────────────────────────────┘    │
│  └─────────────────────────────────────┘                                     │
│                                                                              │
│  ┌─── Volumes partages ─────────────────────────────────────────────────┐    │
│  │  ./data/          (Bronze, Silver, Gold, warehouse.duckdb)           │    │
│  │  ./src/           (code source pipeline)                             │    │
│  │  ./config.toml    (configuration centralisee)                        │    │
│  │  ./dags/          (DAG Airflow)                                      │    │
│  │  ./dbt_project/   (modeles dbt)                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Profils Docker Compose

| Profil | Services | Usage |
|--------|----------|-------|
| *(aucun)* | api, streamlit | Runtime par defaut |
| `pipeline` | pipeline | Bootstrap initial (one-shot) |
| `airflow` | airflow-webserver, airflow-scheduler, postgres | Orchestration quotidienne |
| `streaming` | redpanda, redpanda-console, stream-producer, stream-consumer | Ingestion temps reel |
| `monitoring` | prometheus, grafana | Observabilite |
| `benchmarks` | postgres-benchmarks | Base de benchmarks |
| `cache` | redis | Cache API |
| `storage` | minio | Object storage S3 |
| `full` | Tous les services | Stack complete |

### 5.3 Ports exposes

| Service | Port | Protocole | Usage |
|---------|------|-----------|-------|
| FastAPI | 8000 | HTTP | API REST + /prom/metrics |
| Streamlit | 8501 | HTTP | Dashboard interactif |
| Airflow | 8081 | HTTP | Interface web DAG |
| Redpanda Console | 8080 | HTTP | Monitoring Kafka |
| Redpanda (Kafka) | 19092 | TCP | Acces externe Kafka |
| Prometheus | 9090 | HTTP | Interface metriques |
| Grafana | 3000 | HTTP | Dashboards operationnels |
| PostgreSQL (benchmarks) | 5433 | TCP | Base benchmarks |
| Redis | 6379 | TCP | Cache |
| MinIO | 9000/9001 | HTTP | Object storage / console |

### 5.4 Ressources requises

| Ressource | Minimum (api + streamlit) | Recommande (full) |
|-----------|---------------------------|-------------------|
| CPU | 2 cores | 4 cores |
| RAM | 1 GB | 4 GB |
| Disque | 500 MB | 5 GB |
| Reseau | Internet (Binance, Yahoo, CoinGecko) | Idem |
| Docker | Docker Engine 24+ | Docker Desktop |

---

## 6. Representation operationnelle

### 6.1 Cycle de vie des donnees

```
Sources externes (Binance, Yahoo, CoinGecko, PostgreSQL, CSV, JSON)
     │
     │  Airflow DAG quotidien (00:00) ou bootstrap initial
     ▼
[Bronze: data/raw/]
     │  Parquet brut, schema source
     │  Retention: 1 an
     │  + Stream consumer (micro-batch continu via Kafka)
     ▼
[Silver: data/processed/]
     │  Rendements, volatilite, correlation, covariance
     │  Retention: 1 an
     │  + dbt staging models (stg_klines, stg_symbols)
     ▼
[Gold: data/output/]
     │  Poids optimaux, frontiere, backtest, metriques
     │  Retention: 30 jours
     │  + dbt marts (fact_prices, dim_symbol, dim_date, aggregats)
     ▼
[DuckDB: data/warehouse.duckdb]
     │  Star schema interrogeable SQL
     │  Retention: permanente (rebuilt par dbt)
     ▼
[Exposition]
     API REST (46 endpoints) + Dashboard (32 pages) + PDF export
```

### 6.2 Orchestration Airflow

Le DAG `portfolio_dag.py` orchestre 12 taches en deux branches paralleles :

```
                         ┌─── Branche Crypto ───────────────────────────────────┐
                         │                                                      │
start ──┬───▶ ingest_crypto ──▶ transform_crypto ──▶ optimize_crypto          │
        │          ──▶ frontier_crypto ──▶ backtest_crypto ─────┐              │
        │                                                       │               │
        │    ┌─── Branche Traditionnelle ────────────────────────┤              │
        │    │                                                   │              │
        ├───▶ ingest_trad ──▶ transform_trad ──▶ optimize_trad │              │
        │          ──▶ frontier_trad ──▶ backtest_trad ──┐      │              │
        │                                                 │      │              │
        │                                                 ▼      ▼              │
        └──────────────────────────────────────────▶  dbt_run    ──▶ end       │
                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

- **Frequence** : quotidien a 00:00 UTC
- **Retry** : 2 tentatives par tache, delai 5 minutes
- **Monitoring** : interface Airflow :8081 (historique, logs, durees)

### 6.3 Monitoring et alertes

| Metrique | Source | Outil | Seuil d'alerte |
|----------|--------|-------|----------------|
| Latence API p95 | FastAPI /prom/metrics | Prometheus + Grafana | > 2s |
| Taux d'erreur API | FastAPI /prom/metrics | Prometheus + Grafana | > 5% |
| Disponibilite API | Docker healthcheck | Docker Engine | Service unhealthy |
| Succes DAG Airflow | Airflow metadata | Interface Airflow | Echec tache |
| Espace disque data/ | OS monitoring | Alertes manuelles | > 80% |
| Lag consommateur Kafka | Redpanda Console | Interface Redpanda | > 1000 messages |
| Metriques metier | prometheus-client custom | Grafana dashboard | Configurable |

### 6.4 Strategie de sauvegarde

| Element | Methode | Frequence |
|---------|---------|-----------|
| Code source | Git (GitHub) | A chaque commit |
| Donnees Bronze/Silver | Regenerables depuis les sources | A la demande |
| Donnees Gold | Regenerables par pipeline | Quotidien |
| DuckDB warehouse | Rebuild par dbt_run | Quotidien |
| Configuration | Versionnee dans Git (config.toml) | A chaque commit |
| Volumes Docker | Volumes nommes persistants | Continu |

---

## 7. Decisions d'architecture

### 7.1 Choix techniques justifies (avec ADR)

| Decision | Justification | Reference ADR |
|----------|---------------|---------------|
| **Parquet** | Format columnar compresse, standard industrie, schema type | ADR-001 |
| **DuckDB** | OLAP in-process, SQL standard, pas de serveur a gerer | ADR-002 |
| **PyArrow (pas de pandas)** | Memoire efficace, type-safe, zero-copy, API stable | ADR-003 |
| **FastAPI** | Async, auto-documentation OpenAPI, injection Depends() | ADR-004 |
| **Airflow** | Standard industriel, interface web, retry, monitoring integre | ADR-005 |
| **Delta Lake** | ACID, time travel, schema enforcement (backend optionnel) | ADR-006 |
| **dbt-duckdb** | Transforms SQL declaratifs, tests integres, lineage | ADR-007 |
| **Docker Compose** | Portabilite, isolation, profils modulaires | — |
| **Kafka (Redpanda)** | Streaming decoupled, compatible Kafka, leger (single binary) | — |
| **Prometheus + Grafana** | Standard observabilite, PromQL, alertes configurables | — |
| **PySpark (local)** | API distribuee, preparation a la scalabilite, mode local suffisant | — |
| **Python 3.13** | Dernieres optimisations, typing generics natifs | — |
| **Redis** | Cache API TTL, reduction latence endpoints couteux | — |
| **MinIO** | S3-compatible, backend optionnel cloud-native | — |

### 7.2 Alternatives ecartees

| Alternative | Raison du rejet |
|-------------|-----------------|
| **PostgreSQL pour le DWH** | Necessite un serveur dedie ; DuckDB offre les memes requetes OLAP sans infrastructure |
| **Spark cluster distribue** | Volume insuffisant (<100 symboles) ; PySpark en mode local suffit |
| **Cloud AWS/GCP** | Budget et complexite excessifs pour un projet certification ; Docker local equivalent |
| **pandas** | Dependance lourde, API instable entre versions, surcout memoire (copies implicites) ; PyArrow plus efficace (ADR-003) |
| **Celery** | Complexite (Redis/RabbitMQ broker) pour une orchestration simple ; Airflow offre interface, retry, monitoring |
| **InfluxDB** | Specialise time-series pur ; DuckDB couvre le cas OLAP + time-series avec SQL standard |
| **Apache Flink** | Streaming distribue ; Redpanda + consumer Python suffisent pour le volume actuel |

---

## 8. Eco-responsabilite

### 8.1 Conformite au RGESN

Conformement au [Referentiel General d'Ecoconception de Services Numeriques (RGESN)](https://ecoresponsable.numerique.gouv.fr/publications/referentiel-general-ecoconception/), les mesures suivantes sont appliquees :

| Critere RGESN | Mesure appliquee | Impact |
|---------------|------------------|--------|
| **Hebergement** | Deploiement local (Docker), pas de datacenter cloud | Empreinte carbone reduite, pas de surconsommation cloud |
| **Architecture** | Services a la demande (profils Docker), pas de compute permanent | Ressources consommees uniquement quand necessaire |
| **Stockage** | Parquet compresse (Snappy), reduction ~70% vs CSV brut | Espace disque minimise |
| **Traitement** | DuckDB in-process (pas de serveur SGBD permanent) | Pas de ressource gaspillee en idle |
| **Images Docker** | Multi-stage builds, base `python:3.13-slim` | Images legeres (~200 MB vs >1 GB) |
| **Donnees** | Retention differenciee (Bronze 1 an, Gold 30 jours), purge planifiee | Pas d'accumulation inutile |
| **Requetes API** | Cache Redis (TTL configurable), evite recalculs couteux | Reduction charge CPU et I/O |
| **Streaming** | Micro-batch (pas de traitement message par message) | Amortissement overhead, moins de cycles CPU |
| **Monitoring** | Scrape Prometheus a intervalle (15s), pas de push continu | Trafic reseau maitrise |
| **Code** | PyArrow zero-copy, pas de duplication en memoire (vs pandas) | Empreinte memoire reduite de 50%+ |

### 8.2 Indicateurs d'eco-conception

| Indicateur | Valeur mesuree | Objectif |
|------------|----------------|----------|
| Taille image Docker API | ~200 MB | < 500 MB |
| Taille image Streamlit | ~300 MB | < 500 MB |
| Stockage donnees 1 an (10 symboles) | ~50 MB | < 100 MB |
| Consommation memoire API | ~150 MB | < 500 MB |
| Consommation memoire pipeline (pic) | ~400 MB | < 1 GB |
| Nombre de services en profil defaut | 2 (api + streamlit) | Minimal |

### 8.3 Bonnes pratiques de developpement

- **Pas de dependance inutile** : `pyproject.toml` avec extras optionnels (test, streaming, spark)
- **Lazy loading** : les modules lourds (PySpark, dbt) ne sont importes que quand necessaire
- **Profils Docker** : seuls les services necessaires demarrent, pas de stack monolithique par defaut
- **CI legere** : tests unitaires rapides, linting sans build Docker complet

---

## 9. Accessibilite

### 9.1 Adaptation des postes de travail

| Interface | Mesure d'accessibilite |
|-----------|------------------------|
| **API REST** | Accessible depuis tout client HTTP (curl, Postman, navigateur, lecteur d'ecran) |
| **Documentation OpenAPI** | Interface Swagger UI auto-generee, navigable au clavier |
| **Dashboard Streamlit** | HTML semantique, contrastes suffisants, responsive |
| **Logs** | Format texte structure, lisible par outils d'assistance |
| **CLI / scripts** | Sorties texte standard, compatibles avec pipes et outils shell |

### 9.2 Utilisateurs finaux

- **API JSON** : format structure compatible avec les technologies d'assistance (lecteurs d'ecran, terminaux braille)
- **Tableau de bord** : graphiques Plotly avec tooltips textuels, tableaux de donnees avec en-tetes
- **PDF export** : rapports generes avec texte selectionnable (fpdf2)
- **Documentation** : Markdown versionne dans Git, convertible en tout format

### 9.3 Accessibilite de l'infrastructure

- **Docker** : deploiement identique sur Windows, macOS, Linux
- **Configuration** : fichier TOML unique (`config.toml`), variables d'environnement pour les secrets
- **Profils** : complexite progressive — un developpeur peut demarrer avec `docker compose up api streamlit` sans connaitre l'ensemble de la stack

---

## 10. Processus RGPD

### 10.1 Nature des donnees traitees

| Type de donnee | Exemple | Donnee personnelle ? |
|----------------|---------|----------------------|
| Prix OHLCV | BTC: 95 000 USD | Non |
| Volume de marche | 1 000 BTC echanges | Non |
| Timestamps | 2025-01-15T00:00:00Z | Non |
| Symboles | BTCUSDT, AAPL, GLD | Non |
| Metriques calculees | Rendement: +2%, Sharpe: 1.5 | Non |
| Metadata marche (scraping) | Market cap: $1.2T | Non |

**Conclusion** : aucune donnee a caractere personnel (PII) n'est collectee, stockee ou traitee dans ce projet. Toutes les donnees proviennent de sources publiques (API Binance, Yahoo Finance, CoinGecko) et representent des informations de marche agregees, anonymes par nature.

### 10.2 Applicabilite du RGPD

Le RGPD ne s'applique pas directement a ce projet (absence de PII). Cependant, par anticipation d'evolutions futures (portefeuilles utilisateurs, historique de transactions personnelles), les mesures suivantes sont documentees et pretes a etre activees.

### 10.3 Mesures privacy-by-design

| Principe RGPD | Application actuelle | Mesure preventive |
|----------------|---------------------|---------------------|
| **Minimisation** | Seules les donnees OHLCV necessaires sont collectees | Filtrage a la source (symboles configures dans config.toml) |
| **Limitation de conservation** | Retention differenciee (Bronze 1 an, Gold 30 jours) | Script de purge automatique planifiable |
| **Transparence** | Sources documentees (registre des traitements dans `07_rgpd.md`) | Registre mis a jour a chaque nouvelle source |
| **Securite** | Docker isolation, secrets dans .env, pas d'exposition externe | Chiffrement TLS vers toutes les API externes (HTTPS) |
| **Tracabilite** | Logs applicatifs (module logging Python), Git history | Audit trail pour tout changement de configuration |

### 10.4 Variables sensibles

Les secrets sont geres via variables d'environnement (fichier `.env` non versionne) :

| Variable | Usage | Stockage |
|----------|-------|----------|
| `AIRFLOW_DB_PASSWORD` | PostgreSQL metadata Airflow | `.env` (local) |
| `AIRFLOW_FERNET_KEY` | Chiffrement connexions Airflow | `.env` (local) |
| `AIRFLOW_SECRET_KEY` | Session webserver Airflow | `.env` (local) |
| `BENCHMARKS_DB_PASSWORD` | PostgreSQL benchmarks | `.env` (local) |
| `MINIO_SECRET_KEY` | Object storage MinIO | `.env` (local) |

Aucun mot de passe ou cle n'est present dans le code source ou les fichiers de configuration versionnes.

### 10.5 Reference detaillee

Le registre complet des traitements, les procedures de suppression et d'export, ainsi que la politique de purge sont documentes dans [`07_rgpd.md`](07_rgpd.md).
