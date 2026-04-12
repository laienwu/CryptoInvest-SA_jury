# Guide de Démonstration — Soutenance

**Durée cible : 10 minutes dans le créneau de 30 minutes**
**Dernière mise à jour : 2026-04-10**

---

## Préparation (avant d'entrer en salle)

```bash
# Démarrer l'infrastructure complète (5 min avant le jury)
# Profile "full" = api + streamlit + airflow + postgres + redis + minio + prometheus + grafana
docker compose --profile full up -d

# Vérifier que tout tourne (11 services en mode full)
docker compose ps

# Pré-charger les données fraîches (crypto + traditionnel)
python scripts/bootstrap.py
```

**Endpoints à garder ouverts dans le navigateur :**
- `http://localhost:8000/docs` — Swagger UI (45 endpoints)
- `http://localhost:8501` — Dashboard Streamlit (32 pages)
- `http://localhost:8081` — Airflow (DAG `portfolio_optimization`)
- `http://localhost:3000` — Grafana (dashboards API)

---

## Étape 1 — Infrastructure Docker (30s)

**Commande :** `docker compose ps`

**Montrer :** Tableau des conteneurs — api, streamlit, airflow-webserver/scheduler, postgres, postgres-benchmarks, redis, minio, prometheus, grafana.

**Dire :** « L'infrastructure complète tourne via docker-compose avec un système de profils : `full`, `pipeline`, `streaming`, `monitoring`, etc. Onze services en mode `full`, tous reproductibles en une commande. Airflow est l'orchestrateur unique — le service `pipeline` est réservé au bootstrap initial. »

---

## Étape 2 — Ingestion multi-sources C8 (90s)

**Commande :**
```bash
python -c "from src.pipeline import ingest_all_sources; ingest_all_sources()"
```

**Montrer :** Les logs montrant les **6 sources hétérogènes** invoquées : `BinanceAPISource`, `CSVSource`, `JSONSource`, `ScrapingSource` (CoinGecko), `PostgreSQLSource` (benchmarks), `YFinanceSource` (33 actifs traditionnels).

**Dire :** « C8 en action : six sources hétérogènes intégrées via le pattern `DataSource` ABC. API REST Binance, CSV de métadonnées, JSON de configuration, scraping CoinGecko, PostgreSQL pour les benchmarks, yfinance pour les actions/ETF/commodités. L'orchestrateur invoque chaque source de manière uniforme via une interface abstraite — résilience gracieuse si une source est indisponible. »

---

## Étape 3 — Transformation C10 (30s)

**Commande :**
```bash
python -c "from src.pipeline import transform_data; transform_data()"
```

**Montrer :** Logs de calcul des rendements, volatilité annualisée, corrélation, covariance (sanitization NaN/Inf).

**Dire :** « C10 : règles d'agrégation multi-sources. À partir des OHLCV bruts, on calcule les log-rendements, volatilité annualisée, matrices de corrélation et covariance. Tout en **PyArrow pur** — zéro Pandas dans le pipeline (ADR-003) — pour la performance mémoire. »

---

## Étape 4 — DuckDB Star Schema + dbt C9/C11/C13 (75s)

**Commande :**
```python
from src.storage.duckdb import DuckDBStorage

with DuckDBStorage() as db:
    # Requête sur le schéma en étoile
    print(db.query("""
        SELECT s.symbol, s.sector,
               COUNT(*) AS nb_obs,
               AVG(f.close) AS prix_moyen,
               MAX(f.high) AS plus_haut
        FROM fact_prices f
        JOIN dim_symbol s USING (symbol_id)
        GROUP BY s.symbol, s.sector
        ORDER BY prix_moyen DESC
        LIMIT 10
    """))
```

**Puis :**
```bash
cd dbt_project && dbt run && dbt test
```

**Dire :** « C9, C11, C13 : DWH en étoile sur DuckDB — `fact_prices`, `dim_symbol`, `dim_date`. Six modèles dbt (staging + marts) avec tests automatiques et lineage — c'est l'ADR-007. DuckDB lit directement les Parquet sans serveur (ADR-002). »

---

## Étape 5 — 6 Stratégies d'Optimisation C10 (60s)

**Commande :**
```bash
curl -s http://localhost:8000/strategies/compare | python -m json.tool
```

**Montrer :** JSON comparant Markowitz, HRP (Hierarchical Risk Parity), Risk Parity, Black-Litterman, Min Variance, Max Diversification — rendement, volatilité, Sharpe pour chaque.

**Dire :** « Six stratégies d'optimisation de portefeuille exposées côte à côte. Markowitz mean-variance classique, mais aussi HRP basé sur le clustering hiérarchique, Risk Parity pour l'égalité des contributions au risque, Black-Litterman pour intégrer des vues subjectives, plus les variantes min-variance et max-diversification. Chaque stratégie est un module indépendant dans `src/pipeline/`. »

---

## Étape 6 — API REST C12 (60s)

**Commandes :**
```bash
curl -s http://localhost:8000/portfolio | python -m json.tool
curl -s http://localhost:8000/portfolio/trad | python -m json.tool
```

**Puis ouvrir :** `http://localhost:8000/docs`

