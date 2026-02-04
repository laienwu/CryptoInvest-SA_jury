# Portfolio Optimization - Essentials for Jury

> Aide-memoire pour Q&A au jury.

---

## 1. ARCHITECTURE GLOBALE

```
┌─────────────────────────────────────────────────────────────┐
│                        DATA LAKE                            │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│   BRONZE    │   SILVER    │    GOLD     │     EXPOSE        │
│  data/raw/  │ data/proc/  │ data/output │    FastAPI        │
│  (ingest)   │ (transform) │ (optimize)  │    port 8000      │
├─────────────┴─────────────┴─────────────┴───────────────────┤
│                    ETL PIPELINE                             │
│  ingest.py → transform.py → optimize.py                     │
├─────────────────────────────────────────────────────────────┤
│                   STORAGE LAYER                             │
│  Parquet (Data Lake) │ DuckDB (Data Warehouse)              │
└─────────────────────────────────────────────────────────────┘
```

**Phrase cle:** "Architecture medallion (Bronze/Silver/Gold) avec storage pluggable et exposition REST."

---

## 2. FICHIERS CLES ET LEUR ROLE

### Pipeline (`src/pipeline/`)

| Fichier | Role | Competences |
|---------|------|-------------|
| `ingest.py` | Extraction API Binance → Parquet | C8 |
| `transform.py` | Calculs: returns, vol, corr, cov | C10 |
| `optimize.py` | Optimisation Markowitz (Sharpe max) | Business |

### Storage (`src/storage/`)

| Fichier | Role | Competences |
|---------|------|-------------|
| `base.py` | Interface abstraite Storage | Architecture |
| `parquet.py` | Implementation Data Lake | C11, C18 |
| `duckdb.py` | Implementation DWH + Star Schema | C9, C13, C14 |

### API (`src/api/`)

| Fichier | Role | Competences |
|---------|------|-------------|
| `main.py` | FastAPI endpoints REST | C12 |

### Orchestration (`dags/`)

| Fichier | Role | Competences |
|---------|------|-------------|
| `portfolio_dag.py` | DAG Airflow (scheduling) | C15, C16 |

---

## 3. FONCTIONS IMPORTANTES A CONNAITRE

### ingest.py

```python
# Fonction principale - point d'entree
def ingest_data(symbols, interval, period_days) -> dict[str, list[dict]]
    """Collecte les donnees OHLCV depuis Binance API."""

# Fonction de requete avec retry et rate limiting
def _make_request(url, params) -> list
    """Gere les erreurs, timeout, rate limit (429)."""

# Fetch pour un symbole
def fetch_klines(symbol, interval, start_time, end_time) -> list[dict]
    """Retourne: [{"timestamp": "2024-01-01", "open": 42000.0, ...}, ...]"""
```

**A retenir:**
- Rate limit: 1200 req/min, on utilise 0.5s delay
- Retry: 3 tentatives avec backoff exponentiel
- Format sortie: dict avec symbol comme cle

### transform.py

```python
# Fonction principale
def transform_data(symbols, save, storage_backend) -> dict
    """Calcule toutes les metriques et les sauvegarde."""

# Calculs financiers (SANS numpy/pandas, juste pyarrow)
def calculate_log_returns(prices) -> list[list[float]]
    """r_t = ln(P_t / P_{t-1}) - rendements logarithmiques"""

def calculate_volatility(returns) -> list[float]
    """vol = std(returns) * sqrt(365) - annualisation crypto"""

def calculate_correlation_matrix(returns) -> list[list[float]]
    """Matrice de correlation entre actifs"""

def calculate_covariance_matrix(returns) -> list[list[float]]
    """Matrice de covariance annualisee (pour Markowitz)"""
```

**A retenir:**
- Log returns (pas simple returns) car additifs et symetriques
- 365 jours pour annualisation (crypto = 24/7)
- Tout en pyarrow.compute, pas de pandas

### optimize.py

