# Portfolio Optimization - Essentials for Jury

> Aide-memoire pour Q&A au jury.

---

## 1. ARCHITECTURE GLOBALE

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA SOURCES (C8)                       │
│ [Binance API] [CSV] [JSON] [Scraping] [PostgreSQL] [yfinance] │
└──────────┬──────────────────────────────────────────────────┘
           │  Paginated ingestion (1000 records/page)
           ▼
┌─────────────────────────────────────────────────────────────┐
│                  STREAMING (optional)                        │
│   Binance WebSocket → Kafka (Redpanda)                      │
│   - Klines (candlesticks) → klines-raw topic                │
│   - Order Book depth (top 20 bids/asks) → orderbook-depth   │
│   → Consumer → Bronze Parquet                               │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAKE (C18-C21)                      │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│   │ BRONZE  │───▶│ SILVER  │───▶│  GOLD   │                │
│   │data/raw/│    │data/proc│    │data/out │                │
│   └─────────┘    └─────────┘    └─────────┘                │
│   Hive-partitioned: symbol=X/year=Y/month=M/data.parquet   │
│   Optional: Delta Lake (ACID, time travel via delta-rs)     │
├─────────────────────────────────────────────────────────────┤
│                 DATA WAREHOUSE (C13-C17)                    │
│   fact_prices │ dim_symbol │ dim_date — DuckDB Star Schema  │
│   + dbt models (staging/marts) via dbt-duckdb               │
├─────────────────────────────────────────────────────────────┤
│                 COMPUTE (optional)                           │
│   PySpark local mode: rolling correlation, vol surface      │
├─────────────────────────────────────────────────────────────┤
│                    EXPOSURE (C12)                           │
│   FastAPI :8000 (46 endpoints) │ Streamlit :8501 (32 pages)│
│   Redis cache │ Prometheus + Grafana │ Airflow :8081        │
└─────────────────────────────────────────────────────────────┘
```

**Phrase cle:** "Architecture medallion (Bronze/Silver/Gold) avec Hive-partitioned Parquet, Delta Lake optionnel, dbt transforms, PySpark analytics, et 6 optimiseurs de portefeuille."

---

## 2. FICHIERS CLES ET LEUR ROLE

### Pipeline (`src/pipeline/`) — 30+ modules

| Fichier | Role | Competences |
|---------|------|-------------|
| `ingest.py` | Extraction API Binance (paginee, 1000/page) | C8 |
| `ingest_sources.py` | Orchestration 6 sources (DataSource ABC) | C8, C10 |
| `ingest_yfinance.py` | Actifs traditionnels (stocks, ETFs, commodites) | C8 |
| `ingest_scraping.py` | Web scraping CoinGecko | C8 |
| `ingest_postgres.py` | Benchmarks PostgreSQL | C8, C9 |
| `transform.py` | Returns, volatilite, correlation, covariance | C10 |
| `optimize.py` | Markowitz (6 strategies: max Sharpe, min var, etc.) | Business |
| `backtest.py` | Walk-forward backtesting engine | Business |
| `monte_carlo.py` | Simulation VaR/CVaR (10k simulations) | Business |
| `strategy_compare.py` | Comparaison 6 optimiseurs cote a cote | Business |
| `black_litterman.py` | Optimisation bayesienne avec vues | Business |
| `hrp.py` | Hierarchical Risk Parity (clustering) | Business |
| `risk_parity.py` | Egalite de contribution au risque | Business |
| `constrained.py` | Optimisation avec contraintes min/max | Business |
| `signals.py` | Signaux trading (SMA, RSI, MACD, Bollinger) | Business |
| `regime.py` | Detection regime marche (bull/bear/sideways) | Business |
| `var_models.py` | VaR 3 methodes (historique, parametrique, CF) | Business |
| `spark_transforms.py` | PySpark: rolling corr, vol surface, volume | Massive |
| `data_metrics.py` | Metriques volume: records, taille, freshness | C20, C21 |
| `stream_producer.py` | WebSocket Binance → Kafka (klines + order book) | Streaming |
| `stream_consumer.py` | Kafka → Parquet (klines + order book) | Streaming |
| `validation.py` | Qualite donnees (bronze/silver/gold) | C21 |

### Storage (`src/storage/`)

| Fichier | Role | Competences |
|---------|------|-------------|
| `base.py` | Interface abstraite Storage (ABC) | Architecture |
| `parquet.py` | Data Lake Hive-partitioned | C11, C18 |
| `duckdb.py` | DWH Star Schema | C9, C13, C14 |
| `delta.py` | Delta Lake (ACID, time travel) | C18, C19 |
| `minio.py` | MinIO S3-compatible | C18 |

### API (`src/api/`)

| Fichier | Role | Competences |
|---------|------|-------------|
| `main.py` | 46 endpoints FastAPI REST | C12 |
| `schemas.py` | 50+ modeles Pydantic | C12 |
| `cache.py` | Redis cache avec TTL | Performance |
| `metrics.py` | Metriques Prometheus business | Monitoring |

### dbt (`dbt_project/`)

| Fichier | Role |
|---------|------|
| `models/staging/stg_klines.sql` | Staging: raw Parquet → types propres |
| `models/staging/stg_symbols.sql` | Staging: symboles uniques + metadata |
| `models/marts/fact_prices.sql` | Fait: OHLCV deduplique |
| `models/marts/dim_symbol.sql` | Dimension: symbole + classe actif |
| `models/marts/dim_date.sql` | Dimension: date spine |
| `models/marts/agg_daily_returns.sql` | Aggregat: log returns |
| `macros/log_returns.sql` | Macro reutilisable |

---

## 3. FONCTIONS IMPORTANTES A CONNAITRE

### ingest.py — Ingestion paginee

```python
def fetch_klines(symbol, interval, start_ms, end_ms, page_size=1000) -> list[dict]:
    """Pagination: boucle startTime/closeTime, 1000 records/page."""
    # Supporte 1d (daily) et 1m (intraday, ISO 8601)

