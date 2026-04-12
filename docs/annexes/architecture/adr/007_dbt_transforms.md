# ADR-007 : dbt pour les transformations SQL du Data Warehouse

## Statut
Accepte

## Contexte
La couche data warehouse utilise DuckDB avec un schema en etoile (`fact_prices`, `dim_symbol`, `dim_date`). Actuellement, toutes les transformations sont implementees en Python (PyArrow). Meme si cela fonctionne bien pour le pipeline, les transformations basees sur SQL offrent :
- **Modelisation declarative des donnees** : SQL est la lingua franca de l'analytique
- **Tests integres** : dbt fournit des tests de schema, des tests de donnees et des controles de fraicheur
- **Lignage des donnees** : DAG automatique des dependances entre modeles
- **Documentation** : catalogue de donnees genere automatiquement a partir des fichiers YAML de schema

## Decision
Ajouter un **projet dbt** avec l'adaptateur `dbt-duckdb` pour les transformations de la couche data warehouse. Les modeles dbt completent le pipeline Python existant, sans le remplacer.

### Structure du projet :
- `staging/` : lecture des fichiers Parquet bruts, cast des types, nettoyage des donnees
- `marts/` : tables du schema en etoile (`fact_prices`, `dim_symbol`, `dim_date`)
- `marts/` : agregats (rendements journaliers, synthese portefeuille)
- `tests/` : assertions personnalisees de qualite des donnees
- `macros/` : SQL reutilisable (rendements logarithmiques)

### Integration :
- dbt s'execute comme une tache `BashOperator` Airflow apres le pipeline ETL Python
- dbt utilise le meme fichier DuckDB de data warehouse (`data/warehouse.duckdb`)

## Consequences

### Positives
- Transformations nativement SQL pour les membres de l'equipe analytique
- Tests de donnees et documentation integres
- Graphe de lignage automatique via `dbt docs generate`
- Pratique standard dans les stacks modernes de data engineering

### Negatives
- Dependances supplementaires (`dbt-core`, `dbt-duckdb`)
- Deux systemes de transformation a maintenir (pipeline Python + dbt)
- Necessite de comprendre les deux paradigmes

### Neutres
- dbt opere uniquement sur la couche data warehouse ; les zones Bronze/Silver restent gerees en Python
- dbt peut etre execute independamment ou via Airflow
