# Slides Soutenance — Portfolio Optimization
### RNCP Niveau 7 — Expert en Infrastructures de Données Massives
**Durée totale : 30 minutes de présentation + 10 minutes Q&A**

---

## SLIDE 1 — Titre

**Optimisation de Portefeuille Crypto avec Binance**
Projet de certification RNCP Niveau 7 — Bloc 1 à 4 (C1–C21)

- Candidat : Laien Wu
- Rôle : Data Engineer
- Stack : Python · PyArrow · DuckDB · FastAPI · Streamlit · Airflow · Docker
- Date : 2026

> *Notes présentateur : Se présenter brièvement. Annoncer le plan : contexte → architecture → démonstration → choix techniques → conformité → conclusion.*

---

## SLIDE 2 — Contexte & Besoin (C1)

**Problème métier : comment allouer un portefeuille crypto de manière optimale ?**

- Marché 24/7, haute volatilité, 13 actifs suivis (BTC, ETH, BNB, SOL…)
- Besoin : données fraîches, métriques fiables, décision fondée sur la théorie (Markowitz)
- Parties prenantes : investisseur particulier (client simulé), jury certification

**Objectifs SMART définis :**
- Automatiser l'ingestion quotidienne de 13 symboles depuis l'API Binance
- Calculer rendements, volatilité, corrélation en < 60 secondes
- Exposer un portefeuille optimisé via API REST et dashboard interactif

> *Notes : Citer les SMART goals et la méthode RICE utilisée pour prioriser. Référencer 01_analyse_besoin.md.*

---

## SLIDE 3 — Cartographie des Données (C2)

**5 sources de données hétérogènes intégrées (C8)**

| Source | Type | Données |
|--------|------|---------|
| Binance API | REST/JSON | OHLCV klines (1j, 13 symboles) |
| symbols_metadata.csv | CSV | Métadonnées actifs |
| portfolio_config.json | JSON | Config allocation initiale |
| CoinGecko | Web scraping | Benchmarks de marché |
| PostgreSQL | Base relationnelle | Données historiques benchmarks |

**Flux de données :** API → Bronze → Silver → Gold → DWH → API REST → Dashboard

> *Notes : Expliquer le principe de Data Lineage. Montrer que chaque source répond à une règle d'agrégation distincte (C10).*

---

## SLIDE 4 — Cadre Technique (C3)

**Décisions architecturales fondées sur des ADR (Architecture Decision Records)**

| Décision | Choix | Justification |
|----------|-------|---------------|
| Format stockage | Parquet | Colonnaire, compressé, schéma fort |
| Moteur DWH | DuckDB | OLAP embarqué, SQL natif sur Parquet |
| Pas de Pandas | PyArrow | Mémoire efficace, typage strict |
| API | FastAPI | Async, OpenAPI auto, injection DI |
| Orchestration | Airflow | Standard industrie, monitoring |

5 ADR documentés dans `docs/architecture/adr/`

> *Notes : Insister sur le fait que chaque choix a une alternative rejetée documentée. Montrer la maturité d'ingénierie.*

---

## SLIDE 5 — Veille Technologique (C4)

**Surveillance active de 5 domaines**

1. **Streamlit** — évolutions dashboard (source : changelog officiel)
2. **DuckDB** — nouvelles fonctionnalités OLAP (source : duckdb.org)
3. **Binance API** — limites de taux, nouveaux endpoints (source : docs Binance)
4. **Airflow** — DAG authoring, TaskFlow API (source : apache.org)
5. **Réglementation crypto EU (MiCA)** — impact conformité (source : EUR-Lex)

Chaque item : source évaluée (fiabilité), impact analysé, action trackée.

> *Notes : Mentionner que la veille est documentée avec dates, sources cotées, et actions prises ou planifiées.*

---

## SLIDE 6 — Planification Projet (C5, C6)

**6 phases sur 12 semaines — 127h estimées**