```python
# Fonction principale
def optimize_portfolio(storage_backend, risk_free_rate, save) -> dict
    """Trouve les poids optimaux (max Sharpe ratio)."""

# Metriques portefeuille
def calculate_portfolio_return(weights, mean_returns) -> float
    """E[R] = somme(w_i * r_i)"""

def calculate_portfolio_volatility(weights, cov_matrix) -> float
    """sigma = sqrt(w' * Cov * w)"""

def calculate_sharpe_ratio(weights, mean_returns, cov_matrix, rf) -> float
    """Sharpe = (E[R] - Rf) / sigma"""
```

**A retenir:**
- Utilise scipy.optimize.minimize si dispo, sinon grid search
- Contraintes: sum(weights)=1, weights>=0 (long only)
- Risk-free rate: 5% par defaut

### duckdb.py

```python
# Methode cle pour C9 (requetes SQL)
def query(self, sql: str) -> list[dict]
    """Execute SQL et retourne liste de dicts."""

# Star schema (C13)
# - fact_prices: symbol, timestamp, open, high, low, close, volume
# - dim_symbol: symbol_id, symbol
# - dim_date: date_id, date, year, month, day, day_of_week

# Requetes analytiques
def get_daily_returns(self) -> list[dict]
    """Calcule returns avec LAG() window function."""

def get_summary_stats(self) -> list[dict]
    """Agregats par symbole: AVG, MIN, MAX, COUNT."""
```

**A retenir:**
- DuckDB = SQL sur fichiers Parquet, pas de serveur
- Views creees dynamiquement a l'init
- Pattern: read_parquet('path') dans les requetes

### api/main.py

```python
# Endpoints disponibles
GET /              # Health check
GET /symbols       # Liste des symboles disponibles
GET /klines/{sym}  # Donnees brutes d'un symbole
GET /metrics       # Liste des metriques calculees
GET /metrics/{name}# Une metrique specifique
GET /portfolio     # Poids optimaux complets
GET /portfolio/summary  # Resume du portefeuille
```

**A retenir:**
- FastAPI genere auto la doc OpenAPI sur /docs
- Storage injecte au demarrage (parquet par defaut)
- Pas d'auth (MVP)

---

## 4. PATTERNS DE CODE A EXPLIQUER

### Pattern 1: Storage Pluggable

```python
# Dans src/storage/__init__.py
_STORAGE_REGISTRY = {
    "parquet": ParquetStorage,
    "duckdb": DuckDBStorage,
}

def get_storage(name="parquet") -> Storage:
    return _STORAGE_REGISTRY[name]()
```

**Explication jury:** "J'ai implemente un pattern Factory avec registry. Ca permet de changer de backend (Parquet, DuckDB, futur Postgres) sans modifier le code pipeline. C'est le principe Open/Closed de SOLID."

### Pattern 2: Interface Abstraite

```python
# Dans src/storage/base.py
class Storage(ABC):
    @abstractmethod
    def save_raw(self, data, metadata) -> str: ...
    @abstractmethod
    def load_raw(self, symbols) -> dict: ...
    # etc.
```

**Explication jury:** "L'interface abstraite definit le contrat. Toute implementation doit respecter ces methodes. Ca garantit l'interchangeabilite des backends."

### Pattern 3: Gestion d'erreurs

```python
# Exceptions custom par module
class BinanceAPIError(Exception):
    def __init__(self, message, status_code=None): ...

class TransformError(Exception):
    def __init__(self, message, operation=None): ...

class StorageError(Exception):
    def __init__(self, message, operation=None): ...
```

**Explication jury:** "Chaque module a ses propres exceptions avec contexte (operation, status_code). Ca facilite le debug et le logging."

---

## 5. FLUX DE DONNEES COMPLET

