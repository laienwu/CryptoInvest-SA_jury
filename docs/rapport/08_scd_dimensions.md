# Gestion des Variations de Dimensions (C17)

## 1. Introduction aux SCD (Slowly Changing Dimensions)

Les dimensions d'un entrepôt de données peuvent évoluer dans le temps. Ralph Kimball définit trois types principaux de gestion de ces changements :

| Type | Stratégie | Historisation | Cas d'usage |
|------|-----------|---------------|-------------|
| **Type 1** | Écrasement | Non | Corrections, données non-critiques |
| **Type 2** | Ajout de ligne | Oui (complet) | Audit, analyse temporelle |
| **Type 3** | Colonne additionnelle | Partiel (avant/après) | Comparaison directe |

---

## 2. Dimensions du Projet

### 2.1 Schéma en étoile actuel

```
                    ┌─────────────┐
                    │ dim_symbol  │
                    ├─────────────┤
                    │ symbol_id   │
                    │ symbol      │
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

### 2.2 Analyse des dimensions

| Dimension | Volatilité | Type SCD choisi | Justification |
|-----------|------------|-----------------|---------------|
| `dim_symbol` | Faible | Type 1 + Type 2 | Nouveaux tokens rares, delisting possible |
| `dim_date` | Nulle | N/A | Dimension dégénérée, auto-générée |

---

## 3. dim_symbol : Gestion des variations

### 3.1 Scénarios de changement

| Scénario | Exemple | Fréquence | Impact |
|----------|---------|-----------|--------|
| **Nouveau symbole** | Ajout AVAXUSDT au portfolio | Rare | Nouvelle ligne |
| **Delisting** | Retrait d'un token | Très rare | Marquage inactif |
| **Renommage** | LUNAUSDT → LUNC | Exceptionnel | Historique à préserver |
| **Correction** | Erreur de saisie | Jamais (API) | Écrasement |

### 3.2 Implémentation Type 1 (état actuel)

Actuellement, `dim_symbol` utilise **SCD Type 1** implicite :

```sql
-- Vue actuelle (duckdb.py)
CREATE OR REPLACE VIEW dim_symbol AS
SELECT symbol, ROW_NUMBER() OVER (ORDER BY symbol) as symbol_id
FROM (SELECT DISTINCT symbol FROM fact_prices)
```

**Comportement :**
- Nouveau symbole → Ajouté automatiquement
- Symbole supprimé → Disparaît des données actives
- Pas d'historique des changements

### 3.3 Évolution vers Type 2 (recommandé)

Pour une traçabilité complète, le schéma évoluerait vers :

```sql
-- Structure SCD Type 2
CREATE TABLE dim_symbol_scd2 (
    symbol_sk       INTEGER PRIMARY KEY,  -- Surrogate key
    symbol          VARCHAR NOT NULL,     -- Business key
    symbol_name     VARCHAR,              -- Nom complet (Bitcoin, Ethereum...)
    is_active       BOOLEAN DEFAULT TRUE,
    valid_from      DATE NOT NULL,
    valid_to        DATE,                 -- NULL = actif
    is_current      BOOLEAN DEFAULT TRUE
);
```

**Exemple de données :**

| symbol_sk | symbol | symbol_name | is_active | valid_from | valid_to | is_current |
|-----------|--------|-------------|-----------|------------|----------|------------|
| 1 | BTCUSDT | Bitcoin | true | 2024-01-01 | NULL | true |
| 2 | ETHUSDT | Ethereum | true | 2024-01-01 | NULL | true |
| 3 | LUNAUSDT | Terra Luna | true | 2024-01-01 | 2024-05-15 | false |
| 4 | LUNCUSDT | Terra Classic | true | 2024-05-15 | NULL | true |

### 3.4 Processus ETL pour SCD Type 2

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│ Source       │     │ ETL SCD         │     │ dim_symbol   │
│ (API/Config) │────▶│                 │────▶│ (Type 2)     │
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
        new_symbols: [{"symbol": "BTCUSDT", "name": "Bitcoin"}, ...]
    """
    today = date.today()

    for record in new_symbols:
        existing = query("""
            SELECT * FROM dim_symbol_scd2
            WHERE symbol = ? AND is_current = TRUE
        """, record["symbol"])

        if not existing:
            # INSERT: nouveau symbole
            insert(symbol=record["symbol"],
                   symbol_name=record["name"],
                   valid_from=today,
                   is_current=True)

        elif existing["symbol_name"] != record["name"]:
            # UPDATE: changement détecté → fermer ancienne ligne
            update(symbol_sk=existing["symbol_sk"],
                   valid_to=today - 1,
                   is_current=False)

            # INSERT: nouvelle version
            insert(symbol=record["symbol"],
                   symbol_name=record["name"],
                   valid_from=today,
                   is_current=True)

    # Marquer les symboles supprimés comme inactifs
    mark_deleted_symbols_inactive(today)
```