def _timestamp_format(interval: str) -> str:
    """'1d' → '%Y-%m-%d', '1m' → '%Y-%m-%dT%H:%M:%S'"""

def ingest_incremental() -> dict[str, list[dict]]:
    """Incremental: ne charge que les donnees apres le dernier timestamp."""
```

**A retenir:**
- 51 crypto + 33 actifs trad (84 symboles total)
- Interval par defaut: `1m` (chandelles 1 minute)
- Periode: 30 jours
- Rate limit: 1200 req/min, 0.5s delay entre pages
- Retry: 3 tentatives avec backoff exponentiel

### optimize.py — 6 strategies

```python
# Strategies disponibles:
_scipy_max_sharpe()        # Markowitz unconstrained (short selling autorise)
_scipy_max_sharpe_long_only()  # Long only
_scipy_min_variance()      # Minimum variance
_analytical_min_variance() # Min variance analytique (inv(Cov))
_analytical_max_sharpe()   # Tangent portfolio analytique
_grid_search_max_sharpe()  # Fallback si scipy indisponible

# Portfolio par defaut = unconstrained (short selling autorise)
optimize_portfolio() → optimal_weights via _scipy_max_sharpe()
```

**A retenir:**
- Unconstrained: short selling autorise (poids negatifs possibles)
- Le dashboard filtre les graphiques pour ne montrer que les actifs investis (|w| > 0.1%)

### parquet.py — Hive partitioning

```python
def save_raw(data, metadata):
    """Ecrit en layout Hive: symbol=X/year=Y/month=M/data.parquet"""

def _load_symbol_table(symbol):
    """Lit toutes les partitions via rglob('*.parquet') + concat_tables()
    Fallback: legacy flat file si pas de partitions."""
```

---

## 4. PATTERNS DE CODE A EXPLIQUER

### Pattern 1: Storage Pluggable (Factory + Registry)

```python
_mutable_registry = {
    "parquet": ParquetStorage,
    "duckdb": DuckDBStorage,
    "minio": MinIOStorage,    # optional
    "delta": DeltaStorage,    # optional
}

def get_storage(name="parquet") -> Storage:
    return _STORAGE_REGISTRY[name]()
