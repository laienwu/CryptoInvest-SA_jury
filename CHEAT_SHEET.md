# Portfolio Optimization - Essentials for Jury

> Aide-memoire pour Q&A au jury.

---

## 1. ARCHITECTURE GLOBALE

```
┌─────────────────────────────────────────────────────────────┐
│                        DATA LAKE                            │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│   BRONZE    │   SILVER    │    GOLD     │     EXPOSE        │
│  data/raw/  │ data/proc/  │ data/output │    FastAPI:8000   │
│  (ingest)   │ (transform) │ (optimize)  │    Streamlit:8501 │
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

### Dashboard (`src/dashboard/`)

| Fichier | Role | Competences |
|---------|------|-------------|
| `app.py` | Streamlit dashboard (visualisation) | C12, Business |

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
GET /portfolio/frontier # Frontiere efficiente
GET /portfolio/backtest # Resultats backtest
```

**A retenir:**
- FastAPI genere auto la doc OpenAPI sur /docs
- Storage injecte au demarrage (parquet par defaut)
- Pas d'auth (MVP)

### dashboard/app.py

```python
# Structure du dashboard Streamlit
# 6 pages accessibles via sidebar:
# - Dashboard: KPIs + Pie chart + Risk contribution + Correlation
# - Symbols: Selection symbole + Price chart + Raw data
# - Metrics: Exploration des metriques calculees
# - Frontier: Frontiere efficiente + CML + poids
# - Backtest: Courbes cumulatives + metriques + drawdown
# - Risk: Vol roulante, beta, skew/kurtosis, VaR/CVaR, reseau

# Composants principaux:
def render_kpi_cards(portfolio)     # 3 metriques: Return, Vol, Sharpe
def render_allocation_chart(weights) # Pie chart allocation
def render_price_chart(symbol)       # Line chart OHLCV
def render_correlation_heatmap()     # Matrice correlation Plotly
def render_volatility_chart()        # Bar chart volatilites
```

**A retenir:**
- Connecte a l'API via `API_URL=http://api:8000`
- Port 8501 (Streamlit standard)
- Plotly pour les graphiques interactifs
- Pandas dans le dashboard uniquement (pipeline = PyArrow, ADR-003)

---

## 4. PATTERNS DE CODE A EXPLIQUER

### Pattern 1: Storage Pluggable

```python
# Dans src/storage/__init__.py
_mutable_registry = {"parquet": ParquetStorage, "duckdb": DuckDBStorage}
_STORAGE_REGISTRY = MappingProxyType(_mutable_registry)  # read-only

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

## 6. COMMANDES DEMO (COPIER-COLLER)

### 6.1 Setup Initial

```bash
# Installer les dependances
uv sync

# Installer avec extras test
uv sync --extra test

# Verifier l'installation
uv run python -c "from src.pipeline import ingest_data; print('OK')"
```

### 6.2 Lancer les Tests (montrer en premier)

```bash
# Tests rapides
uv run pytest tests/ -v

# Tests avec coverage
uv run pytest tests/ --cov=src --cov-report=term-missing

# Test un fichier specifique
uv run pytest tests/test_transform.py -v
```

**Resultat attendu:** 254 tests passed

### 6.3 Docker - Demarrage Rapide

```bash
# RECOMMANDE: API + Dashboard ensemble
docker compose up api streamlit

# Verifier que ca tourne
docker compose ps

# Arreter tout
docker compose down
```

**URLs:**
- API: http://localhost:8000/docs
- Dashboard: http://localhost:8501

### 6.4 Docker - Services Individuels

```bash
# API seule
docker compose up api

# Dashboard seul (necessite API)
docker compose up api streamlit

# Pipeline (execution unique)
docker compose --profile pipeline up pipeline

# Airflow complet
docker compose --profile airflow up -d

# Stack complete (API + Benchmarks + Airflow)
docker compose --profile full up -d

# PostgreSQL benchmarks
docker compose --profile benchmarks up -d postgres-benchmarks
```

### 6.5 Pipeline Python (etape par etape)

```bash
# ETAPE 1: Ingestion (C8)
uv run python -c "
from src.pipeline import ingest_data
from src.storage import get_storage
storage = get_storage()
data = ingest_data()
storage.save_raw(data)
print('Symbols:', list(data.keys()))
"

# ETAPE 2: Transformation (C10)
uv run python -c "
from src.pipeline import transform_data
results = transform_data()
print('Volatility:', results['volatility'])
"

# ETAPE 3: Optimisation
uv run python -c "
from src.pipeline import optimize_portfolio
result = optimize_portfolio()
print('Weights:', result['weights'])
print('Sharpe:', result['sharpe_ratio'])
"