```
Phase 1  Fondations      S1–S2   ████████████ 100%
Phase 2  Transformation  S3–S4   ████████████ 100%
Phase 3  Analytics       S5–S6   ████████████ 100%
Phase 4  Exposition      S7–S8   ████████████ 100%
Phase 5  Optimisation    S9–S10  ████████████ 100%
Phase 6  Finalisation    S11–S12 ████████████ 100%
GLOBAL                           ████████████ 100%
```

**5 jalons validés** | **254 tests passants** | **0 dette technique**

> *Notes : Mentionner la méthode Planning Poker pour les estimations. 5 jalons tous respectés.*

---

## SLIDE 7 — Architecture Globale

**Vue C4 — Niveau Contexte**

```
┌─────────────────────────────────────────────────────────┐
│  SOURCES           PIPELINE           EXPOSITION        │
│                                                         │
│  Binance API ──▶  BRONZE (raw/)  ──▶  FastAPI :8000    │
│  CSV/JSON    ──▶  SILVER (proc/) ──▶  Streamlit :8501  │
│  Scraping    ──▶  GOLD (output/) ──▶  OpenAPI /docs    │
│  PostgreSQL  ──▶  DuckDB DWH     ──▶  Airflow :8081    │
└─────────────────────────────────────────────────────────┘
```

- **5 conteneurs Docker** orchestrés via docker-compose
- **Airflow** = orchestrateur unique (DAG journalier automatique)
- **pipeline service** = bootstrap initial seulement

> *Notes : Montrer le docker-compose.yml. Expliquer la séparation bootstrap vs orchestration récurrente.*

---

## SLIDE 8 — Data Lake — Architecture 3 Zones (C18, C19, C20, C21)

**Zones Bronze / Silver / Gold + gouvernance**

| Zone | Contenu | Format | Rétention |
|------|---------|--------|-----------|
| Bronze (`data/raw/`) | Données brutes Binance | Parquet | 90 jours |
| Silver (`data/processed/`) | Rendements, métriques | Parquet | 1 an |
| Gold (`data/output/`) | Portefeuille optimisé, frontier | Parquet | Permanent |

- **Catalogue de données** complet : schéma, lignage, qualité, propriétaire (C20)
- **RGPD** : données publiques, aucune PII, pas d'applicabilité directe (C21)
- Politique de rétention documentée avec justification légale

> *Notes : Montrer data/ dans le terminal. Ouvrir un fichier Parquet dans DuckDB live.*

---

## SLIDE 9 — Pipeline ETL & Orchestration (C8, C10, C15, C16)

**Airflow DAG : 4 tâches séquentielles**

```
ingest_data ──▶ transform_data ──▶ optimize_portfolio ──▶ run_backtest
```

- **C8** — 5 sources via DataSource ABC + 5 implémentations
- **C10** — Règles d'agrégation : union de symboles, normalisation dates, alignement
- **C15** — DAG Airflow avec retry, timeout, SLA alerting
- **C16** — Monitoring via Airflow UI + logs structurés

**Scheduler** : `@daily` avec backfill automatique sur l'historique

> *Notes : Ouvrir Airflow UI (:8081). Montrer le DAG et un run réussi. Cliquer sur une tâche pour montrer les logs.*

---

## SLIDE 10 — Data Warehouse & Modélisation (C9, C11, C13, C14, C17)

**Schéma en étoile dans DuckDB**

```
        dim_symbol          dim_date
           │                   │
           └──────┬────────────┘
                  ▼
             fact_prices
         (symbol_id, date_id,
          open, high, low, close, volume)
```

- **C11** — MERISE complet : MCD → MLD → MPD, DDL généré
- **C13** — Faits : prix OHLCV | Dimensions : symbole, date
- **C14** — DuckDB avec vues analytiques et requêtes SQL complexes (C9)
- **C17** — SCD Type 1 (symboles actifs), Type 2 documenté pour évolution

> *Notes : Montrer une requête SQL analytique en live sur le DWH. Ex : top 5 symboles par volatilité.*

---

## SLIDE 11 — Exposition API REST (C12)

**FastAPI — 9 endpoints, OpenAPI auto-générée**