```

**Explication jury:** "Factory pattern avec registry. 4 backends (Parquet, DuckDB, MinIO, Delta Lake). Open/Closed de SOLID: ajouter un backend = une classe, zero modification du pipeline."

### Pattern 2: Config centralisee (Frozen Dataclass)

```python
@dataclass(frozen=True)
class PipelineConfig:
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", ...)  # 51 symboles
    interval: str = "1m"
    period_days: int = 30
    storage_backend: str = "parquet"
    # Layering: TOML → env vars → defaults
```

**Explication jury:** "Frozen dataclass = immuable apres creation. Config layering: fichier TOML en priorite, puis variables d'env, puis defaults. Centralise dans un seul module."

### Pattern 3: Depends() Injection (FastAPI)

```python
def get_storage_dep() -> Storage:
    return get_storage(load_config().storage_backend)

@app.get("/portfolio")
def get_portfolio(storage: Storage = Depends(get_storage_dep)):
    ...  # storage injecte automatiquement
```

**Explication jury:** "Dependency injection native FastAPI. Le storage est injecte a chaque requete. En test, on override la dependance avec un mock."

### Pattern 4: Delta Lake (ACID sans JVM)

```python
# delta-rs: implementation Rust, pas besoin de Java/Spark
import deltalake
deltalake.write_deltalake(path, table, mode="overwrite", partition_by=["symbol"])
dt = deltalake.DeltaTable(path)  # Time travel: dt.load_as_version(0)
```

**Explication jury:** "Delta Lake ajoute des transactions ACID sur Parquet. Le _delta_log/ garde l'historique des modifications. Time travel possible. J'utilise delta-rs (Rust) — pas besoin de JVM."

---

## 5. FLUX DE DONNEES COMPLET

```
1. INGEST (6 sources, paginee)
   Binance API ──GET /klines──▶ JSON (1000 records/page)
                                 │
                                 ▼ parse + pagination loop
                    dict[symbol, list[OHLCV]]
                                 │
                                 ▼ save_raw() — Hive partitioned
                    data/raw/klines/symbol=X/year=Y/month=M/data.parquet

2. TRANSFORM (PyArrow, pas pandas)
   load_raw() ◀── rglob("*.parquet") + concat_tables()
        │
        ▼ align_data_by_date()
   prices_matrix[n_symbols][n_dates]
        │
        ▼ calculate_log_returns()
   returns[n_symbols][n_dates-1]
        │
        ├──▶ volatility  ──▶ data/processed/volatility.parquet
        ├──▶ mean_returns ──▶ data/processed/mean_returns.parquet
        ├──▶ correlation  ──▶ data/processed/correlation.parquet
        └──▶ covariance   ──▶ data/processed/covariance.parquet

3. OPTIMIZE (6 strategies)
   covariance + mean_returns → scipy.optimize.minimize
        │
        ▼ max Sharpe (unconstrained)
   optimal_weights ──▶ data/output/weights.json

4. ADDITIONAL ANALYTICS
   ├── frontier     ──▶ efficient frontier curve
   ├── backtest     ──▶ walk-forward equity curves
   ├── monte_carlo  ──▶ 10k simulations VaR/CVaR
   ├── risk_parity  ──▶ equal risk contribution
   ├── hrp          ──▶ hierarchical clustering
   ├── bl           ──▶ Black-Litterman posterior
   └── strategy_compare ──▶ all 6 strategies side-by-side

5. dbt TRANSFORMS (SQL layer)
   stg_klines → fact_prices + dim_symbol + dim_date → agg_daily_returns

6. EXPOSE
   FastAPI (46 endpoints) + Streamlit (32 pages) + Airflow DAG
