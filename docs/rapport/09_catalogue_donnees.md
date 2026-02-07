# Catalogue de Données (C20)

## 1. Vue d'ensemble du Data Lake

### 1.1 Architecture des zones

```
data/
├── raw/           # BRONZE - Données brutes
│   └── klines/    # OHLCV par symbole
├── processed/     # SILVER - Données transformées
│   ├── returns.parquet
│   ├── volatility.parquet
│   ├── correlation.parquet
│   └── covariance.parquet
└── output/        # GOLD - Résultats métier
    ├── weights.json
    ├── frontier.json
    └── backtest.json
```

### 1.2 Résumé du catalogue

| Zone | Datasets | Format | Volume total | Rétention |
|------|----------|--------|--------------|-----------|
| Bronze | 5 fichiers | Parquet | ~50 KB | 1 an |
| Silver | 5 fichiers | Parquet | ~20 KB | 1 an |
| Gold | 3 fichiers | JSON | ~5 KB | 30 jours |

---

## 2. Catalogue détaillé - Zone Bronze

### 2.1 Dataset: klines/{SYMBOL}.parquet

| Métadonnée | Valeur |
|------------|--------|
| **Identifiant** | `raw.klines.{symbol}` |
| **Localisation** | `data/raw/klines/{SYMBOL}.parquet` |
| **Format** | Apache Parquet |
| **Compression** | Snappy |
| **Source** | Binance API `/api/v3/klines` |
| **Fréquence alimentation** | Quotidienne (incrémental) |
| **Propriétaire** | Data Engineer |
| **Classification** | Public |

#### Schéma

| Colonne | Type | Nullable | Description |
|---------|------|----------|-------------|
| timestamp | STRING | Non | Date ISO 8601 (YYYY-MM-DD) |
| open | FLOAT64 | Non | Prix d'ouverture |
| high | FLOAT64 | Non | Prix le plus haut |
| low | FLOAT64 | Non | Prix le plus bas |
| close | FLOAT64 | Non | Prix de clôture |
| volume | FLOAT64 | Non | Volume échangé (quote asset) |

#### Fichiers actuels

| Fichier | Symbole | Description | Records (estimés) |
|---------|---------|-------------|-------------------|
| BTCUSDT.parquet | BTC/USDT | Bitcoin vs Tether | ~90 |
| ETHUSDT.parquet | ETH/USDT | Ethereum vs Tether | ~90 |
| BNBUSDT.parquet | BNB/USDT | Binance Coin vs Tether | ~90 |
| SOLUSDT.parquet | SOL/USDT | Solana vs Tether | ~90 |
| ADAUSDT.parquet | ADA/USDT | Cardano vs Tether | ~90 |

#### Métadonnées techniques

```yaml
dataset:
  id: raw.klines
  created_at: 2025-01-01
  updated_at: # Dernière exécution ingest
  schema_version: 1.0
  row_count: ~450 (5 symbols × 90 days)
  size_bytes: ~50000
  partitioning: by_symbol (1 file per symbol)
```

---

## 3. Catalogue détaillé - Zone Silver

### 3.1 Dataset: returns.parquet

| Métadonnée | Valeur |
|------------|--------|
| **Identifiant** | `processed.returns` |
| **Localisation** | `data/processed/returns.parquet` |
| **Source** | `raw.klines.*` |
| **Transformation** | `(close[t] - close[t-1]) / close[t-1]` |
| **Fréquence** | Post-ingest |

#### Schéma

| Colonne | Type | Description |
|---------|------|-------------|
| date | STRING | Date du rendement |
| symbol | STRING | Symbole |
| value | FLOAT64 | Rendement journalier |

---

### 3.2 Dataset: volatility.parquet

| Métadonnée | Valeur |
|------------|--------|
| **Identifiant** | `processed.volatility` |
| **Localisation** | `data/processed/volatility.parquet` |
| **Source** | `processed.returns` |
| **Transformation** | `std(returns) × sqrt(252)` |