| Endpoint | Description |
|----------|-------------|
| `GET /symbols` | Liste des 13 symboles |
| `GET /klines/{symbol}` | Historique OHLCV |
| `GET /metrics` | Toutes les métriques |
| `GET /metrics/{name}` | Métrique spécifique |
| `GET /portfolio` | Portefeuille optimisé + poids |
| `GET /portfolio/summary` | KPIs consolidés |
| `GET /portfolio/frontier` | Frontier efficiente |
| `GET /portfolio/backtest` | Résultats walk-forward |

- **Injection DI** via `Depends()` — storage swappable en test
- **Pydantic** response models — validation et documentation auto

> *Notes : Ouvrir http://localhost:8000/docs. Faire un appel GET /portfolio live. Montrer la réponse JSON structurée.*

---

## SLIDE 12 — Dashboard Interactif (C12)

**Streamlit — 6 pages, Plotly, cache 5 min**

| Page | Contenu |
|------|---------|
| Dashboard | KPIs, allocation, risk contribution, risk-return scatter |
| Symbols | Charts techniques (SMA, Bollinger, RSI), compare mode |
| Metrics | Heatmaps corrélation/covariance, rolling pair correlation |
| Frontier | Frontier efficiente + iso-Sharpe + capital market line |
| Backtest | Walk-forward résultats, win rate, contribution par actif |
| Risk | Vol roulante, beta vs BTC, skewness, VaR/CVaR, réseau |

- Auto-refresh configurable | Refresh manuel | Date range selector

> *Notes : Ouvrir http://localhost:8501. Naviguer sur Dashboard → Frontier → Risk en direct.*

---

## SLIDE 13 — Optimisation de Portefeuille

**Théorie de Markowitz — implémentation pure Python**

**Méthode :**
1. Calcul matrice de covariance des rendements (PyArrow, ddof=1)
2. Optimisation SLSQP (scipy) : max Sharpe ratio, contraintes budget
3. Fallback grid search si scipy indisponible
4. Génération de la frontier efficiente (100 points)
5. Walk-forward backtest : train 90j → test 30j (glissant)

**Résultats (exemple) :**
- Sharpe ratio optimisé vs equal weight : mesuré en live
- Max drawdown : comparaison 3 stratégies (optimisé / equal weight / BTC only)

> *Notes : Montrer la page Frontier sur le dashboard. Pointer les iso-Sharpe curves et le portefeuille optimal.*

---

## SLIDE 14 — Qualité & Tests

**254 tests — 100% passants — ruff + mypy strict clean**

| Fichier de test | Tests | Couverture |
|----------------|-------|------------|
| test_transform.py | 37 | Calculs financiers |
| test_optimize.py | 53 | Markowitz, frontier, contraintes |
| test_ingest_sources.py | 40 | 5 sources DataSource ABC |
| test_api.py | 23 | 9 endpoints (mock storage) |
| test_backtest.py | 18 | Walk-forward, métriques |
| test_openapi_drift.py | 6 | Spec YAML vs code (anti-drift) |
| + 5 autres fichiers | 77 | Config, storage, ingest, scraping |

- **Zéro violation ruff** (E/F/W/I/UP/B/SIM)
- **Zéro erreur mypy** (strict=true)
- **CI-ready** : `uv run pytest tests/ -v`

> *Notes : Lancer `uv run pytest tests/ -v` en live si le temps le permet. Montrer 254 passed.*

---

## SLIDE 15 — Choix Techniques — Justifications ADR

**Pourquoi ces choix résistent à un peer review ?**

| Question jury probable | Réponse |
|------------------------|---------|
| Pourquoi PyArrow et pas Pandas ? | Mémoire 2–5× plus efficace, typage strict, ADR-003 |
| Pourquoi DuckDB et pas PostgreSQL ? | OLAP embarqué, SQL sur Parquet sans serveur, ADR-002 |
| Pourquoi Airflow et pas Cron ? | Retry, DAG visualisation, alerting SLA, ADR-005 |
| Pourquoi FastAPI et pas Flask ? | Async natif, OpenAPI auto, Depends() injection, ADR-004 |
| Comment scale si 100 symboles ? | Storage ABC pluggable (S3/MinIO), Airflow parallélisme |

