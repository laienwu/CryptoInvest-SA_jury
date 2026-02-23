# ADR-002 : DuckDB comme moteur d'entrepôt de données

**Statut :** Accepté
**Date :** 2025-01-08
**Décideurs :** Laien Wu (ingénieur de données), Sophie Bernard (analyste de données)
**Histoire technique :** US-008

---

## Contexte

Nous avons besoin d'une interface SQL pour les requêtes analytiques sur notre Data Lake. Exigences :

- Prise en charge SQL pour les utilisateurs professionnels (Sophie, analystes)
- Prise en charge du schéma en étoile (faits et dimensions)
- Intégration avec les fichiers Parquet existants
- Faible surcharge opérationnelle (projet de certification)
- Assez rapide pour une utilisation interactive requêtes

Options considérées :
1. PostgreSQL
2. CanardDB
3. SQLite
4. Apache Spark SQL
5. ClickHouse

---

## Décision

**Nous utiliserons DuckDB comme entrepôt de données intégré moteur.**

---

## Justification

### Matrice de comparaison :

| Critère | PostgreSQL | CanardDB | SQLite | SparkSQL | ClickHouse |
|-----------|------------|--------|--------|-----------|------------|
| Complexité de configuration | Moyen | Zéro | Zéro | Élevé | Moyen |
| Parquet natif | Non | Oui | Non | Oui | Limité |
| OLAP optimisé | Non | Oui | Non | Oui | Oui |
| Mode intégré | Non | Oui | Oui | Non | Non |
| Efficacité de la mémoire | Bon | Excellent | Bon | Pauvre | Bon |
| Courbe d'apprentissage | Faible | Faible | Faible | Élevé | Moyen |

### Facteurs clés :

1. **Zéro infrastructure** : DuckDB s'exécute en cours de processus, aucun serveur à gérer. Parfait pour la portée du projet de certification.

2. **Parquet-native** : interroge les fichiers Parquet directement sans ETL :
   ```sql
   SELECT * FROM 'data/raw/klines/*.parquet'
   ```

3. **Optimisé pour OLAP** : moteur de colonnes conçu pour les requêtes analytiques (agrégations, jointures sur de grandes tables).

4. **SQL familier** : syntaxe SQL standard, simple pour Sophie et les utilisateurs professionnels.

5. **Intégration Python** : fonctionne de manière transparente avec les tables PyArrow.

### Pourquoi pas PostgreSQL :
- Nécessite une gestion du serveur (conteneur Docker, sauvegardes, surveillance)
- Les données doivent être chargées dans des tables (étape ETL)
- Stockage basé sur les lignes moins efficace pour Analytics
- Surpuissance pour la charge de travail analytique d'un seul utilisateur

### Pourquoi pas Spark :
- Surcharge massive pour les petites données (à l'échelle de ~ Mo)
- Complexité de la gestion des clusters
- Temps de démarrage lent
- Serait approprié à la To échelle

---

## Conséquences

### Positif[
- Aucune surcharge opérationnelle
- Interroger Parquet directement (pas d'ETL)
- Analyse rapide requêtes (exécution vectorisée)
- Connexion en mémoire (aucun fichier d'entrepôt à maintenir)
- Excellente intégration Python/PyArrow

### Négatif
- Ne convient pas aux charges de travail d'écriture simultanées
- Aucune réplication/HA intégrée
- Moins d'écosystème d'outils que PostgreSQL
- Relativement nouveau (moins testé au combat)

### Neutre
- Schéma en étoile implémenté dans le code, pas dans les contraintes de base de données
- Aucune application de clé étrangère (gérée dans ETL)

---

## Conformité

| Exigence | Statut |
|-------------|--------|
| C9 - Requêtes d'extraction SQL | Prise en charge complète de SQL |
| C13 - Modélisation faits/dimensions | Schéma en étoile implémenté |
| C14 - Créer un entrepôt | DuckDB = entrepôt analytique |
| C15 - Intégration ETL | Lire depuis Parquet via vues DuckDB |

---

## Implémentation

### Star Schema

```
        ┌──────────────┐
        │  dim_date    │
        │──────────────│
        │ date_key (PK)│
        │ full_date    │
        │ year         │
        │ month        │
        │ day_of_week  │
        └──────┬───────┘
               │
┌──────────────┼──────────────┐
│              │              │
│       ┌──────┴───────┐      │
│       │ fact_prices  │      │
│       │──────────────│      │
│       │ symbol (FK)  │──────┼──────┐
│       │ date_key (FK)│      │      │
│       │ open         │      │      │
│       │ high         │      │      │
│       │ low          │      │      │
│       │ close        │      │      │
│       │ volume       │      │      │
│       └──────────────┘      │      │
│                             │      │
└─────────────────────────────┘      │
                                     │
                              ┌──────┴───────┐
                              │  dim_symbol  │
                              │──────────────│
                              │ symbol (PK)  │
                              │ name         │
                              │ sector       │
                              │ category     │
                              └──────────────┘
```

### Exemple de code

```python
from src.storage.duckdb import DuckDBStorage

# Query star-schema views built on Parquet files
with DuckDBStorage() as db:
    result = db.query("""
        SELECT
            symbol,
            COUNT(*) as num_records,
            AVG(close) as avg_close
        FROM fact_prices
        GROUP BY symbol
        ORDER BY num_records DESC
    """)
    print(result[:5])
```

---

## Références

- [Documentation DuckDB](https://duckdb.org/docs/)
- [Exemple de schéma en étoile DuckDB](https://duckdb.org/docs/guides/star_schema)
- [Pourquoi DuckDB (Hacker News)](https://news.ycombinator.com/item?id=29658553)

---

*Révisé par : Sophie Bernard (Analyste de données)*
*Approuvé par : Marie Dupont (Propriétaire du produit)*