#### Schéma

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Symbole |
| value | FLOAT64 | Volatilité annualisée |

---

### 3.3 Dataset: mean_returns.parquet

| Métadonnée | Valeur |
|------------|--------|
| **Identifiant** | `processed.mean_returns` |
| **Localisation** | `data/processed/mean_returns.parquet` |
| **Source** | `processed.returns` |
| **Transformation** | `mean(returns) × 252` |

#### Schéma

| Colonne | Type | Description |
|---------|------|-------------|
| symbol | STRING | Symbole |
| value | FLOAT64 | Rendement moyen annualisé |

---

### 3.4 Dataset: correlation.parquet

| Métadonnée | Valeur |
|------------|--------|
| **Identifiant** | `processed.correlation` |
| **Localisation** | `data/processed/correlation.parquet` |
| **Source** | `processed.returns` |
| **Transformation** | Matrice de corrélation (Pearson) |

#### Schéma

| Colonne | Type | Description |
|---------|------|-------------|
| symbol_row | STRING | Symbole ligne |
| symbol_col | STRING | Symbole colonne |
| value | FLOAT64 | Coefficient de corrélation [-1, 1] |

---

### 3.5 Dataset: covariance.parquet

| Métadonnée | Valeur |
|------------|--------|
| **Identifiant** | `processed.covariance` |
| **Localisation** | `data/processed/covariance.parquet` |
| **Source** | `processed.returns` |
| **Transformation** | Matrice de covariance annualisée |

#### Schéma

| Colonne | Type | Description |
|---------|------|-------------|
| symbol_row | STRING | Symbole ligne |
| symbol_col | STRING | Symbole colonne |
| value | FLOAT64 | Covariance annualisée |

---

## 4. Catalogue détaillé - Zone Gold

### 4.1 Dataset: weights.json

| Métadonnée | Valeur |
|------------|--------|
| **Identifiant** | `output.weights` |
| **Localisation** | `data/output/weights.json` |
| **Source** | `processed.covariance`, `processed.mean_returns` |
| **Transformation** | Optimisation Markowitz (max Sharpe) |
| **Consommateurs** | API REST, Reporting |

#### Schéma

```json
{
  "_metadata": {
    "saved_at": "2025-01-15T10:30:00"
  },
  "symbols": ["BTCUSDT", "ETHUSDT", ...],
  "weights": {
    "BTCUSDT": 0.35,
    "ETHUSDT": 0.25,
    ...
  },
  "expected_return": 0.15,
  "volatility": 0.28,
  "sharpe_ratio": 0.54
}
```

### 4.2 Dataset: frontier.json

| Métadonnée | Valeur |
|------------|--------|
| **Identifiant** | `output.frontier` |
| **Localisation** | `data/output/frontier.json` |
| **Source** | `processed.covariance`, `processed.mean_returns` |
| **Transformation** | Frontière efficiente (50 points, Markowitz) |
| **Consommateurs** | API REST (`/portfolio/frontier`), Dashboard (page Frontier) |

#### Schéma

```json
{
  "frontier": [
    {"volatility": 0.18, "return": 0.12, "weights": [0.6, 0.3, 0.1]}
  ],
  "max_sharpe": {"volatility": 0.28, "return": 0.18, "weights": [...]},
  "min_variance": {"volatility": 0.15, "return": 0.10, "weights": [...]},
  "assets": [{"symbol_index": 0, "volatility": 0.45, "return": 0.15}],
  "capital_market_line": {"x": [0.0, 0.5], "y": [0.05, 0.35]},
  "risk_free_rate": 0.05,
  "symbols": ["BTCUSDT", "ETHUSDT", ...]
}
```

---

### 4.3 Dataset: backtest.json