```
1. INGEST
   Binance API ──GET /klines──▶ JSON
                                 │
                                 ▼ parse
                    dict[symbol, list[OHLCV]]
                                 │
                                 ▼ save_raw()
                    data/raw/klines/{SYMBOL}.parquet

2. TRANSFORM
   load_raw() ◀── data/raw/klines/*.parquet
        │
        ▼ align_data_by_date()
   prices_matrix[n_symbols][n_dates]
        │
        ▼ calculate_log_returns()
   returns[n_symbols][n_dates-1]
        │
        ├──▶ calculate_volatility() ──▶ data/processed/volatility.parquet
        ├──▶ calculate_mean_returns() ──▶ data/processed/mean_returns.parquet
        ├──▶ calculate_correlation_matrix() ──▶ data/processed/correlation.parquet
        └──▶ calculate_covariance_matrix() ──▶ data/processed/covariance.parquet

3. OPTIMIZE
   load_processed("covariance") ◀── data/processed/covariance.parquet
   load_processed("mean_returns") ◀── data/processed/mean_returns.parquet
        │
        ▼ scipy.optimize.minimize (ou grid_search)
   optimal_weights[n_symbols]
        │
        ▼ save_output()
   data/output/weights.json

4. EXPOSE
   FastAPI ◀── load_*() ◀── data/*
        │
        ▼
   HTTP JSON responses
```

---

## 6. COMMANDES DEMO

### Lancer le pipeline complet

```bash
# Avec Docker
docker compose --profile pipeline run pipeline

# Sans Docker (local)
python -c "
from src.pipeline import ingest_data, transform_data, optimize_portfolio
from src.storage import get_storage

storage = get_storage()
data = ingest_data()
storage.save_raw(data)
transform_data()
optimize_portfolio()
"
```

### Lancer l'API

```bash
# Avec Docker
docker compose up api

# Sans Docker
uvicorn src.api.main:app --reload
# Puis ouvrir http://localhost:8000/docs
```

### Demo DuckDB (C9 - SQL)

```python
from src.storage import get_storage

storage = get_storage("duckdb")

# Requete sur le star schema
storage.query("SELECT * FROM fact_prices LIMIT 5")
storage.query("SELECT * FROM dim_symbol")
storage.query("SELECT * FROM dim_date LIMIT 5")

# Calcul returns en SQL
storage.get_daily_returns()

# Stats agregees
storage.get_summary_stats()
```

### Demo Airflow

```bash
# Lancer Airflow
docker compose --profile airflow up -d

# Init (premiere fois)
docker compose --profile airflow run airflow-init

# UI: http://localhost:8081 (admin/admin)
# DAG: portfolio_optimization
```

---

## 7. QUESTIONS JURY PROBABLES

### Q1: "Pourquoi DuckDB et pas PostgreSQL?"

**Reponse:** "DuckDB est un moteur SQL embarque qui lit directement les fichiers Parquet. Pas besoin de serveur, pas de duplication de donnees. Pour notre volume (quelques MB), c'est ideal. PostgreSQL aurait necessite un serveur permanent et une copie des donnees."

### Q2: "Pourquoi pas pandas?"

**Reponse:** "pandas est une dependance lourde (~150MB) avec beaucoup de fonctionnalites dont je n'ai pas besoin. pyarrow suffit pour lire/ecrire Parquet et faire des calculs via pyarrow.compute. C'est plus leger et plus performant pour du columnar."

### Q3: "Comment le systeme scale?"

**Reponse:** "L'architecture est pluggable. Pour scaler:
1. Storage: ajouter un backend PostgreSQL ou BigQuery
2. Compute: remplacer les calculs Python par Spark
3. Orchestration: Airflow est deja la pour le scheduling
Le code pipeline ne change pas grace a l'abstraction Storage."

### Q4: "Quid du RGPD?"

**Reponse:** "Les donnees Binance sont publiques (prix de marche agreges). Aucune donnee personnelle n'est traitee, donc le RGPD ne s'applique pas strictement. J'ai quand meme documente les mesures preventives si le projet evoluait vers des donnees utilisateurs."

### Q5: "C'est quoi l'optimisation Markowitz?"

**Reponse:** "Markowitz (Modern Portfolio Theory) cherche l'allocation qui maximise le rendement pour un niveau de risque donne. Je maximise le ratio de Sharpe = (rendement - taux sans risque) / volatilite. Les contraintes sont: poids positifs (pas de short) et somme = 100%."

### Q6: "Pourquoi des log returns?"

**Reponse:** "Les log returns ont deux avantages:
1. Ils sont additifs dans le temps (r_total = r1 + r2 + r3)
2. Ils sont symetriques (+10% puis -10% = 0, contrairement aux returns simples)
C'est le standard en finance quantitative."

### Q7: "Comment tu geres les erreurs API Binance?"

