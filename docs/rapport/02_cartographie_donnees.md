# Cartographie des Données (C2)

## 1. Inventaire des sources

### 1.1 Source principale : API Binance

| Attribut | Valeur |
|----------|--------|
| **Type** | API REST publique |
| **URL** | `https://api.binance.com/api/v3/klines` |
| **Authentification** | Aucune (données publiques) |
| **Rate limit** | 1200 requêtes/minute |
| **Format** | JSON |

### 1.2 Données disponibles

| Endpoint | Description | Fréquence |
|----------|-------------|-----------|
| `/klines` | Données OHLCV (candlesticks) | Temps réel |
| `/ticker/price` | Prix actuel | Temps réel |
| `/exchangeInfo` | Métadonnées symboles | Statique |

---

## 2. Glossaire métier (Sémantique)

| Terme | Définition |
|-------|------------|
| **OHLCV** | Open, High, Low, Close, Volume - données de chandelier |
| **Symbol** | Paire de trading (ex: BTCUSDT = Bitcoin vs Tether) |
| **Kline** | Chandelier japonais sur une période donnée |
| **Interval** | Période du chandelier (1d = journalier) |
| **Rendement** | Variation relative du prix entre deux périodes |
| **Volatilité** | Écart-type annualisé des rendements |
| **Corrélation** | Mesure de co-mouvement entre deux actifs |
| **Covariance** | Mesure de variance conjointe |
| **Sharpe Ratio** | Rendement ajusté au risque |

---

## 3. Modèles de données

### 3.1 Données brutes (Bronze)

**Schéma klines** :
```
timestamp : STRING (ISO 8601)
open      : FLOAT64
high      : FLOAT64
low       : FLOAT64
close     : FLOAT64
volume    : FLOAT64
```

**Stockage** : `data/raw/klines/{SYMBOL}.parquet`

### 3.2 Données transformées (Silver)

**returns.parquet** :
```
date   : STRING
symbol : STRING
value  : FLOAT64 (rendement journalier)
```

**volatility.parquet** :
```
symbol : STRING
value  : FLOAT64 (volatilité annualisée)
```

**correlation.parquet / covariance.parquet** :
```
symbol_row : STRING
symbol_col : STRING
value      : FLOAT64
```

### 3.3 Données agrégées (Gold)

**weights.json** :
```json
{
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "weights": {"BTCUSDT": 0.6, "ETHUSDT": 0.4},
  "expected_return": 0.15,
  "volatility": 0.25,
  "sharpe_ratio": 0.6
}
```

---

## 4. Modèle dimensionnel (Star Schema)

### 4.1 Table de faits
```
**fact_prices** :
| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | FK vers dim_symbol |
| timestamp | STRING | FK vers dim_date |
| open | FLOAT64 | Prix d'ouverture |
| high | FLOAT64 | Prix le plus haut |
| low | FLOAT64 | Prix le plus bas |
| close | FLOAT64 | Prix de clôture |
| volume | FLOAT64 | Volume échangé |

```
### 4.2 Tables de dimensions

```
**dim_symbol** :
| Colonne | Type | Description |
|---------|------|-------------|
| symbol_id | INT | Clé primaire |
| symbol | STRING | Code symbole (BTCUSDT) |

**dim_date** :
| Colonne | Type | Description |
|---------|------|-------------|
| date_id | INT | Clé primaire |
| date | STRING | Date ISO |
| year | INT | Année |
| month | INT | Mois |
| day | INT | Jour |
| day_of_week | INT | Jour de semaine |
```
### 4.3 Schéma visuel

```
                    ┌─────────────┐
                    │ dim_symbol  │
                    ├─────────────┤
                    │ symbol_id   │
                    │ symbol      │
                    └──────┬──────┘
                           │
┌─────────────┐    ┌───────┴───────┐
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

---

## 5. Flux de données

### 5.1 Matrice des flux

| Source | Destination | Fréquence | Volume | Format |
|--------|-------------|-----------|--------|--------|
| Binance API | data/raw/ | Quotidien | ~1KB/symbol/jour | Parquet |
| data/raw/ | data/processed/ | Quotidien | ~5KB | Parquet |
| data/processed/ | data/output/ | Quotidien | ~1KB | JSON |
| data/ | API REST | On-demand | Variable | JSON |

### 5.2 Pipeline ETL

```
[Binance API]
      │
      ▼ ingest.py (Extract)
[data/raw/klines/]
      │
      ▼ transform.py (Transform)
[data/processed/]
      │
      ▼ optimize.py (Load)
[data/output/]
      │
      ▼ FastAPI (Expose)
[Utilisateurs]
```

---

## 6. Accès et autorisations

### 6.1 Accès aux sources

| Source | Méthode | Authentification |
|--------|---------|------------------|
| Binance API | HTTPS GET | Aucune (public) |
| Parquet files | Filesystem | Permissions OS |
| DuckDB | In-memory | N/A |
| FastAPI | HTTP | Aucune (MVP) |

### 6.2 Données manquantes identifiées
- Métadonnées des symboles (market cap, sector)
- Données fondamentales (pas disponibles pour crypto)
- Historique > 1 an (limite API)

---

## 7. Qualité des données

### 7.1 Contrôles implémentés
- Validation du schéma Parquet
- Détection valeurs nulles
- Vérification continuité temporelle

### 7.2 Métriques de qualité
| Métrique | Cible | Actuel |
|----------|-------|--------|
| Complétude | 100% | 100% |
| Unicité | 100% | 100% |
| Fraîcheur | < 24h | OK |