| Métadonnée | Valeur |
|------------|--------|
| **Identifiant** | `output.backtest` |
| **Localisation** | `data/output/backtest.json` |
| **Source** | `raw.klines.*` (validation walk-forward) |
| **Transformation** | Fenêtres glissantes : 60j train / 30j test |
| **Consommateurs** | API REST (`/portfolio/backtest`), Dashboard (page Backtest) |

#### Schéma

```json
{
  "windows": [
    {
      "window_id": 0,
      "train_start": "2025-01-01", "train_end": "2025-03-01",
      "test_start": "2025-03-02", "test_end": "2025-04-01",
      "weights": {"BTCUSDT": 0.4, "ETHUSDT": 0.35, "BNBUSDT": 0.25},
      "test_return": 0.0512
    }
  ],
  "cumulative_values": {
    "dates": [...],
    "strategy": [1.0, 1.005, ...],
    "equal_weight": [1.0, 1.004, ...],
    "btc_only": [1.0, 1.003, ...]
  },
  "metrics": {
    "strategy": {"cumulative_return": 0.25, "annualized_return": 0.35,
                  "max_drawdown": 0.12, "sharpe_ratio": 1.85, "calmar_ratio": 2.92},
    "equal_weight": {...},
    "btc_only": {...}
  },
  "symbols": [...],
  "config": {"train_window": 60, "test_window": 30, "strategy": "max_sharpe"}
}
```

---

## 5. Lignage des données (Data Lineage)

### 5.1 Graphe de dépendances

```
[Binance API]
      │
      ▼
┌─────────────────────────────────────────────────┐
│                    BRONZE                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ BTCUSDT  │ │ ETHUSDT  │ │ BNBUSDT  │ ...     │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘         │
└───────┼────────────┼────────────┼───────────────┘
        │            │            │
        └────────────┼────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│                    SILVER                        │
│  ┌──────────┐                                    │
│  │ returns  │──────────┬──────────┬─────────┐   │
│  └──────────┘          │          │         │   │
│        │               ▼          ▼         ▼   │
│        │        ┌──────────┐ ┌────────┐ ┌─────┐ │
│        └───────▶│volatility│ │ correl │ │ cov │ │
│                 └──────────┘ └────────┘ └──┬──┘ │
└────────────────────────────────────────────┼────┘
                                             │
                     ┌───────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│                     GOLD                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────┐ │
│  │ weights.json │ │frontier.json │ │backtest  │ │
│  └──────┬───────┘ └──────┬───────┘ └────┬─────┘ │
└─────────┼────────────────┼──────────────┼───────┘
                     │
                     ▼
               [FastAPI REST]
```

### 5.2 Matrice de lignage

| Dataset cible | Dépendances directes | ETL |
|---------------|---------------------|-----|
| raw.klines.* | Binance API | ingest.py |
| processed.returns | raw.klines.* | transform.py |
| processed.volatility | processed.returns | transform.py |
| processed.mean_returns | processed.returns | transform.py |
| processed.correlation | processed.returns | transform.py |
| processed.covariance | processed.returns | transform.py |
| output.weights | processed.covariance, processed.mean_returns | optimize.py |
| output.frontier | processed.covariance, processed.mean_returns | optimize.py |
| output.backtest | raw.klines.* | backtest.py |

---

## 6. Cycle de vie des données

### 6.1 Politique de rétention

| Zone | Rétention | Archivage | Suppression |
|------|-----------|-----------|-------------|
| Bronze | 365 jours | Non | Automatique (script) |
| Silver | 365 jours | Non | Automatique |
| Gold | 30 jours | Non | Écrasement |

### 6.2 Processus de suppression

```python
# Pseudo-code: data_lifecycle.py
def cleanup_old_data():
    """Suppression des données > rétention."""
    today = date.today()

    # Bronze: supprimer records > 1 an
    for file in glob("data/raw/klines/*.parquet"):
        df = read_parquet(file)
        df_filtered = df[df.timestamp > today - timedelta(days=365)]
        write_parquet(df_filtered, file)

    # Silver: idem
    # Gold: garder uniquement le dernier fichier
```

