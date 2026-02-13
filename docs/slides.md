# Soutenance — Portfolio Optimization Binance

> RNCP Niveau 7 — Expert en infrastructures de données massives
> Candidat : Laien Wu

---

## Slide 1 — Page de titre

**Optimisation de Portefeuille Crypto avec Binance**

- Projet de certification Data Engineer
- RNCP Niveau 7
- Laien Wu — 2025

---

## Slide 2 — Problématique métier

**Comment optimiser un portefeuille crypto en s'appuyant sur des données massives multi-sources ?**

- Marché crypto : volatilité élevée, données temps réel
- Besoin : pipeline automatisé de collecte → analyse → décision
- Approche : Markowitz (mean-variance optimization)
- 5 cryptomonnaies : BTC, ETH, BNB, SOL, ADA

---

## Slide 3 — Architecture globale

```
Sources (5 types) → Data Lake (Bronze/Silver/Gold) → Data Warehouse (DuckDB) → API + Dashboard
```

- Stack : Python, FastAPI, DuckDB, Airflow, Docker, Streamlit
- Pas de pandas dans le pipeline (PyArrow uniquement — ADR 003)
- Config centralisée (`config.toml` + env vars)

---

## Slide 4 — Stack technique

| Composant | Technologie | Justification (ADR) |
|-----------|-------------|---------------------|
| Stockage | Parquet | Colonnes, compressé, schéma typé |
| Entrepôt | DuckDB | OLAP intégré, sans serveur |
| Pipeline | PyArrow | Mémoire efficace, pas de pandas |
| API | FastAPI | OpenAPI auto, async, Pydantic |
| Orchestration | Airflow | Standard industriel |
| Dashboard | Streamlit | Prototypage rapide, Plotly |

---

## Slide 5 — Data Lake (C18-C21)

**3 zones de données**

| Zone | Contenu | Format |
|------|---------|--------|
| Bronze (`data/raw/`) | Klines brutes Binance | Parquet |
| Silver (`data/processed/`) | Returns, volatilité, corrélation | Parquet |
| Gold (`data/output/`) | Poids optimaux, frontier, backtest | JSON |

- Catalogue de données (C20) : `docs/rapport/09_catalogue_donnees.md`
- Gouvernance RGPD (C21) : données publiques, pas de PII

---

## Slide 6 — Collecte multi-sources (C8)

**5 types de sources — conformité C8**

| # | Source | Type | Données |
|---|--------|------|---------|
| 1 | Binance API | REST API | Prix OHLCV |
| 2 | CSV | Fichier structuré | Métadonnées symboles |
| 3 | JSON | Fichier semi-structuré | Config portefeuille |
| 4 | CoinGecko | Web scraping | Rankings marché |
| 5 | PostgreSQL | Base relationnelle | Benchmarks historiques |

- Pattern DataSource ABC avec 5 implémentations
- Fallback automatique (ex: PostgreSQL → simulation)

---

## Slide 7 — Agrégation multi-sources (C10)

**Enrichissement croisé des données**

- Prix API + métadonnées CSV → données enrichies (secteur, catégorie)
- Rankings scraping → données marché par symbole
- Benchmarks PostgreSQL → comparaison S&P 500

```python
sources = [CSVSource(), JSONSource(), BinanceAPISource(), ...]
for source in sources:
    result.update(source.fetch())
```

---

## Slide 8 — Requêtes SQL (C9)

**DuckDB — SQL analytique sur fichiers**

```sql
SELECT ds.symbol, AVG(fp.close) AS avg_close
FROM fact_prices fp
JOIN dim_symbol ds ON fp.symbol = ds.symbol
GROUP BY ds.symbol
```

- Star schema : `fact_prices`, `dim_symbol`, `dim_date`
- Requêtes OLAP sans serveur dédié

---

## Slide 9 — Data Warehouse (C13-C14)

**Modèle en étoile**

- Table de faits : `fact_prices` (timestamp, OHLCV, clés étrangères)
- Dimension symbole : `dim_symbol` (nom, secteur, catégorie)
- Dimension date : `dim_date` (année, mois, jour, jour de semaine)
- Modélisation MERISE : MCD/MLD/MPD (C11)

---

## Slide 10 — ETL & Orchestration (C15-C16)

**Airflow DAG : `portfolio_dag.py`**

```
ingest → transform → optimize → frontier → backtest
```

- Planification quotidienne
- Monitoring via Airflow UI (port 8081)
- Gestion des erreurs et retries

---

## Slide 11 — Dimensions (C17)

**SCD — Slowly Changing Dimensions**

| Type | Application | Exemple |
|------|-------------|---------|
| Type 1 | Écrasement | Mise à jour market_cap_rank |
| Type 2 | Historique | Changement de consensus (PoW → PoS) |

- Documentation : `docs/rapport/08_scd_dimensions.md`

---

## Slide 12 — API REST (C12)

**FastAPI avec injection de dépendances**

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET | Health check |
| `/symbols` | GET | Liste des symboles |
| `/klines/{symbol}` | GET | Données OHLCV |
| `/metrics` | GET | Métriques disponibles |
| `/metrics/{name}` | GET | Métrique spécifique |
| `/portfolio` | GET | Poids optimaux |
| `/portfolio/summary` | GET | Résumé KPI portefeuille |
| `/portfolio/frontier` | GET | Frontière efficiente |
| `/portfolio/backtest` | GET | Résultats backtest |