```

---

## 6. DASHBOARD — 32 PAGES EN 6 SECTIONS

| Section | Pages |
|---------|-------|
| **Overview** | Dashboard, Symbols, Metrics, Live Ticker |
| **Optimization** | Frontier, Constrained, Black-Litterman, HRP, Max Diversification, Min Variance, Strategy Showdown |
| **Risk** | Risk Analysis, VaR, Tail Risk, Factors, Shrinkage, Alpha/Beta, Sortino, Stress Test |
| **Backtest** | Backtest, Monte Carlo, Multi Backtest |
| **Trading** | Signals, Regime, Pairs, Position Sizing, Costs |
| **Portfolio** | Comparison, Correlation, Drawdown, Attribution, Decay |

**Navigation:** Sidebar avec 6 sections expandables (session_state routing).
**Data range filter:** Selectbox Streamlit (1D, 3D, 5D, 1W, MTD, 1M, 3M, 6M, YTD, 1Y, All) — filtre au niveau data, pas Plotly rangeselector.

---

## 7. API — 46 ENDPOINTS

### Health & Data

```
GET /                          # Health check
GET /symbols                   # Liste symboles
GET /klines/{symbol}           # Donnees OHLCV d'un symbole
GET /metrics                   # Liste metriques
GET /metrics/{name}            # Une metrique
GET /data/metrics              # Volume: records, taille, partitions, freshness
GET /prices/live               # Prix temps reel (Binance + yfinance)
```

### Portfolio Crypto

```
GET /portfolio                 # Poids optimaux (unconstrained)
GET /portfolio/summary         # Resume KPIs
GET /portfolio/frontier        # Frontiere efficiente
GET /portfolio/backtest        # Walk-forward backtest
GET /portfolio/monte-carlo     # Simulation 10k
GET /portfolio/backtest/multi  # Multi-strategy equity curves
```

### Portfolio Traditionnel

```
GET /portfolio/trad            # Poids trad (yfinance)
GET /portfolio/trad/frontier   # Frontiere trad
GET /portfolio/trad/backtest   # Backtest trad
GET /portfolio/combined        # Crypto + Trad combine
```

### Optimisation avancee

```
POST /portfolio/constrained    # Contraintes min/max weights
GET /portfolio/black-litterman # Bayesian + vues
GET /portfolio/hrp             # Hierarchical Risk Parity
GET /portfolio/risk-parity     # Egalite risque
GET /portfolio/max-diversification
GET /portfolio/min-variance
GET /portfolio/compare-strategies  # 6 strategies cote a cote
```

### Risque

```
GET /portfolio/risk-contribution    # MCTR par actif
GET /portfolio/rolling-correlation  # Correlation roulante
GET /portfolio/var                  # VaR 3 methodes
GET /portfolio/shrinkage           # Ledoit-Wolf
GET /portfolio/tail-risk           # Skew, kurtosis, Omega
GET /portfolio/factors             # Multi-factor exposure
GET /portfolio/alpha-beta          # CAPM
GET /portfolio/sortino             # Downside risk
GET /portfolio/drawdown            # Drawdown analysis
GET /portfolio/decay               # Weight drift
GET /portfolio/attribution         # Performance decomposition
GET /portfolio/stress-test         # 5 scenarios + custom
GET /portfolio/scenarios           # Liste scenarios
```

### Trading

```
GET /portfolio/signals         # SMA, RSI, MACD, Bollinger
GET /portfolio/regime          # Bull/bear/sideways
GET /portfolio/pairs           # Cointegration Engle-Granger
GET /portfolio/position-sizing # Kelly, vol-target, fixed-frac
GET /portfolio/cost-analysis   # Fees, slippage, net returns
GET /portfolio/rebalance       # Alertes rebalancement
```

### Autres

```
GET /portfolio/report          # PDF export
POST /portfolio/custom         # Evaluation portefeuille custom
GET /prom/metrics              # Prometheus metrics
```

---

## 8. COMMANDES DEMO (COPIER-COLLER)

### 8.1 Setup Initial

```bash
uv sync --extra test
uv run python -c "from src.pipeline import ingest_data; print('OK')"
```

### 8.2 Tests

```bash
# Tests complets (1201 tests)
uv run pytest tests/ -v

# Tests avec coverage
uv run pytest tests/ --cov=src --cov-report=term-missing

# Test un module specifique
uv run pytest tests/test_optimize.py -v
```

**Resultat attendu:** 1201 passed, 2 skipped

### 8.3 Docker

```bash
# API + Dashboard
docker compose up api streamlit

# Stack complete (API + Benchmarks + Airflow)
docker compose --profile full up -d

# Streaming (Kafka/Redpanda)
docker compose --profile streaming up -d