# TOUT EN UNE COMMANDE
uv run python -c "
from src.pipeline import ingest_data, transform_data, optimize_portfolio
from src.storage import get_storage
storage = get_storage()
data = ingest_data()
storage.save_raw(data)
transform_data()
result = optimize_portfolio()
print('Done! Sharpe:', result['sharpe_ratio'])
"
```

### 6.6 API - Tests avec curl

```bash
# Health check
curl http://localhost:8000/

# Liste des symboles
curl http://localhost:8000/symbols

# Donnees d'un symbole
curl http://localhost:8000/klines/BTCUSDT

# Liste des metriques
curl http://localhost:8000/metrics

# Volatilite
curl http://localhost:8000/metrics/volatility

# Correlation
curl http://localhost:8000/metrics/correlation

# Portfolio complet
curl http://localhost:8000/portfolio

# Resume portfolio (KPIs)
curl http://localhost:8000/portfolio/summary

# Frontiere efficiente
curl http://localhost:8000/portfolio/frontier

# Backtest
curl http://localhost:8000/portfolio/backtest
```

### 6.7 Multi-Sources (C8 - 5 sources)

```bash
# Ingestion multi-sources (sans API pour rapidite)
uv run python -c "
from src.pipeline import ingest_all_sources
data = ingest_all_sources(include_api=False)
print('Sources:', data['sources'])
print('Metadata count:', len(data.get('metadata', [])))
"

