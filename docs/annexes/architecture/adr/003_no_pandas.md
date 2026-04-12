# ADR-003 : PyArrow au lieu de Pandas

**Statut :** Accepté
**Date :** 2025-01-08
**Décideurs :** Laien Wu (data engineer)
**Histoire technique :** Performance optimisation

---

## Contexte

Choix de bibliothèque de manipulation de données pour le pipeline ETL. Le pipeline traite les données OHLCV avec les opérations :

- Conversions de types
- Transformations de colonnes
- Agrégations (moyenne, standard, corrélation)
- E/S de fichier (lecture/écriture de parquet)

Options considéré :
1. Pandas
2. PyArrow (Apache Arrow)
3. Polars
4. Pure Python + NumPy

---

## Décision

**Nous utiliserons PyArrow directement pour la manipulation des données, en évitant la dépendance à Pandas.**

---

## Justification

### Comparaison :

| Critère | Pandas | PyArrow | Polars |
|-----------|--------|---------|--------|
| Efficacité de la mémoire | Faible | Excellent | Excellent |
| Parquet natif | Via PyArrow | Natif | Natif |
| Type de sécurité | Faible | Fort | Fort |
| Complexité des API | Faible | Moyen | Moyen |
| Maturité de l'écosystème | Excellent | Bon | Croissance |
| Poids de dépendance | Lourd | Léger | Léger |

### Facteurs clés :

1. **Efficacité de la mémoire** : PyArrow utilise des lectures sans copie et une disposition de la mémoire en colonnes. Pour notre ensemble de données de 450 enregistrements :
 - Pandas : ~2 Mo de surcharge de mémoire
 - PyArrow : ~50 Ko de taille réelle des données

2. **Sécurité des types** : le schéma Arrow applique les types au moment de la lecture, empêchant ainsi les bogues de coercition de type silencieux courants dans Pandas.

3. **Parquet natif** : PyArrow est la bibliothèque Parquet sous-jacente. Son utilisation directe évite les frais de conversion :
   ```python
   # Pandas (2 conversions)
   df = pd.read_parquet("file.parquet")  # Arrow → Pandas
   df.to_parquet("out.parquet")          # Pandas → Arrow

   # PyArrow (0 conversions)
   table = pq.read_table("file.parquet")  # Native Arrow
   pq.write_table(table, "out.parquet")   # Native Arrow
   ```

4. **Dépendance plus légère** : PyArrow ~ 30 Mo contre Pandas ~ 50 Mo (inclut NumPy).

5. **Intégration DuckDB** : DuckDB peut interroger les tables Arrow sans copie, impossible avec les Pandas DataFrames.

### Pourquoi pas Polars :
- Ajoute une autre dépendance
- Écosystème moins mature
- Équipe plus familiarisée avec les concepts Arrow/Pandas
- Ce serait un bon choix pour les ensembles de données plus volumineux

### Compromis accepté :
- L'API PyArrow est plus détaillée que Pandas pour certaines opérations
- Moins de méthodes « pratiques »
- Moins de couverture Stack Overflow

---

## Conséquences

### Positif
- Utilisation de la mémoire 10 à 50 fois inférieure
- E/S Parquet plus rapides (sans conversion)
- Garanties de type plus fortes
- Intégration DuckDB sans copie
- Image Docker plus légère

### Négatif
- Code plus détaillé pour les transformations
- Courbe d'apprentissage pour l'équipe
- Moins de tutoriels/exemples en ligne
- Certaines opérations nécessitent une implémentation manuelle

### Neutre
- NumPy toujours utilisé pour les calculs numériques (corrélation, covariance)
- Peut se convertir en Pandas si absolument nécessaire : `table.to_pandas()`

---

## Conformité

| Exigence | Statut |
|-------------|--------|
| C10 - Règles d'agrégation | Implémenté avec le calcul PyArrow |
| C19 - Intégration de composants | Intégration native avec DuckDB |

---

## Exemples d'implémentation

### Reading Parquet
```python
import pyarrow.parquet as pq

# Read with schema validation
table = pq.read_table(
    "data/raw/klines/BTCUSDT.parquet",
    columns=["timestamp", "close", "volume"]
)
```

### Transformation de colonne
```python
import pyarrow.compute as pc

# Calculate log returns
closes = table.column("close")
returns = pc.subtract(
    pc.ln(closes[1:]),
    pc.ln(closes[:-1])
)
```

### Agrégation
```python
# Mean and standard deviation
mean_price = pc.mean(table.column("close")).as_py()
std_price = pc.stddev(table.column("close")).as_py()
```

### Schéma de type sécurisé
```python
schema = pa.schema([
    ("symbol", pa.string()),
    ("timestamp", pa.timestamp("ms")),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.float64()),
])

# This will raise if data doesn't match schema
table = pa.Table.from_pydict(data, schema=schema)
```

---

## Chemin de migration

Si jamais nous avons besoin de la fonctionnalité Pandas :

```python
# One-way conversion (last resort)
df = table.to_pandas()

# Or use DuckDB for complex transformations
result = duckdb.query("""
    SELECT
        symbol,
        AVG(close) OVER (PARTITION BY symbol ORDER BY timestamp
                         ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as ma7
    FROM table
""").arrow()
```

---

## Références

- [Documentation Apache Arrow Python](https://arrow.apache.org/docs/python/)
- [Pourquoi Arrow plutôt que Pandas](https://towardsdatascience.com/stop-using-pandas-and-start-using-arrow-7e12e63c2fca)
- [Fonctions de calcul PyArrow](https://arrow.apache.org/docs/python/compute.html)

---

*Révisé par : Sophie Bernard (data analyst)*
*Approuvé par : Laien Wu (data engineer)*

