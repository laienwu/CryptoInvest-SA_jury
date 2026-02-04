# Modélisation MERISE (C11)

## 1. Introduction

La méthode MERISE (Méthode d'Étude et de Réalisation Informatique pour les Systèmes d'Entreprise) structure la modélisation en trois niveaux :

| Niveau | Modèle | Description |
|--------|--------|-------------|
| Conceptuel | MCD | Quoi ? (entités, associations) |
| Logique | MLD | Comment ? (tables, relations) |
| Physique | MPD | Où ? (implémentation technique) |

---

## 2. Modèle Conceptuel de Données (MCD)

### 2.1 Diagramme entité-association

```
┌─────────────────┐          ┌─────────────────┐
│     SYMBOL      │          │      DATE       │
├─────────────────┤          ├─────────────────┤
│ symbol (PK)     │          │ date (PK)       │
│ name            │          │ year            │
│ sector          │          │ month           │
│ category        │          │ day             │
│ launch_year     │          │ day_of_week     │
│ consensus       │          └────────┬────────┘
└────────┬────────┘                   │
         │                            │
         │ 1,n                    1,n │
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
```

### 2.2 Dictionnaire des entités

| Entité | Description | Identifiant |
|--------|-------------|-------------|
| SYMBOL | Paire de trading crypto | symbol |
| DATE | Dimension temporelle | date |
| PRICE | Données OHLCV quotidiennes | (symbol, date) |
| PORTFOLIO | Configuration de portefeuille | portfolio_id |
| ALLOCATION | Poids d'un symbole dans un portefeuille | (portfolio_id, symbol) |

### 2.3 Cardinalités

| Association | Cardinalité | Lecture |
|-------------|-------------|---------|
| SYMBOL - PRICE | 1,n | Un symbole a plusieurs prix (historique) |
| DATE - PRICE | 1,n | Une date a plusieurs prix (multi-symboles) |
| PORTFOLIO - ALLOCATION | 1,n | Un portefeuille a plusieurs allocations |
| SYMBOL - ALLOCATION | 1,n | Un symbole peut être dans plusieurs portefeuilles |

---

## 3. Modèle Logique de Données (MLD)

### 3.1 Passage MCD → MLD

Règles appliquées :
- Entités → Tables
- Associations n,n → Table intermédiaire
- Associations 1,n → Clé étrangère

### 3.2 Schéma relationnel

```sql
-- Dimension: Symboles
dim_symbol (
    symbol      VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    sector      VARCHAR(50),
    category    VARCHAR(50),
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

-- Fait: Prix
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
```

### 3.3 Dépendances fonctionnelles

```
-- dim_symbol
symbol → name, sector, category, launch_year, consensus

-- dim_date
date → year, month, day, day_of_week

-- fact_prices
(symbol, date) → open, high, low, close, volume

-- allocation
(portfolio_id, symbol) → weight
```

---

## 4. Modèle Physique de Données (MPD)

### 4.1 Choix d'implémentation

| Aspect | Choix | Justification |
|--------|-------|---------------|
| SGBD | DuckDB + Parquet | Analytique, serverless |
| Format stockage | Parquet | Columnar, compressé |
| Partitionnement | Par symbole | Requêtes par actif |
| Index | Automatique (Parquet) | Statistiques intégrées |

### 4.2 Structure physique

```
data/
├── raw/
│   └── klines/
│       ├── BTCUSDT.parquet    # fact_prices partitionné
│       ├── ETHUSDT.parquet
│       └── ...
├── reference/
│   ├── symbols_metadata.csv   # dim_symbol source
│   └── portfolio_config.json  # portfolio config
├── processed/
│   ├── returns.parquet        # Métriques calculées
│   ├── volatility.parquet
│   ├── correlation.parquet
│   └── covariance.parquet
└── output/
    └── weights.json           # allocation résultat
```

### 4.3 Schéma Parquet

**klines/{SYMBOL}.parquet** (équivalent fact_prices) :

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
-- Création des vues sur Parquet (duckdb.py)

-- Vue dimension symboles
CREATE VIEW dim_symbol AS
SELECT symbol, ROW_NUMBER() OVER (ORDER BY symbol) as symbol_id
FROM (SELECT DISTINCT symbol FROM fact_prices);

-- Vue dimension dates
CREATE VIEW dim_date AS
SELECT DISTINCT
    timestamp as date,
    EXTRACT(YEAR FROM CAST(timestamp AS DATE)) as year,
    EXTRACT(MONTH FROM CAST(timestamp AS DATE)) as month,
    EXTRACT(DAY FROM CAST(timestamp AS DATE)) as day,
    EXTRACT(DOW FROM CAST(timestamp AS DATE)) as day_of_week
FROM fact_prices;

-- Vue fait prix (union des fichiers Parquet)
CREATE VIEW fact_prices AS
SELECT 'BTCUSDT' as symbol, * FROM read_parquet('data/raw/klines/BTCUSDT.parquet')
UNION ALL
SELECT 'ETHUSDT' as symbol, * FROM read_parquet('data/raw/klines/ETHUSDT.parquet')
-- ...
```

---

## 5. Normalisation

### 5.1 Analyse des formes normales

| Table | 1NF | 2NF | 3NF | BCNF |
|-------|-----|-----|-----|------|
| dim_symbol | ✅ | ✅ | ✅ | ✅ |
| dim_date | ✅ | ✅ | ✅ | ✅ |
| fact_prices | ✅ | ✅ | ✅ | ✅ |
| portfolio | ✅ | ✅ | ✅ | ✅ |
| allocation | ✅ | ✅ | ✅ | ✅ |

**Justifications :**
- **1NF** : Toutes les valeurs sont atomiques
- **2NF** : Pas de dépendance partielle (clés composites OK)
- **3NF** : Pas de dépendance transitive
- **BCNF** : Tout déterminant est une clé candidate

### 5.2 Dénormalisation justifiée

Le schéma en étoile (star schema) dénormalise volontairement pour :
- Performance des requêtes analytiques
- Simplicité des jointures (fait → dimension)
- Compatibilité avec les outils BI

---

## 6. Contraintes d'intégrité

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

### 6.2 Contraintes référentielles

```sql
-- Intégrité référentielle
fact_prices.symbol → dim_symbol.symbol
allocation.symbol → dim_symbol.symbol
allocation.portfolio_id → portfolio.portfolio_id
```

### 6.3 Contraintes métier

| Contrainte | Règle | Implémentation |
|------------|-------|----------------|
| Somme poids = 1 | Un portefeuille est fully invested | CHECK au niveau applicatif |
| Unicité prix | Un seul prix par (symbol, date) | PK composite |
| Dates continues | Pas de trous dans l'historique | Validation à l'ingestion |

---

## 7. Conformité au référentiel C11

| Critère | Statut | Preuve |
|---------|--------|--------|
| Modélisation MERISE | ✅ | Sections 2-4 (MCD/MLD/MPD) |
| Modèle physique fonctionnel | ✅ | DuckDB + Parquet opérationnels |
| Base adaptée aux contraintes | ✅ | Serverless, analytique |
| Script d'import fonctionnel | ✅ | `ingest.py`, `ingest_sources.py` |
| Documentation technique | ✅ | Ce document |
| Registre RGPD | ✅ | `07_rgpd.md` |