**Dire :** « C12 : FastAPI avec **45 endpoints** documentés automatiquement en OpenAPI. Injection DI via `Depends()` — le storage est swappable entre production et tests. Modèles de réponse validés par Pydantic, cache Redis avec TTL, métriques Prometheus exposées sur `/metrics`. Un test anti-drift CI vérifie que le YAML de spec reste synchronisé au code. »

---

## Étape 7 — Dashboard Streamlit C12 (90s)

**Ouvrir :** `http://localhost:8501`

**Naviguer (toggle Crypto / Traditional / Combined dans la sidebar) :**
1. **Dashboard** — KPIs, allocation pie, risk contribution, correlation heatmap
2. **Frontier** — Frontière efficiente avec iso-Sharpe et point optimal
3. **Risk** — Vol roulante, VaR/CVaR, drawdown, tail risk (skew/kurt)
4. **Strategy Compare** — Les 6 stratégies en une seule vue
5. **Stress Test** — 5 scénarios (2008, COVID, Luna, FTX, flash crash)
6. **Signals** — SMA crossover, RSI, MACD, Bollinger

**Dire :** « Le dashboard expose **32 pages interactives** avec cache 5 min. Trois modes via toggle sidebar : Crypto pur, Traditionnel pur, ou Combiné. Plotly pour tous les graphiques — zoom, hover, export PNG. »

---

## Étape 8 — Airflow C15, C16 (60s)

**Ouvrir :** `http://localhost:8081`

**Montrer :** Le DAG `portfolio_optimization` avec ses **12 tâches** — deux branches parallèles (crypto + traditional), chacune `ingest → transform → optimize → frontier → backtest`, suivies de `monte_carlo` et `dbt_run` après convergence des deux branches. Run récent en vert.

**Dire :** « C15 et C16 : Airflow est l'orchestrateur unique. DAG horaire (`@hourly`) avec retry automatique, timeout 10 min, deux branches parallèles crypto/trad pour ingérer et optimiser indépendamment, puis Monte Carlo et dbt après convergence. Le service `pipeline` de docker-compose sert uniquement au bootstrap initial. »

---

## Étape 9 — Streaming Kafka (optionnel, 45s)

**Commande :**
```bash
docker compose --profile streaming up -d
docker compose logs -f stream-producer | head -20
```

**Montrer :** Logs du producer envoyant klines + order book depth vers Redpanda, consumer écrivant en micro-batch Parquet dans Bronze.

**Dire :** « Ingestion temps réel optionnelle : Binance WebSocket → Redpanda (Kafka-compatible, zéro JVM) → consumer micro-batch → Bronze Parquet. Architecture parallèle au batch, pas de duplication car profiles Docker séparés. »

---

## Étape 10 — Monitoring Prometheus/Grafana (45s)

**Ouvrir :** `http://localhost:3000` (Grafana, admin/admin)

**Montrer :** Le dashboard `api_dashboard.json` — rate de requêtes, latence P50/P95/P99, taux d'erreur, métriques métier custom (taille du portefeuille, Sharpe courant).

**Dire :** « Observabilité complète : Prometheus scrape `/metrics` de l'API toutes les 15s, Grafana affiche les dashboards provisionnés automatiquement. Alertes configurées dans `monitoring/alerts.yml` pour latence et taux d'erreur. »

---

## Étape 11 — Tests & Qualité (optionnel, 30s)

**Commande :**
```bash
uv run pytest tests/ -q 2>&1 | tail -5
uv run ruff check src/
uv run mypy src/
```

**Dire :** « **1201 tests** passants, zéro failure sur 37+ fichiers de test. `ruff` et `mypy --strict` avec zéro erreur sur `src/`. Test anti-drift OpenAPI qui diff la spec YAML et le code généré. CI GitHub Actions : ruff + mypy + pytest + coverage + bandit + pip-audit. »

---

## Timing

| Étape | Durée | Compétences |
|-------|-------|-------------|
| Infrastructure Docker | 0:30 | C18, C19 |
| Ingestion 6 sources | 1:30 | C8, C10 |
| Transformation PyArrow | 0:30 | C10 |
| DuckDB + dbt | 1:15 | C9, C11, C13, C14 |
| 6 stratégies d'optimisation | 1:00 | C10 |
| API REST (45 endpoints) | 1:00 | C12 |
| Dashboard (32 pages) | 1:30 | C12 |
| Airflow (12 tâches) | 1:00 | C15, C16 |
| Streaming Kafka (optionnel) | 0:45 | C8, C21 |
| Monitoring Grafana | 0:45 | C19 |
| Tests & qualité | 0:30 | Qualité |
| **Total (sans optionnels)** | **~9:00** | Buffer 1–2 min |
| **Total (avec optionnels)** | **~10:30** | Buffer serré |

---

## Fallback en cas de problème

| Problème | Fallback |
|----------|----------|
| Binance API rate-limited | Dire « la résilience est codée, passer à la source suivante » |
| Dashboard vide | `python scripts/bootstrap.py` puis rafraîchir |
| Airflow DAG rouge | Ouvrir logs de la tâche échouée, expliquer retry policy |
| yfinance ticker retourne NaN | Montrer `_sanitize_float()` dans `optimize.py` — safety net |
| Conteneur down | `docker compose --profile full up -d <service>` |
| Pipeline met trop longtemps | Couper la démo et passer à l'API/Dashboard déjà prêts |