# Monitoring (Prometheus + Grafana)
docker compose --profile monitoring up -d
```

**URLs:**
- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501
- Airflow: http://localhost:8081 (admin/admin)
- Redpanda Console: http://localhost:8080
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

### 8.4 Pipeline etape par etape

```bash
# 1. Ingestion (paginee, 51 crypto + 33 trad)
uv run python -c "
from src.pipeline import ingest_data
from src.storage import get_storage
storage = get_storage()
data = ingest_data()
storage.save_raw(data)
print(f'{len(data)} symbols ingested')
"

# 2. Transformation
uv run python -c "
from src.pipeline import transform_data
results = transform_data()
print('Metrics:', list(results.keys()))
"

# 3. Optimisation
uv run python -c "
from src.pipeline import optimize_portfolio
result = optimize_portfolio()
print('Sharpe:', result['sharpe_ratio'])
print('Method:', result.get('method', 'scipy'))
"

# 4. Frontiere efficiente
uv run python -c "
from src.pipeline.optimize import compute_and_save_frontier
compute_and_save_frontier()
print('Frontier computed')
"

# 5. Backtest
uv run python -c "
from src.pipeline.backtest import run_backtest
result = run_backtest()
print('Sharpe:', result['metrics']['strategy']['sharpe_ratio'])
"