**Reponse:** "J'ai implemente:
1. Retry avec backoff exponentiel (3 tentatives, delai x2)
2. Gestion du rate limit (code 429 → attendre Retry-After)
3. Timeout de 30 secondes
4. Exceptions custom avec contexte (status_code)"

### Q8: "Qu'est-ce que le star schema?"

**Reponse:** "C'est un modele dimensionnel avec une table de faits centrale (fact_prices avec les mesures OHLCV) et des tables de dimensions (dim_symbol, dim_date). Ca permet des requetes analytiques efficaces avec des JOIN simples."

---

## 8. METRIQUES A CONNAITRE

### Donnees actuelles

```
Symboles: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT
Periode: 90 jours par defaut
Interval: 1d (journalier)
```

### Formules cles

Log Return:
$$
r_t = \ln\left(\frac{P_t}{P_{t-1}}\right)
$$

Volatilité:
$$
\sigma = std(r)\sqrt{365}
$$

Corrélation:
$$
\rho = \frac{Cov(X,Y)}{\sigma_X \sigma_Y}
$$

Sharpe:
$$
S = \frac{E[R] - R_f}{\sigma}
$$

Variance du portefeuille:
$$
\sigma_p^2 = w^T Cov\, w
$$

```
Log Return:     r_t = ln(P_t / P_{t-1})
Volatilite:     σ = std(r) × √365
Correlation:    ρ = Cov(X,Y) / (σ_X × σ_Y)
Sharpe:         S = (E[R] - Rf) / σ
Portfolio Var:  σ²_p = w' × Cov × w
```

### Resultats typiques (exemple)

```
BTCUSDT:  ~45% volatilite annualisee
ETHUSDT:  ~55% volatilite annualisee
Correlation BTC/ETH: ~0.8 (forte)
Sharpe optimal: ~0.5-1.0 (depend du marche)
```

---

## 9. STRUCTURE DES FICHIERS DE DONNEES

### Bronze: data/raw/klines/{SYMBOL}.parquet

```
Schema:
- timestamp: STRING (ISO 8601)
- open: FLOAT64
- high: FLOAT64
- low: FLOAT64
- close: FLOAT64
- volume: FLOAT64
```

### Silver: data/processed/*.parquet

**returns.parquet:**
```
- date: STRING
- symbol: STRING
- value: FLOAT64
```

**correlation.parquet / covariance.parquet:**
```
- symbol_row: STRING
- symbol_col: STRING
- value: FLOAT64
```

### Gold: data/output/weights.json

```json
{
  "symbols": ["BTCUSDT", "ETHUSDT", ...],
  "weights": {"BTCUSDT": 0.4, "ETHUSDT": 0.3, ...},
  "expected_return": 0.15,
  "volatility": 0.25,
  "sharpe_ratio": 0.6,
  "method": "scipy"
}
```

---

## 10. CHECKLIST AVANT SOUTENANCE

- [ ] Docker fonctionne: `docker compose up api`
- [ ] API accessible: http://localhost:8000/docs
- [ ] Donnees presentes dans data/
- [ ] Pipeline execute sans erreur
- [ ] DuckDB queries fonctionnent
- [ ] Connaitre les 5 endpoints API
- [ ] Savoir expliquer Markowitz en 1 phrase
- [ ] Savoir expliquer le star schema
- [ ] Connaitre les competences par fichier (tableau section 2)

---

## 11. VOCABULAIRE TECHNIQUE

| Terme | Definition rapide |
|-------|-------------------|
| **OHLCV** | Open, High, Low, Close, Volume |
| **Kline** | Chandelier japonais (candlestick) |
| **ETL** | Extract, Transform, Load |
| **Data Lake** | Stockage brut, schema-on-read |
| **Data Warehouse** | Stockage structure, schema-on-write |
| **Star Schema** | Modele faits + dimensions |
| **Parquet** | Format columnar compresse |
| **Sharpe Ratio** | Rendement ajuste au risque |
| **Covariance** | Mesure de co-mouvement |
| **SCD** | Slowly Changing Dimension |
| **RGPD** | Reglement protection donnees |

---

**Bonne chance pour la soutenance!**
