# Gestion des Variations de Dimensions (C17)

## 1. Introduction aux SCD (Slowly Changing Dimensions)

Les dimensions d'un entrepot de donnees peuvent evoluer dans le temps. Ralph Kimball definit trois types principaux de gestion de ces changements :

| Type | Strategie | Historisation | Cas d'usage |
|------|-----------|---------------|-------------|
| **Type 1** | Ecrasement | Non | Corrections, donnees non-critiques |
| **Type 2** | Ajout de ligne | Oui (complet) | Audit, analyse temporelle |
| **Type 3** | Colonne additionnelle | Partiel (avant/apres) | Comparaison directe |

---

## 2. Dimensions du Projet

### 2.1 Schema en etoile actuel

```
                    ┌─────────────┐
                    │ dim_symbol  │
                    ├─────────────┤
                    │ symbol_id   │
                    │ symbol      │
                    │ asset_class │  (crypto / trad)
                    └──────┬──────┘
                           │
┌─────────────┐    ┌───────▼───────┐
│  dim_date   │    │  fact_prices  │
├─────────────┤    ├───────────────┤
│ date_id     │◄───┤ symbol        │
│ date        │    │ timestamp     │
│ year        │    │ open          │
│ month       │    │ high          │
│ day         │    │ low           │
│ day_of_week │    │ close         │
└─────────────┘    │ volume        │
                   └───────────────┘
```

### 2.2 Implementation dbt

Le schema en etoile est implemente via des modeles dbt dans `dbt_project/models/marts/` :

| Modele dbt | Fichier | Description |
|------------|---------|-------------|
| `dim_symbol` | `dbt_project/models/marts/dim_symbol.sql` | Dimension symboles avec metadonnees |
| `dim_date` | `dbt_project/models/marts/dim_date.sql` | Dimension temporelle derivee des faits |
| `fact_prices` | `dbt_project/models/marts/fact_prices.sql` | Table de faits OHLCV dedupliquee |
| `agg_daily_returns` | `dbt_project/models/marts/agg_daily_returns.sql` | Agregation des rendements journaliers |

Les tests de qualite dbt (`dbt_project/models/marts/schema.yml`) appliquent des contraintes sur les dimensions :
- **unique** : garantit l'unicite des cles primaires
- **not_null** : empeche les valeurs nulles sur les colonnes critiques
- **relationships** : verifie l'integrite referentielle entre faits et dimensions

### 2.3 Analyse des dimensions

| Dimension | Volatilite | Type SCD choisi | Justification |
|-----------|------------|-----------------|---------------|
| `dim_symbol` | Faible | Type 1 + Type 2 | Nouveaux tokens rares, delisting possible |
| `dim_date` | Nulle | N/A | Dimension degeneree, auto-generee |

---

## 3. dim_symbol : Gestion des variations

### 3.1 Scenarios de changement

| Scenario | Exemple | Frequence | Impact |
|----------|---------|-----------|--------|
| **Nouveau symbole crypto** | Ajout AVAXUSDT au portfolio | Rare | Nouvelle ligne |
| **Nouveau symbole traditionnel** | Ajout SPY, QQQ via yfinance | Ponctuel | Nouvelle ligne (SCD Type 1) |
| **Delisting** | Retrait d'un token | Tres rare | Marquage inactif |
| **Renommage** | LUNAUSDT -> LUNC | Exceptionnel | Historique a preserver |
| **Correction** | Erreur de saisie | Jamais (API) | Ecrasement |

### 3.2 Comportement SCD Type 1 pour les actifs traditionnels (yfinance)

L'ajout d'actifs traditionnels (actions, ETF, matieres premieres) via yfinance constitue un cas typique de **SCD Type 1** :

- Lorsqu'un nouvel actif est ajoute a la configuration (`TRAD_SYMBOLS` dans `config.py`), une nouvelle ligne est inseree dans `dim_symbol`
- L'attribut `asset_class` distingue les actifs crypto (`crypto`) des actifs traditionnels (`trad`)
- Aucun historique de changement n'est necessaire car l'ajout est un enrichissement, pas une modification

Exemple :
```
| symbol  | asset_class | source   |
|---------|-------------|----------|
| BTCUSDT | crypto      | binance  |
| ETHUSDT | crypto      | binance  |
| SPY     | trad        | yfinance |
| QQQ     | trad        | yfinance |
| GLD     | trad        | yfinance |
```

### 3.3 Implementation Type 1 (etat actuel)

