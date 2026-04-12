# Modelisation MERISE (C11)

## 1. Introduction

La methode MERISE (Methode d'Etude et de Realisation Informatique pour les Systemes d'Entreprise) structure la modelisation en trois niveaux :

| Niveau | Modele | Description |
|--------|--------|-------------|
| Conceptuel | MCD | Quoi ? (entites, associations) |
| Logique | MLD | Comment ? (tables, relations) |
| Physique | MPD | Ou ? (implementation technique) |

---

## 2. Modele Conceptuel de Donnees (MCD)

### 2.1 Diagramme entite-association

```
┌─────────────────┐          ┌─────────────────┐
│     SYMBOL      │          │      DATE       │
├─────────────────┤          ├─────────────────┤
│ symbol (PK)     │          │ date (PK)       │
│ name            │          │ year            │
│ sector          │          │ month           │
│ category        │          │ day             │
│ asset_class     │          │ day_of_week     │
│ source          │          └────────┬────────┘
│ launch_year     │                   │
│ consensus       │                   │
└────────┬────────┘                   │
         │                            │
         │ 1,n                   1,n  │
         │                            │
         └──────────┐    ┌────────────┘
                    │    │
                    ▼    ▼
              ┌─────────────────┐
              │     PRICE       │
              ├─────────────────┤
              │ symbol (FK)     │
              │ date (FK)       │
              │ open            │
              │ high            │
              │ low             │
              │ close           │
              │ volume          │
              └─────────────────┘


┌─────────────────┐          ┌─────────────────┐
│    PORTFOLIO    │          │   ALLOCATION    │
├─────────────────┤          ├─────────────────┤
│ portfolio_id(PK)│ 1      n │ portfolio_id(FK)│
│ name            │──────────│ symbol (FK)     │
│ created_at      │          │ weight          │
│ risk_free_rate  │          │ expected_return │
└─────────────────┘          └─────────────────┘


┌─────────────────┐
│    BENCHMARK    │
├─────────────────┤
│ symbol (PK)     │          Utilise pour l'analyse
│ name            │          alpha/beta (CAPM) :
│ description     │          SPY, QQQ, BTC, etc.
│ asset_class     │
└────────┬────────┘
         │
         │ 1,n
         ▼
┌─────────────────┐
│ BENCHMARK_PRICE │
├─────────────────┤
│ symbol (FK)     │
│ date (FK)       │
│ close           │
│ volume          │
└─────────────────┘
```

### 2.2 Dictionnaire des entites

| Entite | Description | Identifiant |
|--------|-------------|-------------|
| SYMBOL | Actif financier (crypto ou traditionnel) | symbol |
| DATE | Dimension temporelle | date |
| PRICE | Donnees OHLCV quotidiennes | (symbol, date) |
| PORTFOLIO | Configuration de portefeuille | portfolio_id |
| ALLOCATION | Poids d'un symbole dans un portefeuille | (portfolio_id, symbol) |
| BENCHMARK | Indice de reference pour analyse CAPM | symbol |
| BENCHMARK_PRICE | Prix historiques des benchmarks | (symbol, date) |

### 2.3 Attribut asset_class

L'entite SYMBOL couvre a la fois les actifs crypto et les actifs traditionnels :

| asset_class | Source | Exemples |
|-------------|--------|----------|
| `crypto` | API Binance | BTCUSDT, ETHUSDT, BNBUSDT |
| `trad` | yfinance | SPY, QQQ, GLD, AAPL |

Cette distinction permet de :
- Filtrer par classe d'actif dans les requetes
- Comparer les performances crypto vs traditionnel (page Comparison du dashboard)
- Construire des portefeuilles mixtes (`src/pipeline/combine.py`)

### 2.4 Cardinalites

| Association | Cardinalite | Lecture |
|-------------|-------------|---------|
| SYMBOL - PRICE | 1,n | Un symbole a plusieurs prix (historique) |
| DATE - PRICE | 1,n | Une date a plusieurs prix (multi-symboles) |
| PORTFOLIO - ALLOCATION | 1,n | Un portefeuille a plusieurs allocations |
| SYMBOL - ALLOCATION | 1,n | Un symbole peut etre dans plusieurs portefeuilles |
| BENCHMARK - BENCHMARK_PRICE | 1,n | Un benchmark a plusieurs prix historiques |

---

## 3. Modele Logique de Donnees (MLD)