# CSV metadata
uv run python -c "
from src.pipeline import load_symbols_metadata_csv
metadata = load_symbols_metadata_csv()
for m in metadata[:3]:
    print(f\"{m['symbol']}: {m['sector']}\")
"

# JSON config
uv run python -c "
from src.pipeline import load_portfolio_config_json
config = load_portfolio_config_json()
print(config)
"
```

### 6.8 DuckDB - Requetes SQL (C9, C13, C14)

```bash
uv run python -c "
from src.storage import get_storage
storage = get_storage('duckdb')

# Star schema - Table de faits
print('=== FACT_PRICES ===')
print(storage.query('SELECT * FROM fact_prices LIMIT 5'))

# Dimension symbole
print('=== DIM_SYMBOL ===')
print(storage.query('SELECT * FROM dim_symbol'))

# Dimension date
print('=== DIM_DATE ===')
print(storage.query('SELECT * FROM dim_date LIMIT 5'))

# Stats agregees
print('=== SUMMARY STATS ===')
print(storage.get_summary_stats())
"
```

### 6.9 Airflow (C15, C16)

```bash
# Premiere fois: init
docker compose --profile airflow run airflow-init

# Demarrer Airflow
docker compose --profile airflow up -d

# Verifier les services
docker compose --profile airflow ps

# Arreter Airflow
docker compose --profile airflow down
```

**UI:** http://localhost:8081
**Login:** admin / admin
**DAG:** portfolio_optimization

### 6.10 Verifications Rapides

```bash
# Verifier les fichiers data (PowerShell / Windows)
Get-ChildItem data/raw/klines/
Get-ChildItem data/processed/
Get-ChildItem data/output/

# Contenu du portfolio
Get-Content data/output/weights.json

# Taille des fichiers
Get-ChildItem data -Recurse | Select-Object FullName, Length

# Logs Docker
docker compose logs api
docker compose logs streamlit
```

### 6.11 Commandes de Secours

```bash
# Rebuild les images Docker
docker compose build --no-cache

# Supprimer les conteneurs
docker compose down -v

# Reset les donnees (PowerShell / Windows)
Remove-Item data/raw/klines/*.parquet -Force -ErrorAction SilentlyContinue
Remove-Item data/processed/*.parquet -Force -ErrorAction SilentlyContinue
Remove-Item data/output/*.json -Force -ErrorAction SilentlyContinue

# Reinstaller les deps
uv sync --reinstall
```

### 6.12 Mode Secours (sans Internet)

```bash
# 1) Montrer la collecte multi-sources sans appels reseau
uv run python -c "
from src.pipeline import ingest_all_sources
data = ingest_all_sources(include_api=False, include_scraping=False, include_postgres=False)
print('Sources chargees:', data['sources'])
"

# 2) Travailler sur les donnees locales deja presentes dans data/
uv run python -c "
from src.pipeline import transform_data, optimize_portfolio
transform_data()
result = optimize_portfolio()
print('Sharpe:', result['sharpe_ratio'])
"

# 3) API + Dashboard sur resultat local
docker compose up api streamlit
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
2. Ils sont plus stables pour la modelisation statistique et coherents avec la capitalisation continue
C'est le standard en finance quantitative."

### Q7: "Comment tu geres les erreurs API Binance?"

**Reponse:** "J'ai implemente:
1. Retry avec backoff exponentiel (3 tentatives, delai x2)
2. Gestion du rate limit (code 429 → attendre Retry-After)
3. Timeout de 30 secondes
4. Exceptions custom avec contexte (status_code)"

### Q8: "Qu'est-ce que le star schema?"

**Reponse:** "C'est un modele dimensionnel avec une table de faits centrale (fact_prices avec les mesures OHLCV) et des tables de dimensions (dim_symbol, dim_date). Ca permet des requetes analytiques efficaces avec des JOIN simples."

### Q9: "Pourquoi un dashboard Streamlit?"

**Reponse:** "Streamlit permet de creer rapidement un dashboard Python sans frontend complexe. Il se connecte a notre API REST existante et affiche les donnees de maniere interactive. C'est le standard pour les data scientists - plus rapide que React/Vue pour un MVP."

### Q10: "Comment sont testes les composants?"

**Reponse:** "J'utilise pytest avec 254 tests unitaires couvrant:
- Les calculs financiers (returns, volatility, correlation)
- L'optimisation de portefeuille (Markowitz)
- Le storage layer (parquet, factory)
- Les endpoints API (avec mock DI)
- L'ingestion multi-sources
- La frontière efficiente
- Le backtesting walk-forward
- La détection de drift OpenAPI spec

Coverage global: 53%. Les modules critiques (transform, optimize, API, config) ont 60-100% de couverture."

---

## 8. METRIQUES A CONNAITRE

### Donnees actuelles

```
Symboles: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT,
          LINKUSDT, DOTUSDT, AVAXUSDT, MATICUSDT, ATOMUSDT,
          XRPUSDT, DOGEUSDT, FILUSDT  (13 actifs)
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

- [ ] Tests passent: `uv run pytest tests/ -v` (254 tests)
- [ ] Docker fonctionne: `docker compose up api streamlit`
- [ ] API accessible: http://localhost:8000/docs
- [ ] Dashboard accessible: http://localhost:8501
- [ ] Donnees presentes dans data/
- [ ] Pipeline execute sans erreur
- [ ] DuckDB queries fonctionnent
- [ ] Connaitre les 9 endpoints API
- [ ] Dashboard affiche KPIs, Pie chart, Correlation
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

## 12. LIMITES ACTUELLES ET NEXT STEPS

### Limites actuelles (a assumer clairement au jury)

- API sans authentification (mode MVP interne)
- Credentials Docker de demonstration (a externaliser en `.env`/secrets)
- Couverture de tests plus faible sur certains modules d'ingestion reseau
- Optimiseur en mode long-only avec contraintes de base (somme=1, poids >= 0)

### Prochaines evolutions credibles

- Ajouter auth API key + rate limiting
- Externaliser secrets et durcir la configuration securite
- Ajouter tests d'integration end-to-end (API + storage + dashboard)
- Etendre l'optimisation avec contraintes metier (max poids, contraintes sectorielles)

---

## 13. DASHBOARD EMBED — OPTIONS POUR LA SOUTENANCE

### Option A: Navigateur local (recommande — risque zero)

Ouvrir http://localhost:8501 pendant la presentation. Interactif, pas de setup.

### Option B: ngrok — URL publique temporaire

Permet au jury d'acceder au dashboard depuis leur machine pendant la demo.

```bash
# Installer une fois
winget install ngrok

# Exposer le dashboard
ngrok http 8501
# → donne: https://xxxx.ngrok-free.app
```

Tier gratuit suffisant pour une soutenance de 30 min.

### Option C: Streamlit Community Cloud — URL permanente

Deployer sur https://share.streamlit.io avec le repo GitHub.
Donne une URL `https://yourapp.streamlit.app` a mettre dans le rapport et les slides.

**Caveat:** le dashboard appelle `http://api:8000` (reseau Docker interne).
Pour un deploy cloud, il faudrait pointer `API_URL` vers un endpoint public
ou mocker les donnees dans l'app.

### Option D: iframe dans un HTML

```html
<iframe src="http://localhost:8501"
        width="100%" height="800px" frameborder="0">
</iframe>
```

Fonctionne dans un fichier HTML ouvert localement pour le jury.

### Option E: Capture video / GIF

Enregistrer une demo avec OBS ou ShareX et l'integrer dans les slides PowerPoint/Canva.
Utile comme filet de secours si la demo live tombe.

---

### Recommandation pour la soutenance

| Contexte | Solution |
|----------|----------|
| Presentation live | Navigateur `localhost:8501` — zero risque |
| Rapport / slides | Screenshots de chaque page avec legende |
| Jury veut explorer apres | ngrok pendant la seance |
| URL permanente dans le rapport | Streamlit Community Cloud |
| Backup si demo plante | Video/GIF enregistre a l'avance |

---

**Bonne chance pour la soutenance!**