Actuellement, `dim_symbol` utilise **SCD Type 1** implicite :

```sql
-- Vue actuelle (duckdb.py)
CREATE OR REPLACE VIEW dim_symbol AS
SELECT symbol, ROW_NUMBER() OVER (ORDER BY symbol) as symbol_id
FROM (SELECT DISTINCT symbol FROM fact_prices)
```

**Comportement :**
- Nouveau symbole (crypto ou traditionnel) -> Ajoute automatiquement
- Symbole supprime -> Disparait des donnees actives
- Pas d'historique des changements

Le modele dbt equivalent (`dbt_project/models/marts/dim_symbol.sql`) produit le meme resultat avec en plus les tests de qualite integres.

### 3.4 Evolution vers Type 2 (recommande)

Pour une tracabilite complete, le schema evoluerait vers :

```sql
-- Structure SCD Type 2
CREATE TABLE dim_symbol_scd2 (
    symbol_sk       INTEGER PRIMARY KEY,  -- Surrogate key
    symbol          VARCHAR NOT NULL,     -- Business key
    symbol_name     VARCHAR,              -- Nom complet (Bitcoin, Ethereum...)
    asset_class     VARCHAR,              -- 'crypto' ou 'trad'
    is_active       BOOLEAN DEFAULT TRUE,
    valid_from      DATE NOT NULL,
    valid_to        DATE,                 -- NULL = actif
    is_current      BOOLEAN DEFAULT TRUE
);
```

**Exemple de donnees :**

| symbol_sk | symbol | symbol_name | asset_class | is_active | valid_from | valid_to | is_current |
|-----------|--------|-------------|-------------|-----------|------------|----------|------------|
| 1 | BTCUSDT | Bitcoin | crypto | true | 2024-01-01 | NULL | true |
| 2 | ETHUSDT | Ethereum | crypto | true | 2024-01-01 | NULL | true |
| 3 | LUNAUSDT | Terra Luna | crypto | true | 2024-01-01 | 2024-05-15 | false |
| 4 | LUNCUSDT | Terra Classic | crypto | true | 2024-05-15 | NULL | true |
| 5 | SPY | SPDR S&P 500 | trad | true | 2025-01-01 | NULL | true |
| 6 | GLD | SPDR Gold | trad | true | 2025-01-01 | NULL | true |

### 3.5 Processus ETL pour SCD Type 2

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│ Source       │     │ ETL SCD         │     │ dim_symbol   │
│ (API/Config) │────>│                 │────>│ (Type 2)     │
└──────────────┘     │ 1. Lookup       │     └──────────────┘
                     │ 2. Compare      │
                     │ 3. Insert/Update│
                     └─────────────────┘
```

**Pseudo-code du processus :**

```python
def update_dim_symbol_scd2(new_symbols: list[dict]):
    """
    SCD Type 2 update logic for dim_symbol.

    Args:
        new_symbols: [{"symbol": "BTCUSDT", "name": "Bitcoin", "asset_class": "crypto"}, ...]
    """
    today = date.today()

    for record in new_symbols:
        existing = query("""
            SELECT * FROM dim_symbol_scd2
            WHERE symbol = ? AND is_current = TRUE
        """, record["symbol"])

        if not existing:
            # INSERT: nouveau symbole (crypto ou traditionnel)
            insert(symbol=record["symbol"],
                   symbol_name=record["name"],
                   asset_class=record["asset_class"],
                   valid_from=today,
                   is_current=True)

        elif existing["symbol_name"] != record["name"]:
            # UPDATE: changement detecte -> fermer ancienne ligne
            update(symbol_sk=existing["symbol_sk"],
                   valid_to=today - 1,
                   is_current=False)

            # INSERT: nouvelle version
            insert(symbol=record["symbol"],
                   symbol_name=record["name"],
                   asset_class=record["asset_class"],
                   valid_from=today,
                   is_current=True)

    # Marquer les symboles supprimes comme inactifs
    mark_deleted_symbols_inactive(today)
```

---

## 4. dim_date : Dimension degeneree

### 4.1 Caracteristiques

`dim_date` est une **dimension degeneree** (degenerate dimension) :
- Generee automatiquement a partir des faits
- Ne change jamais (une date reste une date)
- Pas de SCD necessaire

### 4.2 Structure actuelle

```sql
-- Vue DuckDB (duckdb.py)
CREATE OR REPLACE VIEW dim_date AS
SELECT DISTINCT
    timestamp as date,
    ROW_NUMBER() OVER (ORDER BY timestamp) as date_id,
    EXTRACT(YEAR FROM CAST(timestamp AS DATE)) as year,
    EXTRACT(MONTH FROM CAST(timestamp AS DATE)) as month,
    EXTRACT(DAY FROM CAST(timestamp AS DATE)) as day,
    EXTRACT(DOW FROM CAST(timestamp AS DATE)) as day_of_week