### 3.1 Passage MCD -> MLD

Regles appliquees :
- Entites -> Tables
- Associations n,n -> Table intermediaire
- Associations 1,n -> Cle etrangere

### 3.2 Schema relationnel

```sql
-- Dimension: Symboles (crypto + traditionnel)
dim_symbol (
    symbol      VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    sector      VARCHAR(50),
    category    VARCHAR(50),
    asset_class VARCHAR(10) NOT NULL DEFAULT 'crypto',  -- 'crypto' ou 'trad'
    source      VARCHAR(20),                            -- 'binance', 'yfinance', 'coingecko'
    launch_year INTEGER,
    consensus   VARCHAR(50)
)

-- Dimension: Dates
dim_date (
    date        DATE PRIMARY KEY,
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    day         INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL
)

-- Fait: Prix (crypto + traditionnel)
fact_prices (
    symbol      VARCHAR(20) REFERENCES dim_symbol(symbol),
    date        DATE REFERENCES dim_date(date),
    open        DECIMAL(18,8) NOT NULL,
    high        DECIMAL(18,8) NOT NULL,
    low         DECIMAL(18,8) NOT NULL,
    close       DECIMAL(18,8) NOT NULL,
    volume      DECIMAL(24,8) NOT NULL,
    PRIMARY KEY (symbol, date)
)

-- Portefeuille
portfolio (
    portfolio_id    SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    risk_free_rate  DECIMAL(6,4) DEFAULT 0.05
)

-- Allocation
allocation (
    portfolio_id    INTEGER REFERENCES portfolio(portfolio_id),
    symbol          VARCHAR(20) REFERENCES dim_symbol(symbol),
    weight          DECIMAL(6,4) NOT NULL CHECK (weight >= 0 AND weight <= 1),
    PRIMARY KEY (portfolio_id, symbol)
)

-- Benchmark (pour analyse alpha/beta)
benchmark (
    symbol      VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    asset_class VARCHAR(10) NOT NULL  -- 'index', 'etf', 'crypto'
)
```

### 3.3 Dependances fonctionnelles

```
-- dim_symbol
symbol -> name, sector, category, asset_class, source, launch_year, consensus

-- dim_date
date -> year, month, day, day_of_week

-- fact_prices
(symbol, date) -> open, high, low, close, volume

-- allocation
(portfolio_id, symbol) -> weight

-- benchmark
symbol -> name, description, asset_class
```

---

## 4. Modele Physique de Donnees (MPD)

### 4.1 Choix d'implementation

| Aspect | Choix | Justification |
|--------|-------|---------------|
| SGBD | DuckDB + Parquet | Analytique, serverless |
| Format stockage | Parquet | Columnar, compresse |
| Partitionnement | Par symbole (Hive) | Requetes par actif, glob patterns |
| Index | Automatique (Parquet) | Statistiques integrees |
| Transforms SQL | dbt-duckdb | Lineage, tests, documentation |

### 4.2 Structure physique

```
data/
├── raw/
│   └── klines/
│       ├── BTCUSDT.parquet      # Crypto (Binance)
│       ├── ETHUSDT.parquet
│       ├── SPY.parquet          # Traditionnel (yfinance)
│       ├── QQQ.parquet
│       └── ...
├── reference/
│   ├── symbols_metadata.csv     # dim_symbol source
│   └── portfolio_config.json    # portfolio config
├── processed/
│   ├── returns.parquet          # Metriques calculees
│   ├── volatility.parquet
│   ├── correlation.parquet
│   └── covariance.parquet
└── output/
    └── weights.json             # allocation resultat
```

### 4.3 Schema Parquet

**klines/{SYMBOL}.parquet** (equivalent fact_prices) :

| Colonne | Type Parquet | Compression |
|---------|--------------|-------------|
| timestamp | STRING | SNAPPY |
| open | DOUBLE | SNAPPY |
| high | DOUBLE | SNAPPY |
| low | DOUBLE | SNAPPY |
| close | DOUBLE | SNAPPY |
| volume | DOUBLE | SNAPPY |

### 4.4 Vues DuckDB (Star Schema)