> *Notes : Avoir les ADR ouverts en backup. Chaque décision a une alternative rejetée documentée.*

---

## SLIDE 16 — Conformité RGPD & Éco-conception (C21)

**RGPD : données publiques, pas d'applicabilité directe**

- Données Binance = cours publics, aucune PII collectée
- Registre des traitements : 1 traitement (analyse de marché), base légale = intérêt légitime
- Mesures préventives documentées pour évolution (si données utilisateurs ajoutées)
- Politique de rétention : Bronze 90j, Silver 1 an, Gold permanent

**Éco-conception :**
- PyArrow : empreinte mémoire réduite vs Pandas
- DuckDB : pas de serveur dédié (0 idle compute)
- Parquet : compression native (–60–80% vs CSV)
- Docker : reproducibilité = pas de sur-provisionnement

> *Notes : Référencer 07_rgpd.md. Mentionner que le registre des traitements est conforme CNIL.*

---

## SLIDE 17 — Résultats & Bilan

**Projet 100% complet — 21 compétences couvertes**

| Bloc | Compétences | Status |
|------|-------------|--------|
| Bloc 1 — Pilotage | C1–C7 | ✅ 7/7 |
| Bloc 2 — Collecte/Stockage | C8–C12 | ✅ 5/5 |
| Bloc 3 — Data Warehouse | C13–C17 | ✅ 5/5 |
| Bloc 4 — Data Lake | C18–C21 | ✅ 4/4 |

**Livrables :**
- 5 000+ lignes de code Python production-ready
- 10 documents de rapport certification
- 5 conteneurs Docker orchestrés
- API REST + dashboard interactif déployés

> *Notes : Conclure sur la cohérence bout-en-bout : du besoin métier jusqu'au dashboard live.*

---

## SLIDE 18 — Perspectives & Limites

**Ce qui a été fait — ce qui pourrait évoluer**

**Limites actuelles (honnêteté technique) :**
- Pas de streaming temps-réel (données journalières uniquement)
- Pas de ML prédictif (Markowitz = théorie classique)
- Grid search fallback limité à ~15 actifs (scipy recommandé)

**Évolutions naturelles :**
- Kafka / Flink pour streaming intraday
- Modèles ML (LSTM, transformer) pour prédiction de rendements
- S3/MinIO pour scaling du Data Lake en production cloud
- SCD Type 2 pour l'historisation des métadonnées symboles

> *Notes : Montrer la maturité d'ingénieur : on sait ce qu'on a fait ET ce qu'on n'a pas fait, et pourquoi.*

---

## SLIDE 19 — Conclusion

**Un système de données complet, de bout en bout**

```
Besoin métier → 5 sources → Data Lake → DWH → API → Dashboard
     C1             C8          C18        C13    C12     C12
```

- Architecture propre, testée, documentée
- Décisions fondées sur ADR, patterns industriels
- Conformité RGPD démontrée
- Démonstration live disponible

**Merci pour votre attention.**

> *Notes : Remercier le jury. Inviter les questions. Avoir les démos prêtes : terminal (pipeline), API (:8000/docs), Dashboard (:8501), Airflow (:8081).*

---

## SLIDE 20 — Questions & Réponses

*[Slide de fond pendant les questions]*

**Points chauds préparés :**
- Architecture Storage ABC → swappabilité backend
- PyArrow matrice de covariance → preuve calcul
- Walk-forward backtest → pas de data leakage
- RGPD → registre des traitements
- Scale → pluggabilité + orchestration Airflow

**Liens utiles pendant Q&A :**
- `http://localhost:8000/docs` — API live
- `http://localhost:8501` — Dashboard live
- `http://localhost:8081` — Airflow DAG live

---

*Document généré le 2026-02-21 — Version 1.0*
*Candidat : Laien Wu — RNCP Niveau 7 — Expert en Infrastructures de Données Massives*