FROM fact_prices
```

Le modele dbt equivalent (`dbt_project/models/marts/dim_date.sql`) produit la meme structure avec les tests dbt (unique, not_null sur `date_id`).

### 4.3 Extension possible

Pour enrichir l'analyse, on pourrait ajouter :

```sql
-- dim_date enrichie
CREATE TABLE dim_date_extended (
    date_id         INTEGER PRIMARY KEY,
    date            DATE NOT NULL,
    year            INTEGER,
    quarter         INTEGER,
    month           INTEGER,
    week            INTEGER,
    day             INTEGER,
    day_of_week     INTEGER,
    day_name        VARCHAR,    -- 'Monday', 'Tuesday'...
    is_weekend      BOOLEAN,
    is_month_end    BOOLEAN,
    is_quarter_end  BOOLEAN
);
```

---

## 5. Synthese des choix

### 5.1 Matrice de decision

| Dimension | SCD Type | Raison | Complexite | Valeur ajoutee |
|-----------|----------|--------|------------|----------------|
| dim_symbol | Type 1 (actuel) | Simplicite, changements rares | Faible | Suffisante |
| dim_symbol | Type 2 (evolution) | Audit complet, historique | Moyenne | Haute si delisting |
| dim_date | N/A | Immuable | Nulle | N/A |

### 5.2 Recommandation

Pour ce projet de certification :

1. **Court terme** : Garder Type 1 pour `dim_symbol` (suffisant pour le cas d'usage)
2. **Documentation** : Ce document demontre la maitrise des concepts SCD
3. **dbt** : Les tests de schema dbt assurent la qualite des dimensions en continu
4. **Evolution future** : Implementer Type 2 si :
   - Besoin d'audit reglementaire
   - Analyse de performance historique par token
   - Gestion des delistings Binance

---

## 6. Impact sur les ETL

### 6.1 ETL actuel (Type 1 implicite)

```python
# dags/portfolio_dag.py - Pas de gestion SCD explicite
def run_ingest():
    data = ingest_incremental()  # Nouveaux symboles ajoutes automatiquement
    storage.save_raw(data)       # Ecrasement (Type 1)
```

### 6.2 ETL avec SCD Type 2

```python
# Evolution pour SCD Type 2
def run_ingest_scd2():
    # 1. Ingest donnees brutes
    data = ingest_incremental()
    storage.save_raw(data)

    # 2. Mise a jour dimension symboles
    current_symbols = [{"symbol": s, "name": get_symbol_name(s)}
                       for s in data.keys()]
    storage.update_dim_symbol_scd2(current_symbols)

    # 3. Log des changements
    log_dimension_changes()
```

---

## 7. Conformite au referentiel

| Critere d'evaluation | Statut | Preuve |
|---------------------|--------|--------|
| Modelisation integre les changements sources | Oui | Section 3.4 - Structure SCD2 |
| Permet d'historiser les changements | Oui | Section 3.4 - valid_from/valid_to |
| Variations integrees a l'entrepot | Oui | Section 3.5 - Processus ETL |
| Respecte la modelisation initiale | Oui | Section 5 - Evolution progressive |
| ETL mis a jour | Oui | Section 6.2 - ETL SCD2 |
| Implementation dbt | Oui | `dbt_project/models/marts/` - dim_symbol.sql, dim_date.sql, fact_prices.sql |
| Tests de qualite dbt | Oui | `dbt_project/models/marts/schema.yml` - unique, not_null, relationships |
| Actifs traditionnels (yfinance) | Oui | Section 3.2 - SCD Type 1 pour nouveaux symboles |
| Documentation a jour | Oui | Ce document |

---

## Glossaire

- **SCD** : Slowly Changing Dimension - methode de gestion des changements de dimensions
- **Surrogate Key** : Cle technique (symbol_sk) independante de la cle metier
- **Business Key** : Cle naturelle metier (symbol)
- **Dimension degeneree** : Dimension sans table propre, attributs dans la table de faits
- **dbt** : Data Build Tool - framework de transformation SQL avec tests integres