# 6. Multi-strategy backtest
uv run python -c "
from src.pipeline.backtest import run_multi_backtest
result = run_multi_backtest()
for r in result['ranking']:
    print(f\"#{r['rank']} {r['strategy']}: Sharpe={r['sharpe_ratio']:.3f}\")
"
```

### 8.5 DuckDB SQL (C9, C13, C14)

```bash
uv run python -c "
from src.storage import get_storage
storage = get_storage('duckdb')
print('=== FACT_PRICES (top 5) ===')
print(storage.query('SELECT * FROM fact_prices LIMIT 5'))
print('=== DIM_SYMBOL ===')
print(storage.query('SELECT * FROM dim_symbol'))
print('=== SUMMARY STATS ===')
print(storage.get_summary_stats())
"
```

### 8.6 Data volume metrics

```bash
curl http://localhost:8000/data/metrics | python -m json.tool
```

### 8.7 dbt (SQL transforms)

```bash
cd dbt_project
dbt run --profiles-dir .
dbt test --profiles-dir .
dbt docs generate --profiles-dir .
```

### 8.8 Mode Secours (sans Internet)

```bash
# 1) Multi-sources hors ligne
uv run python -c "
from src.pipeline import ingest_all_sources
data = ingest_all_sources(include_api=False, include_scraping=False, include_postgres=False)
print('Sources:', data['sources'])
"

# 2) Pipeline sur donnees locales
uv run python -c "
from src.pipeline import transform_data, optimize_portfolio
transform_data()
result = optimize_portfolio()
print('Sharpe:', result['sharpe_ratio'])
"

# 3) Dashboard local
docker compose up api streamlit
```

---

## 9. QUESTIONS JURY PROBABLES

### Q1: "Pourquoi DuckDB et pas PostgreSQL?"

**Reponse:** "DuckDB est un moteur OLAP embarque qui lit directement les fichiers Parquet — pas de serveur, pas de duplication. Pour notre volume, c'est ideal. En plus, j'utilise dbt-duckdb pour les transformations SQL avec tests et lineage integres."

### Q2: "Pourquoi pas pandas?"

**Reponse:** "ADR-003. pandas est lourd (~150MB) et copie les donnees en memoire. J'utilise PyArrow directement — meme format que Parquet, zero-copy possible, type-safe. Le seul endroit ou pandas est tolere c'est le dashboard Streamlit (affichage uniquement)."

### Q3: "Comment le systeme scale?"

**Reponse:** "Plusieurs axes:
1. **Partitioning Hive** — lecture selective par symbole/annee/mois, pas de scan complet
2. **Delta Lake** — ACID transactions pour ingestion concurrente
3. **PySpark** — rolling correlations distribuees en local mode, extensible a un cluster
4. **Kafka (Redpanda)** — decouplage producteur/consommateur pour le streaming
5. **Pagination** — ingestion par pages de 1000 records, pas de limites memoire
6. **dbt** — transforms SQL materialisees, incrementales possibles
Actuellement 51 crypto + 33 trad en chandelles 1 minute = ~2M records potentiels."

### Q4: "C'est quoi Delta Lake et pourquoi l'avoir ajoute?"

**Reponse:** "Delta Lake ajoute des transactions ACID sur Parquet — un _delta_log/ JSON enregistre chaque modification. Ca permet le time travel (revenir a une version), le schema enforcement, et des ecritures atomiques. J'utilise delta-rs (Rust), pas besoin de JVM."

### Q5: "C'est quoi l'optimisation Markowitz?"

**Reponse:** "Modern Portfolio Theory: trouver l'allocation qui maximise le rendement ajuste au risque. Je maximise le ratio de Sharpe = (E[R] - Rf) / sigma. J'ai 6 strategies: Markowitz unconstrained, long-only, min variance, risk parity, HRP (clustering), et Black-Litterman (bayesien)."

### Q6: "Pourquoi unconstrained (short selling)?"

**Reponse:** "Le short selling autorise des poids negatifs — ca permet au modele de parier contre des actifs correles negativement. C'est plus realiste pour un portefeuille professionnel et produit souvent un meilleur Sharpe. On peut comparer avec les 5 autres strategies."

### Q7: "Quid du RGPD?"

**Reponse:** "Donnees Binance = prix de marche agreges, publiques. Aucune donnee personnelle. J'ai quand meme documente les mesures preventives dans `docs/rapport/07_rgpd.md`."

### Q8: "Comment tu geres les erreurs?"

**Reponse:** "Exceptions custom par module avec contexte (operation, status_code). Rate limit 429 → attendre Retry-After. Retry backoff exponentiel (3 tentatives). Chaque erreur est loggee avec le contexte suffisant pour debugger."

### Q9: "Qu'est-ce que le star schema?"

**Reponse:** "Modele dimensionnel: table de faits (fact_prices avec OHLCV) + dimensions (dim_symbol, dim_date). Les dimensions sont reproduites en dbt SQL pour le lineage et les tests automatiques. SCD Type 1 (overwrite) documente."

### Q10: "Combien de tests et pourquoi?"

**Reponse:** "1201 tests unitaires dans 42 fichiers. Ca couvre: calculs financiers, 6 optimiseurs, 4 backends storage, 46 endpoints API (mock DI), backtesting, streaming, Delta Lake, dbt structure, OpenAPI drift detection. Les modules critiques (transform, optimize, API) sont a 80%+ de couverture."

### Q11: "C'est quoi dbt et pourquoi l'utiliser?"

**Reponse:** "dbt = data build tool. Ca permet d'ecrire les transforms du warehouse en SQL declaratif avec des tests integres (not_null, unique) et un lineage automatique. Les modeles staging lisent le Parquet brut, les marts produisent le star schema. C'est le standard industrie pour les data warehouses."

### Q12: "Pourquoi PySpark en local?"

**Reponse:** "PySpark en local demontre la capacite de traitement distribue. Les memes fonctions (rolling correlation, volatility surface) tourneraient sur un cluster Spark sans modification. En local, ca utilise tous les cores du CPU."

---

## 10. METRIQUES A CONNAITRE

### Donnees actuelles

```
Crypto:      51 symboles (BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ...)
Trad:        33 symboles (AAPL, MSFT, GOOGL, SPY, GLD, BTC-USD, ...)
Interval:    1m (chandelles 1 minute)
Periode:     30 jours
Partitions:  Hive-style (symbol=X/year=Y/month=M/)
Total:       84 actifs, ~2M records potentiels
```

### Formules cles

```
Log Return:     r_t = ln(P_t / P_{t-1})
Volatilite:     sigma = std(r) x sqrt(525,960)  [1m candles, 365.25 x 24 x 60]
Correlation:    rho = Cov(X,Y) / (sigma_X x sigma_Y)
Sharpe:         S = (E[R] - Rf) / sigma
Portfolio Var:  sigma²_p = w' x Cov x w
Sortino:        S = (E[R] - Rf) / downside_deviation
Calmar:         C = annual_return / max_drawdown
Omega:          sum(gains) / sum(losses)
```

---

## 11. STRUCTURE DES FICHIERS DE DONNEES

### Bronze: Hive-partitioned Parquet

```
data/raw/klines/
  symbol=BTCUSDT/
    year=2024/
      month=1/data.parquet
      month=2/data.parquet
  symbol=ETHUSDT/
    year=2024/
      month=1/data.parquet

Schema: timestamp (STRING), open, high, low, close, volume (FLOAT64)
```

### Silver: data/processed/

```
returns.parquet, volatility.parquet, correlation.parquet,
covariance.parquet, mean_returns.parquet
```

### Gold: data/output/

```json
{
  "symbols": ["BTCUSDT", "ETHUSDT", ...],
  "weights": {"BTCUSDT": 0.4, "ETHUSDT": -0.1, ...},
  "expected_return": 0.15,
  "volatility": 0.25,
  "sharpe_ratio": 1.2,
  "method": "scipy_unconstrained"
}
```

### Streaming: data/streaming/

```
data/streaming/orderbook/
  orderbook_20240101_120000.parquet
  (symbol, timestamp, spread, mid_price, bid_depth, ask_depth, best_bid, best_ask)
```

### Delta Lake (optional)

```
data/delta/raw/klines/
  _delta_log/        # Transaction log (JSON)
  symbol=BTCUSDT/    # Partitioned data
```

---

## 12. CHECKLIST AVANT SOUTENANCE

- [ ] Tests passent: `uv run pytest tests/ -v` (1201 tests)
- [ ] Docker fonctionne: `docker compose up api streamlit`
- [ ] API accessible: http://localhost:8000/docs
- [ ] Dashboard accessible: http://localhost:8501 (32 pages)
- [ ] Donnees presentes dans data/ (Hive-partitioned)
- [ ] Pipeline execute sans erreur
- [ ] DuckDB queries fonctionnent
- [ ] dbt models compilent: `cd dbt_project && dbt compile --profiles-dir .`
- [ ] Connaitre les 46 endpoints API
- [ ] Dashboard: 6 sections, navigation groupee, data range filter
- [ ] Savoir expliquer Markowitz + 5 autres strategies
- [ ] Savoir expliquer Hive partitioning + Delta Lake
- [ ] Savoir expliquer star schema + dbt
- [ ] Savoir expliquer PySpark et pourquoi local mode
- [ ] Connaitre les competences par module (tableau section 2)

---

## 13. VOCABULAIRE TECHNIQUE

| Terme | Definition rapide |
|-------|-------------------|
| **OHLCV** | Open, High, Low, Close, Volume |
| **Kline** | Chandelier japonais (candlestick) |
| **ETL / ELT** | Extract-Transform-Load / Extract-Load-Transform |
| **Data Lake** | Stockage brut, schema-on-read |
| **Data Warehouse** | Stockage structure, schema-on-write |
| **Star Schema** | Modele faits + dimensions |
| **Hive Partitioning** | Layout repertoire = colonnes (symbol=X/year=Y/) |
| **Delta Lake** | ACID + time travel sur Parquet (transaction log) |
| **dbt** | Data build tool — transforms SQL avec tests et lineage |
| **Parquet** | Format columnar compresse |
| **PyArrow** | Lib Python pour Parquet (C++ engine) |
| **PySpark** | API Python pour Apache Spark |
| **Kafka / Redpanda** | Message broker distribue (streaming) |
| **Sharpe Ratio** | Rendement ajuste au risque |
| **HRP** | Hierarchical Risk Parity |
| **Black-Litterman** | Optimisation bayesienne avec vues investisseur |
| **VaR / CVaR** | Value-at-Risk / Conditional VaR |
| **SCD** | Slowly Changing Dimension |
| **RGPD** | Reglement protection donnees |

---

## 14. DASHBOARD EMBED — OPTIONS POUR LA SOUTENANCE

| Contexte | Solution |
|----------|----------|
| Presentation live | Navigateur `localhost:8501` — zero risque |
| Rapport / slides | Screenshots de chaque page avec legende |
| Jury veut explorer apres | ngrok pendant la seance |
| Backup si demo plante | Video/GIF enregistre a l'avance |

---

**Bonne chance pour la soutenance!**