### 6.3 Conformité RGPD

| Critère | Statut | Justification |
|---------|--------|---------------|
| Données personnelles | N/A | Aucune donnée personnelle |
| Consentement | N/A | Données publiques Binance |
| Droit à l'oubli | N/A | Pas d'identification utilisateur |
| Minimisation | ✅ | Seules les données nécessaires |
| Limitation stockage | ✅ | Rétention 1 an max |

---

## 7. Qualité et monitoring

### 7.1 Règles de qualité

| Dataset | Règle | Seuil | Action si violation |
|---------|-------|-------|---------------------|
| raw.klines | Complétude | 100% | Alerte + retry |
| raw.klines | Fraîcheur | < 24h | Alerte |
| processed.* | Valeurs nulles | 0% | Erreur pipeline |
| output.weights | Somme weights | = 1.0 | Erreur pipeline |
| output.frontier | Somme weights | = 1.0 par point | Erreur pipeline |
| output.backtest | 3 stratégies | Présentes | Erreur pipeline |

### 7.2 Métriques de monitoring

| Métrique | Source | Fréquence | Seuil alerte |
|----------|--------|-----------|--------------|
| Nb records Bronze | Parquet metadata | Quotidien | < 400 |
| Taille totale data/ | Filesystem | Quotidien | > 100 MB |
| Dernière mise à jour | File mtime | Quotidien | > 48h |
| Erreurs ingest | Logs Airflow | Temps réel | > 0 |

### 7.3 Alertes

| Événement | Niveau | Canal | Action |
|-----------|--------|-------|--------|
| Échec ingest | CRITICAL | Log + (email) | Retry auto |
| Données manquantes | WARNING | Log | Investigation |
| Espace disque > 80% | WARNING | Log | Cleanup |

---

## 8. Accès et sécurité

### 8.1 Matrice des accès

| Rôle | Bronze | Silver | Gold | API |
|------|--------|--------|------|-----|
| Data Engineer | RW | RW | RW | RW |
| Analyste | R | R | R | R |
| Application | - | - | R | R |

### 8.2 Méthodes d'accès

| Méthode | Protocole | Authentification |
|---------|-----------|------------------|
| Fichiers Parquet | Filesystem | OS permissions |
| DuckDB SQL | In-process | N/A |
| API REST | HTTP/JSON | Aucune (MVP) |

---

## 9. Dictionnaire de données consolidé

| Terme technique | Terme métier | Définition |
|-----------------|--------------|------------|
| timestamp | Date | Date de la bougie (format YYYY-MM-DD) |
| open | Ouverture | Premier prix de la période |
| high | Plus haut | Prix maximum de la période |
| low | Plus bas | Prix minimum de la période |
| close | Clôture | Dernier prix de la période |
| volume | Volume | Quantité échangée |
| return | Rendement | Variation relative du close |
| volatility | Volatilité | Risque (écart-type annualisé) |
| correlation | Corrélation | Co-mouvement entre actifs |
| covariance | Covariance | Variance conjointe |
| weight | Poids | Allocation dans le portefeuille |
| sharpe_ratio | Ratio de Sharpe | Rendement/risque |

---

## 10. Conformité au référentiel C20

| Critère d'évaluation | Statut | Preuve |
|---------------------|--------|--------|
| Méthodes d'alimentation justifiées | ✅ | Section 2 (source Binance) |
| Scripts s'exécutent sans erreur | ✅ | Airflow DAG fonctionnel |
| Données importées correctement | ✅ | Section 2-4 (schémas validés) |
| Métadonnées dans le catalogue | ✅ | Ce document complet |
| Procédures de suppression conformes | ✅ | Section 6 (lifecycle) |
| Monitorage conditions | ✅ | Section 7 (métriques) |
| Alertes rupture service | ✅ | Section 7.3 (alertes) |