```sql
-- Creation des vues sur Parquet (duckdb.py)

-- Vue fait prix : lecture dynamique de tous les fichiers Parquet
-- Utilisation de glob patterns au lieu de UNION ALL manuel
CREATE VIEW fact_prices AS
SELECT
    REPLACE(REPLACE(filename, 'data/raw/klines/', ''), '.parquet', '') AS symbol,
    timestamp, open, high, low, close, volume
FROM read_parquet('data/raw/klines/*.parquet', filename=true);

-- Vue dimension symboles (derivee des faits)
CREATE VIEW dim_symbol AS
SELECT symbol, ROW_NUMBER() OVER (ORDER BY symbol) as symbol_id
FROM (SELECT DISTINCT symbol FROM fact_prices);

-- Vue dimension dates (derivee des faits)
CREATE VIEW dim_date AS
SELECT DISTINCT
    timestamp as date,
    EXTRACT(YEAR FROM CAST(timestamp AS DATE)) as year,
    EXTRACT(MONTH FROM CAST(timestamp AS DATE)) as month,
    EXTRACT(DAY FROM CAST(timestamp AS DATE)) as day,
    EXTRACT(DOW FROM CAST(timestamp AS DATE)) as day_of_week
FROM fact_prices;
```

### 4.5 Modeles dbt (implementation SQL)

Les modeles MERISE sont egalement implementes via dbt (`dbt_project/models/`) :

| Couche dbt | Modele | Role |
|------------|--------|------|
| Staging | `stg_klines.sql` | Typage et nettoyage des donnees brutes Parquet |
| Staging | `stg_symbols.sql` | Extraction des symboles uniques + metadonnees |
| Marts | `fact_prices.sql` | Table de faits OHLCV dedupliquee |
| Marts | `dim_symbol.sql` | Dimension symboles |
| Marts | `dim_date.sql` | Dimension temporelle |
| Marts | `agg_daily_returns.sql` | Agregation des rendements journaliers |
| Marts | `portfolio_summary.sql` | Resume des metriques de portefeuille |

Les vues DuckDB (section 4.4) et les modeles dbt produisent le meme schema en etoile. Les modeles dbt ajoutent des tests de qualite integres (unique, not_null, relationships) et la documentation du lineage.

---

## 5. Normalisation

### 5.1 Analyse des formes normales

| Table | 1NF | 2NF | 3NF | BCNF |
|-------|-----|-----|-----|------|
| dim_symbol | Oui | Oui | Oui | Oui |
| dim_date | Oui | Oui | Oui | Oui |
| fact_prices | Oui | Oui | Oui | Oui |
| portfolio | Oui | Oui | Oui | Oui |
| allocation | Oui | Oui | Oui | Oui |
| benchmark | Oui | Oui | Oui | Oui |

**Justifications :**
- **1NF** : Toutes les valeurs sont atomiques
- **2NF** : Pas de dependance partielle (cles composites OK)
- **3NF** : Pas de dependance transitive
- **BCNF** : Tout determinant est une cle candidate

### 5.2 Denormalisation justifiee

Le schema en etoile (star schema) denormalise volontairement pour :
- Performance des requetes analytiques
- Simplicite des jointures (fait -> dimension)
- Compatibilite avec les outils BI

---

## 6. Contraintes d'integrite

### 6.1 Contraintes de domaine

```sql
-- Prix positifs
CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0)

-- High >= Low
CHECK (high >= low)

-- Open et Close entre High et Low
CHECK (open BETWEEN low AND high)
CHECK (close BETWEEN low AND high)

-- Poids entre 0 et 1
CHECK (weight >= 0 AND weight <= 1)
```

### 6.2 Contraintes referentielles

```sql
-- Integrite referentielle
fact_prices.symbol -> dim_symbol.symbol
allocation.symbol -> dim_symbol.symbol
allocation.portfolio_id -> portfolio.portfolio_id
```

### 6.3 Contraintes metier

| Contrainte | Regle | Implementation |
|------------|-------|----------------|
| Somme poids = 1 | Un portefeuille est fully invested | CHECK au niveau applicatif |
| Unicite prix | Un seul prix par (symbol, date) | PK composite |
| Dates continues | Pas de trous dans l'historique | Validation a l'ingestion |
| Qualite donnees | Controles bronze/silver/gold | `src/pipeline/validation.py` |

---

## 7. Conformite au referentiel C11

