# ADR-001 : Parquet comme format de stockage principal

**Statut :** Accepté
**Date :** 2025-01-06
**Décideurs :** Laien Wu (Data Engineer), Pierre Durand (DevOps)
**Histoire technique :** US-001, US-002

---

## Contexte

Nous devons stocker des données de prix de séries chronologiques provenant de plusieurs sources de crypto-monnaie. Le format de stockage doit prendre en charge :

- Requêtes en colonnes efficaces (agrégations, filtrage par date)
- Application du schéma pour la qualité des données
- Compression pour une meilleure rentabilité
- Compatibilité avec notre pile d'analyse (DuckDB, Python)

Options considérées :
1. Fichiers CSV
2. Fichiers JSON
3. Parquet Apache
4. Lac Delta
5. Tables PostgreSQL

---

## Décision

**Nous utiliserons Apache Parquet comme format de stockage principal pour les données Lac.**

---

## Justification

### Pourquoi le parquet plutôt que les alternatives :

| Critère | CSV | JSON | Parquet | Lac Delta | PostgreSQL |
|-----------|-----|------|---------|------------|------------|
| Requêtes en colonnes | Pauvre | Pauvre | Excellent | Excellent | Bon |
| Compression | Aucun | Aucun | Snappy/Zstd | Snappy/Zstd | Limité |
| Application du schéma | Aucun | Partielle | Fort | Fort | Fort |
| Complexité de l'outillage | Faible | Faible | Faible | Moyen | Moyen |
| Prise en charge native de DuckDB | Oui | Oui | Excellent | Limité | Externe |
| Basé sur des fichiers (pas de serveur) | Oui | Oui | Oui | Oui | Non |

### Facteurs clés de la décision :

1. **Performances** : le format en colonnes de Parquet est 10 à 100 fois plus rapide pour les requêtes analytiques (colonnes spécifiques SELECT, agrégations) par rapport aux formats basés sur les lignes.

2. **Compression** : la compression Snappy permet d'obtenir une réduction de taille de 5 à 10 fois par rapport au CSV tout en maintenant une décompression rapide.

3. **Schéma** : le schéma intégré empêche la dérive du type de données et la structure des documents.

4. **DuckDB natif** : DuckDB lit Parquet directement sans copie, permettant des requêtes SQL sans ETL.

5. **Simplicité** : contrairement à Delta Lake, Parquet ne nécessite aucun runtime ni dépendance supplémentaire.

### Pourquoi pas Delta Lake :
- Ajoute de la complexité (dépendance delta-rs, journaux de transactions)
- Transactions ACID non requises pour les chargements par lots quotidiens
- Ce serait excessif pour le volume de données actuel (~ 50 Ko/jour)

### Pourquoi pas PostgreSQL pour les données brutes :
- Nécessite une gestion de serveur
- Le modèle Data Lake préfère le stockage basé sur des fichiers
- DuckDB fournit SQL sans surcharge opérationnelle

---

## Conséquences

### Positif
- Requêtes analytiques rapides via DuckDB
- Schéma auto-documenté dans les fichiers
- 80 % de réduction de stockage par rapport à CSV
- Aucun serveur de base de données à gérer
- Sauvegarde facile (il suffit de copier fichiers)

### Négatif
- Non lisible par l'homme (contrairement à CSV/JSON)
- Nécessite la bibliothèque PyArrow
- Aucune mise à jour au niveau des lignes (modèle d'ajout uniquement)
- Moins familier à certaines équipes membres

### Neutre
- Courbe d'apprentissage pour l'API PyArrow
- Besoin d'outils de parquet pour l'inspection des fichiers

---

## Conformité

| Exigence | Statut |
|-------------|--------|
| C11 - Création de base de données | Schéma Parquet = schéma DB implicite |
| C18 - Architecture du lac de données | Le stockage basé sur des fichiers correspond au modèle Lake |
| C19 - Intégration de composants | Intégration native DuckDB/PyArrow |

---

## Implémentation

```python
# Writing Parquet with PyArrow
import pyarrow as pa
import pyarrow.parquet as pq

schema = pa.schema([
    ("symbol", pa.string()),
    ("timestamp", pa.timestamp("ms")),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.float64()),
])

table = pa.Table.from_pydict(data, schema=schema)
pq.write_table(table, "data/raw/klines/BTCUSDT.parquet")
```

---

## Références

- [Documentation Apache Parquet](https://parquet.apache.org/)
- [Support DuckDB Parquet](https://duckdb.org/docs/data/parquet)
- [Guide Parquet PyArrow](https://arrow.apache.org/docs/python/parquet.html)

---

*Révisé par : Pierre Durand (DevOps)*
*Approuvé par : Marie Dupont (Propriétaire du produit)*

