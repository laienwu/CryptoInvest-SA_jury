# Guide de Démonstration — Soutenance

**Durée cible : 10 minutes dans le créneau de 30 minutes**

---

## Préparation (avant d'entrer en salle)

```bash
# Démarrer toute l'infrastructure (5 min avant le jury)
docker compose --profile full up -d
docker compose up -d streamlit

# Vérifier que tout tourne
docker compose ps

# Pré-exécuter le pipeline pour avoir des données fraîches
python scripts/bootstrap.py
```

---

## Étape 1 — Infrastructure (30s)

**Commande :** `docker compose ps`

**Montrer :** Tableau des conteneurs avec ports et health status.

**Dire :** « L'infrastructure complète tourne dans 7 services Docker orchestrés par docker-compose. L'API FastAPI écoute sur le port 8000, le dashboard Streamlit sur 8501, et Airflow sur 8081. Toute la stack est reproductible en une seule commande. »

---

## Étape 2 — Ingestion multi-sources C8 (90s)

**Commande :**
```bash
python -c "from src.pipeline import ingest_all_sources; ingest_all_sources()"
```

**Montrer :** Les logs montrant les 5 sources invoquées : BinanceAPISource, CSVSource, JSONSource, ScrapingSource, PostgreSQLSource.

**Dire :** « Voici C8 en action : 5 sources hétérogènes intégrées via le pattern DataSource ABC. Chaque source est une implémentation distincte d'une interface abstraite. L'orchestrateur appelle chaque source de manière uniforme, indépendamment de son type. »

**Si une source échoue :** « Les sources externes peuvent être indisponibles en démo. Le système gère gracieusement ces erreurs et continue — c'est la résilience par conception. »

---

## Étape 3 — Transformation C10 (30s)

**Commande :**
```bash
python -c "from src.pipeline import transform_data; transform_data()"
```

**Montrer :** Logs de calcul des rendements, volatilité, corrélation, covariance.

**Dire :** « C10 : les règles d'agrégation multi-sources. À partir des OHLCV bruts, on calcule rendements, volatilité annualisée, matrices de corrélation et covariance. Tout en PyArrow pur — pas de Pandas — pour la performance mémoire. »

---

## Étape 4 — DuckDB SQL C9 (60s)

**Commande :**
```python
from src.storage.duckdb import DuckDBStorage

with DuckDBStorage() as db:
    print(db.query('SELECT * FROM fact_prices LIMIT 5'))
    print(db.query("""
        SELECT symbol,
               COUNT(*) as nb_jours,
               AVG(close) as prix_moyen,
               MAX(high) as plus_haut
        FROM fact_prices
        GROUP BY symbol
        ORDER BY prix_moyen DESC
    """))
```

**Dire :** « C9 : requêtes SQL d'extraction sur le DWH en étoile — fact_prices, dim_symbol, dim_date. DuckDB lit directement les Parquet sans serveur — c'est l'ADR-002. »

---

## Étape 5 — API REST C12 (60s)

**Commandes :**
```bash
curl -s http://localhost:8000/portfolio | python -m json.tool
```

**Puis ouvrir :** `http://localhost:8000/docs`

**Dire :** « C12 : FastAPI génère cette documentation OpenAPI automatiquement. Injection DI via Depends() — le storage est swappable entre production et tests. Tous les modèles de réponse sont validés par Pydantic. »

---

## Étape 6 — Dashboard Streamlit C12 (90s)

**Ouvrir :** `http://localhost:8501`

**Naviguer :**
1. **Dashboard** — KPIs, allocation pie, risk contribution, correlation heatmap
2. **Frontier** — Frontière efficiente avec iso-Sharpe et point optimal
3. **Risk** — Vol roulante, beta vs BTC, VaR/CVaR

**Dire :** « Le dashboard Streamlit expose 6 pages interactives avec cache 5 min. La frontière efficiente montre le meilleur compromis rendement/risque selon Markowitz. »

---

## Étape 7 — Airflow C15, C16 (45s)

**Ouvrir :** `http://localhost:8081`

**Montrer :** Le DAG `portfolio_optimization` avec ses 5 tâches, un run réussi (vert).

**Dire :** « C15 et C16 : Airflow est le seul orchestrateur. DAG quotidien avec retry automatique, timeout configurable, et SLA alerting. Le service pipeline dans docker-compose est uniquement le bootstrap initial. »

---

## Étape 8 — Tests (optionnel, 30s)

**Commande :**
```bash
uv run pytest tests/ -v --tb=no -q 2>&1 | tail -5
```

**Dire :** « 246 tests passants, zéro failure. ruff et mypy strict avec zéro erreur. Test anti-drift entre la spec OpenAPI YAML et le code. »

---

## Timing

| Étape | Durée | Compétences |
|-------|-------|-------------|
| Infrastructure | 0:30 | C18, C19 |
| Ingestion | 1:30 | C8, C10 |
| Transformation | 0:30 | C10 |
| DuckDB SQL | 1:00 | C9, C13, C14 |
| API REST | 1:00 | C12 |
| Dashboard | 1:30 | C12 |
| Airflow | 0:45 | C15, C16 |
| Tests | 0:30 | Qualité |
| **Total** | **~7:15** | Buffer 2–3 min |