| Critere | Statut | Preuve |
|---------|--------|--------|
| Modelisation MERISE | Oui | Sections 2-4 (MCD/MLD/MPD) |
| Modele physique fonctionnel | Oui | DuckDB + Parquet operationnels |
| Base adaptee aux contraintes | Oui | Serverless, analytique |
| Script d'import fonctionnel | Oui | `ingest.py`, `ingest_sources.py`, `ingest_yfinance.py` |
| Actifs traditionnels inclus | Oui | SYMBOL.asset_class (crypto/trad) |
| Implementation dbt | Oui | `dbt_project/models/marts/` |
| Documentation technique | Oui | Ce document |
| Registre RGPD | Oui | `07_rgpd.md` |

---

## 8. Documentation du script d'import

### 8.1 Dependances

| Dependance | Version | Role |
|------------|---------|------|
| `httpx` | >= 0.27 | Client HTTP asynchrone pour l'API Binance |
| `pyarrow` | >= 15.0 | Serialisation/deserialisation Parquet |
| `yfinance` | >= 0.2 | Recuperation donnees Yahoo Finance (actifs traditionnels) |
| `beautifulsoup4` | >= 4.12 | Scraping CoinGecko (donnees complementaires) |
| `duckdb` | >= 0.10 | Entrepot de donnees analytique |

### 8.2 Commandes d'execution

```bash
# Ingestion incrementale crypto (Binance API)
python -c "from src.pipeline import ingest_incremental; ingest_incremental()"

# Ingestion multi-sources (6 sources : API, CSV, JSON, scraping, PostgreSQL, yfinance)
python -c "from src.pipeline import ingest_all_sources; ingest_all_sources()"

# Ingestion actifs traditionnels (yfinance)
python -c "from src.pipeline.ingest_yfinance import ingest_yfinance_data; ingest_yfinance_data()"

# Transformation (rendements, volatilite, correlation, covariance)
python -c "from src.pipeline import transform_data; transform_data()"

# Optimisation portefeuille (Markowitz)
python -c "from src.pipeline import optimize_portfolio; optimize_portfolio()"

# Pipeline complet via Airflow (recommande)
# Airflow DAG : dags/portfolio_dag.py
docker compose --profile airflow up -d
```

### 8.3 Algorithme d'ingestion incrementale

```
DEBUT ingestion_incrementale(symbols, interval)
    POUR CHAQUE symbol DANS symbols:
        1. Lire le fichier Parquet existant : data/raw/klines/{symbol}.parquet
        2. SI fichier existe:
              last_ts = MAX(timestamp) du fichier
           SINON:
              last_ts = date de debut par defaut (config)
        3. Appeler API Binance : GET /api/v3/klines
              params = symbol, interval, startTime = last_ts + 1
        4. Convertir la reponse JSON en table PyArrow
        5. Valider les donnees (validation.py, etage bronze)
        6. SI fichier existe:
              Concatener anciennes + nouvelles donnees
           SINON:
              Creer nouveau fichier
        7. Ecrire le fichier Parquet (compression SNAPPY)
    FIN POUR
FIN
```

### 8.4 Flux de donnees

```
Sources externes                    Pipeline interne
┌──────────────┐
│ Binance API  │──── httpx ────┐
└──────────────┘               │
┌──────────────┐               │     ┌──────────────┐     ┌──────────────┐
│ Yahoo Finance│── yfinance ───┼────>│ data/raw/    │────>│ data/        │
└──────────────┘               │     │ (Bronze)     │     │ processed/   │
┌──────────────┐               │     │ .parquet     │     │ (Silver)     │
│ CoinGecko    │── bs4 ────────┤     └──────────────┘     └──────┬───────┘
└──────────────┘               │                                 │
┌──────────────┐               │                                 ▼
│ CSV / JSON   │── pyarrow ────┤                          ┌──────────────┐
└──────────────┘               │                          │ data/output/ │
┌──────────────┐               │                          │ (Gold)       │
│ PostgreSQL   │── psycopg2 ───┘                          └──────────────┘
└──────────────┘
```

---

## Glossaire

- **MCD** : Modele Conceptuel de Donnees - representation abstraite des entites et associations
- **MLD** : Modele Logique de Donnees - traduction en schema relationnel
- **MPD** : Modele Physique de Donnees - implementation technique (SGBD, format de stockage)
- **OHLCV** : Open, High, Low, Close, Volume - donnees de marche standard
- **Hive partitioning** : Convention de nommage des repertoires/fichiers pour le partitionnement
- **dbt** : Data Build Tool - framework de transformation SQL avec tests et lineage
- **asset_class** : Classification des actifs (crypto, trad) pour distinguer les sources