- Modèles Pydantic pour validation réponses
- Documentation OpenAPI auto-générée (`/docs`)

---

## Slide 13 — Dashboard Streamlit (C12)

**5 pages de visualisation**

- Dashboard : KPIs, allocation pie chart, heatmap corrélation
- Symbols : Graphiques de prix avec sélecteur
- Metrics : Exploration des métriques
- Frontier : Frontière efficiente interactive
- Backtest : Résultats walk-forward

---

## Slide 14 — Transformation (pipeline)

**Calculs financiers (PyArrow, pas de pandas)**

- Log-returns : `ln(P_t / P_{t-1})`
- Volatilité annualisée : `σ × √365`
- Matrice de corrélation
- Matrice de covariance

---

## Slide 15 — Optimisation Markowitz

**Maximiser le ratio de Sharpe**

```
Sharpe = (R_p - R_f) / σ_p
```

- Contraintes : poids ≥ 0, somme = 1
- scipy SLSQP si disponible, sinon grid search (fallback)
- Portefeuille minimum variance comme alternative

---

## Slide 16 — Frontière efficiente

**Courbe risque/rendement**

- N points calculés entre min et max return
- Capital Market Line (CML) tangente
- Points clés : min variance, max Sharpe
- Visualisation interactive dans le dashboard

---

## Slide 17 — Backtesting walk-forward

**Validation out-of-sample**

- Fenêtres glissantes : train (60j) → test (30j)
- Ré-optimisation à chaque fenêtre
- Métriques : rendement cumulé, max drawdown, Sharpe
- Comparaison stratégies : max_sharpe vs min_variance

---

## Slide 18 — Pilotage projet (C1-C7)

**Méthodologie Agile**

- Analyse du besoin (C1) : user stories
- Cartographie des données (C2) : sources identifiées
- Cadre technique (C3) : ADR documentés
- Veille technologique (C4) : benchmarks outils
- Planification (C5) : sprints de 2 semaines
- Communication (C6-C7) : RACI, comptes-rendus

---

## Slide 19 — RGPD (C21)

**Conformité données**

- Données publiques uniquement (prix marché, rankings)
- Pas de données personnelles (PII)
- Pas de cookies, pas d'authentification utilisateur
- Documentation : `docs/rapport/07_rgpd.md`

---

## Slide 20 — Qualité du code

**214 tests — 10 fichiers de tests**

| Module | Tests | Couverture |
|--------|-------|------------|
| Config | 18 | TOML, env vars, defaults |
| Transform | 34 | Calculs financiers |
| Optimize | 30 | Markowitz, validation |
| Storage | 24 | Parquet, DuckDB, factory |
| API | 22 | Endpoints (mock DI) |
| Ingest sources | 39 | CSV, JSON, DataSource ABC |
| Frontier | 16 | Frontière efficiente |
| Backtest | 25 | Walk-forward |
| OpenAPI drift | 6 | Spec vs code sync |

---

## Slide 21 — Architecture clean

**Refactoring en 3 phases**

- Phase 1 : Hygiène code (logging, exceptions typées)
- Phase 2 : Config centralisée, DataSource ABC, Depends() FastAPI, Pydantic
- Phase 3 : Migration config, couverture tests 214

---

## Slide 22 — Docker & déploiement

**docker-compose.yml — 8 services**

| Service | Port | Image |
|---------|------|-------|
| API | 8000 | Dockerfile |
| Streamlit | 8501 | Dockerfile.streamlit |
| Airflow webserver | 8081 | Dockerfile.airflow |
| Airflow scheduler | — | Dockerfile.airflow |
| Airflow init | — | Dockerfile.airflow |
| PostgreSQL (Airflow) | — | postgres:15 |
| PostgreSQL (benchmarks) | 5433 | postgres:15 |
| Pipeline | — | one-shot |

---

## Slide 23 — Demo live

**Plan de démonstration**

1. `docker compose --profile full up -d` — Infrastructure
2. Ingestion multi-sources (5 types)
3. Transformation → métriques
4. Optimisation → poids optimaux
5. Frontière efficiente
6. Backtest walk-forward
7. API (`/docs`) + Dashboard Streamlit
8. Airflow DAG
9. DuckDB queries SQL

---

## Slide 24 — Bilan

**Ce qui a bien fonctionné**

- Architecture modulaire (changement de backend sans impact)
- PyArrow sans pandas : performance et typage
- DuckDB : SQL analytique sans infrastructure
- 214 tests : confiance pour refactorer

---

## Slide 25 — Difficultés rencontrées

- Grid search vs scipy : fallback nécessaire pour portabilité
- Corrélation avec rendements constants → division par zéro
- Rate limiting Binance API → backoff exponentiel
- Docker multi-service : orchestration des dépendances

---

## Slide 26 — Perspectives

**Améliorations possibles**

- Données temps réel (WebSocket Binance)
- ML : prédiction de rendements (LSTM, Prophet)
- Plus d'actifs (top 50 crypto)
- CI/CD avec GitHub Actions
- Monitoring Prometheus + Grafana

---

## Slide 27 — Questions

**Merci pour votre attention**

Laien Wu — 2025