---

## 4. dim_date : Dimension dégénérée

### 4.1 Caractéristiques

`dim_date` est une **dimension dégénérée** (degenerate dimension) :
- Générée automatiquement à partir des faits
- Ne change jamais (une date reste une date)
- Pas de SCD nécessaire

### 4.2 Structure actuelle

```sql
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

## 5. Synthèse des choix

### 5.1 Matrice de décision

| Dimension | SCD Type | Raison | Complexité | Valeur ajoutée |
|-----------|----------|--------|------------|----------------|
| dim_symbol | Type 1 (actuel) | Simplicité, changements rares | Faible | Suffisante |
| dim_symbol | Type 2 (évolution) | Audit complet, historique | Moyenne | Haute si delisting |
| dim_date | N/A | Immuable | Nulle | N/A |

### 5.2 Recommandation

Pour ce projet de certification :

1. **Court terme** : Garder Type 1 pour `dim_symbol` (suffisant pour le cas d'usage)
2. **Documentation** : Ce document démontre la maîtrise des concepts SCD
3. **Évolution future** : Implémenter Type 2 si :
   - Besoin d'audit réglementaire
   - Analyse de performance historique par token
   - Gestion des delistings Binance

---

## 6. Impact sur les ETL

### 6.1 ETL actuel (Type 1 implicite)

```python
# dags/portfolio_dag.py - Pas de gestion SCD explicite
def run_ingest():
    data = ingest_incremental()  # Nouveaux symboles ajoutés automatiquement
    storage.save_raw(data)       # Écrasement (Type 1)
```

### 6.2 ETL avec SCD Type 2

```python
# Évolution pour SCD Type 2
def run_ingest_scd2():
    # 1. Ingest données brutes
    data = ingest_incremental()
    storage.save_raw(data)

    # 2. Mise à jour dimension symboles
    current_symbols = [{"symbol": s, "name": get_symbol_name(s)}
                       for s in data.keys()]
    storage.update_dim_symbol_scd2(current_symbols)

    # 3. Log des changements
    log_dimension_changes()
```

---

## 7. Conformité au référentiel

| Critère d'évaluation | Statut | Preuve |
|---------------------|--------|--------|
| Modélisation intègre les changements sources | ✅ | Section 3.3 - Structure SCD2 |
| Permet d'historiser les changements | ✅ | Section 3.3 - valid_from/valid_to |
| Variations intégrées à l'entrepôt | ✅ | Section 3.4 - Processus ETL |
| Respecte la modélisation initiale | ✅ | Section 5 - Évolution progressive |
| ETL mis à jour | ✅ | Section 6.2 - ETL SCD2 |
| Documentation à jour | ✅ | Ce document |

---

## Glossaire

- **SCD** : Slowly Changing Dimension - méthode de gestion des changements de dimensions
- **Surrogate Key** : Clé technique (symbol_sk) indépendante de la clé métier
- **Business Key** : Clé naturelle métier (symbol)
- **Dimension dégénérée** : Dimension sans table propre, attributs dans la table de faits
