# Planification et Supervision (C5, C6)

## 1. Composition de l'equipe

### 1.1 Equipe projet

| Role | Personne | Competences | Responsabilites |
|------|----------|-------------|-----------------|
| Data Engineer | Laien Wu | Python, SQL, Docker, ETL, PyArrow, streaming | ADR, C4, specification API, rapport, code |
| Product Owner | Marie Dupont | Definition besoin metier, priorisation | User stories, KPIs, validation fonctionnelle |
| Business Analyst | Jean-Martin | Analyse fonctionnelle, documentation | RACI, comptes-rendus de reunion |
| Data Analyst | Sophie Bernard | Statistiques, validation des metriques | Validation des calculs financiers |
| DevOps | Pierre Durand | Docker, CI/CD, monitoring, securite | Runbook, monitoring, SLA, securite |
| Scrum Master | Lucas Petit | Methodologie Agile, facilitation | Animation des ceremonies, suivi |

### 1.2 Matrice RACI simplifiee

| Activite | Laien Wu | Marie Dupont | Jean-Martin | Sophie Bernard | Pierre Durand | Lucas Petit |
|----------|----------|--------------|-------------|----------------|---------------|-------------|
| Architecture | R | I | I | C | C | I |
| Developpement | R | I | I | I | C | I |
| Tests | R | I | I | C | I | I |
| Documentation | R | A | C | C | C | I |
| Deploiement | R | I | I | I | C | I |
| Validation metier | C | A | R | C | I | I |
| Suivi projet | C | I | I | I | I | R |

R = Responsable, A = Approbateur, C = Consulte, I = Informe

### 1.3 Budget

| Poste | Montant | Justification |
|-------|---------|---------------|
| Ressources humaines | 0 EUR | Projet certification (1 developpeur reel, equipe simulee) |
| Infrastructure | 0 EUR | Local / Docker, pas de cloud |
| Licences logicielles | 0 EUR | 100% open-source |
| **Total reel** | **0 EUR** | Projet academique |

**Estimation du cout equivalent en contexte professionnel** :

| Poste | Estimation | Base |
|-------|-----------|------|
| Data Engineer (6 mois) | 30 000 EUR | TJM 500 EUR x 60 jours |
| Infrastructure cloud (6 mois) | 3 000 EUR | VM + stockage + Kafka managed |
| Licences (monitoring, CI) | 0 EUR | Stack open-source |
| **Total equivalent** | **~33 000 EUR** | -- |

---

## 2. Feuille de route

### 2.1 Grandes etapes (8 phases)

```
PHASE 1 : FONDATIONS (Semaines 1-2)
 -- Setup environnement (Git, pyproject.toml, uv)
 -- Architecture storage (ABC + ParquetStorage)
 -- Pipeline ingest (Binance API + 5 autres sources)
 -- Configuration centralisee (PipelineConfig)

PHASE 2 : TRANSFORMATION (Semaines 3-4)
 -- Calculs statistiques (rendements, volatilite, correlation, covariance)
 -- Pipeline transform (PyArrow, pas de pandas)
 -- Tests unitaires

PHASE 3 : ANALYTICS & DWH (Semaines 5-6)
 -- DuckDB warehouse (star schema)
 -- dbt-duckdb (staging + marts)
 -- Requetes SQL analytiques (C9)

PHASE 4 : EXPOSITION (Semaines 7-9)
 -- FastAPI (46 endpoints, Depends injection, Pydantic schemas)
 -- Streamlit dashboard (32 pages)
 -- Docker packaging (5 Dockerfiles)
 -- Airflow DAG (orchestration)

PHASE 5 : OPTIMISATION AVANCEE (Semaines 10-12)
 -- 6 strategies : Markowitz, HRP, Risk Parity, Min Variance, Max Diversification, Black-Litterman
 -- Backtesting walk-forward
 -- Monte Carlo, stress tests, drawdown, attribution
 -- Signaux de trading (SMA, RSI, MACD, Bollinger)
 -- Pair trading, analyse factorielle, tail risk

PHASE 6 : STREAMING & BIG DATA (Semaines 13-14)
 -- Kafka / Redpanda (WebSocket Binance -> topics)
 -- Consommateur micro-batch (Parquet Bronze)
 -- PySpark (correlation glissante, surface de volatilite)
 -- Delta Lake (stockage ACID optionnel)

PHASE 7 : MONITORING & OBSERVABILITE (Semaines 15-16)
 -- Prometheus (scraping metriques API)
 -- Grafana (tableaux de bord)
 -- Alertes (latence, taux d'erreur)
 -- Metriques metier personnalisees

PHASE 8 : FINALISATION (Semaines 17-18)
 -- Documentation complete (rapport, ADR, catalogue, RGPD, MERISE)
 -- Slides soutenance (HTML)
 -- Preparation orale
 -- Demo end-to-end
```

### 2.2 Diagramme de Gantt

```
Semaine    1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18
           ────────────────────────────────────────────────────────
Phase 1    ████
Phase 2          ████
Phase 3                ████
Phase 4                      ██████
Phase 5                               ██████
Phase 6                                     ████
Phase 7                                           ████
Phase 8                                                 ████
           ────────────────────────────────────────────────────────
Jalons     J1       J2       J3    J4       J5    J6    J7    J8
```

### 2.3 Jalons

| Jalon | Semaine | Livrable | Critere de validation |
|-------|---------|----------|-----------------------|
| J1 | S2 | Pipeline ingest fonctionnel | 6 sources ingerees, donnees en raw/ |
| J2 | S4 | Metriques calculees | Rendements, volatilite, correlation en processed/ |
| J3 | S6 | DWH + dbt operationnel | Star schema, modeles dbt, requetes SQL OK |
| J4 | S9 | API + dashboard deployes | 46 endpoints, 32 pages Streamlit, /docs accessible |
| J5 | S12 | Analytics avancees | 6 strategies, backtest, Monte Carlo fonctionnels |
| J6 | S14 | Streaming operationnel | Kafka producer/consumer, donnees temps reel |
| J7 | S16 | Monitoring actif | Prometheus + Grafana, alertes configurees |
| J8 | S18 | Projet complet | Rapport, slides, demo -- soutenance ready |

### 2.4 Chemin critique (PERT)

Le chemin critique identifie les taches dont tout retard impacte directement la date de livraison :

```
Ingest (P1) --> Transform (P2) --> DWH/dbt (P3) --> API (P4) --> Optimisation (P5) --> Finalisation (P8)
                                                                        |
                                                                        v
                                                              Streaming (P6) --> Monitoring (P7)
```

**Taches sur le chemin critique** :
1. `1.4` Interface Storage (toutes les phases en dependent)
2. `2.1` Calcul rendements (prerequis de l'optimisation)
3. `3.2` Star schema (prerequis des requetes analytiques et de l'API)
4. `5.1` Algorithme Markowitz (prerequis du backtest et des strategies avancees)
5. `8.2` Rapport certification (prerequis de la soutenance)

Les phases 6 (Streaming) et 7 (Monitoring) sont **hors chemin critique** : un retard sur ces phases n'impacte pas la date de soutenance.

---

## 3. Decoupage en taches

### 3.1 Phase 1 -- Fondations

| ID | Tache | Effort | Responsable | Dependance |
|----|-------|--------|-------------|------------|
| 1.1 | Setup Git repo + pyproject.toml | 2h | Laien Wu | -- |
| 1.2 | Structure dossiers (data/, src/, tests/) | 1h | Laien Wu | 1.1 |
| 1.3 | PipelineConfig dataclass + load_config() | 4h | Laien Wu | 1.2 |
| 1.4 | Interface Storage ABC + factory | 4h | Laien Wu | 1.2 |
| 1.5 | ParquetStorage | 8h | Laien Wu | 1.4 |
| 1.6 | Module ingest Binance API | 8h | Laien Wu | 1.5 |
| 1.7 | Ingest multi-sources (CSV, JSON, scraping, PostgreSQL, yfinance) | 8h | Laien Wu | 1.5 |
| 1.8 | Tests ingest | 4h | Laien Wu | 1.6, 1.7 |

### 3.2 Phase 2 -- Transformation

| ID | Tache | Effort | Responsable | Dependance |
|----|-------|--------|-------------|------------|
| 2.1 | Calcul rendements (log returns PyArrow) | 4h | Laien Wu | 1.6 |
| 2.2 | Calcul volatilite | 2h | Laien Wu | 2.1 |
| 2.3 | Matrice correlation | 4h | Laien Wu | 2.1 |
| 2.4 | Matrice covariance | 2h | Laien Wu | 2.3 |
| 2.5 | Tests transform | 4h | Laien Wu | 2.4 |

### 3.3 Phase 3 -- Analytics & DWH

| ID | Tache | Effort | Responsable | Dependance |
|----|-------|--------|-------------|------------|
| 3.1 | DuckDBStorage | 8h | Laien Wu | 1.4 |
| 3.2 | Star schema (fact_prices, dim_symbol, dim_date) | 4h | Laien Wu | 3.1 |
| 3.3 | dbt-duckdb : staging + marts | 8h | Laien Wu | 3.2 |
| 3.4 | Requetes analytiques SQL | 4h | Laien Wu | 3.3 |
| 3.5 | Tests DuckDB + tests dbt | 4h | Laien Wu | 3.4 |

### 3.4 Phase 4 -- Exposition

| ID | Tache | Effort | Responsable | Dependance |
|----|-------|--------|-------------|------------|
| 4.1 | Setup FastAPI + Depends injection | 4h | Laien Wu | 3.1 |
| 4.2 | 46 endpoints (portfolio, backtest, frontier, signals...) | 16h | Laien Wu | 4.1 |
| 4.3 | Pydantic schemas (src/api/schemas.py) | 4h | Laien Wu | 4.2 |
| 4.4 | Streamlit dashboard (32 pages) | 24h | Laien Wu | 4.2 |
| 4.5 | Dockerfiles (API, Airflow, Streamlit, Streaming, Spark) | 8h | Laien Wu | 4.2 |
| 4.6 | docker-compose.yml (profiles) | 4h | Laien Wu | 4.5 |
| 4.7 | Airflow DAG | 4h | Laien Wu | 4.2 |
| 4.8 | Tests API + tests OpenAPI drift | 4h | Laien Wu | 4.3 |

### 3.5 Phase 5 -- Optimisation avancee

| ID | Tache | Effort | Responsable | Dependance |
|----|-------|--------|-------------|------------|
| 5.1 | Markowitz + frontiere efficiente | 8h | Laien Wu | 2.4 |
| 5.2 | HRP (Hierarchical Risk Parity) | 4h | Laien Wu | 2.4 |
| 5.3 | Risk Parity | 4h | Laien Wu | 2.4 |
| 5.4 | Min Variance + Max Diversification | 4h | Laien Wu | 2.4 |
| 5.5 | Black-Litterman | 8h | Laien Wu | 2.4 |
| 5.6 | Backtesting walk-forward | 8h | Laien Wu | 5.1 |
| 5.7 | Monte Carlo, stress tests, drawdown | 8h | Laien Wu | 5.1 |
| 5.8 | Signaux de trading (SMA, RSI, MACD, Bollinger) | 4h | Laien Wu | 2.1 |
| 5.9 | Pair trading, facteurs, tail risk | 8h | Laien Wu | 2.4 |
| 5.10 | Tests (37 fichiers de tests) | 16h | Laien Wu | 5.1-5.9 |

### 3.6 Phase 6 -- Streaming & Big Data

| ID | Tache | Effort | Responsable | Dependance |
|----|-------|--------|-------------|------------|
| 6.1 | Kafka producer (WebSocket Binance -> topics) | 8h | Laien Wu | 1.5 |
| 6.2 | Kafka consumer (micro-batch -> Parquet Bronze) | 8h | Laien Wu | 6.1 |
| 6.3 | PySpark transforms (correlation, volatilite, volume) | 8h | Laien Wu | 2.4 |
| 6.4 | Delta Lake storage backend | 4h | Laien Wu | 1.4 |
| 6.5 | Tests streaming + Delta + Spark | 4h | Laien Wu | 6.1-6.4 |

### 3.7 Phase 7 -- Monitoring & Observabilite

| ID | Tache | Effort | Responsable | Dependance |
|----|-------|--------|-------------|------------|
| 7.1 | Prometheus scraping + metriques personnalisees | 4h | Laien Wu | 4.2 |
| 7.2 | Grafana dashboard (rate, latence, erreurs) | 4h | Laien Wu | 7.1 |
| 7.3 | Alertes (latence, taux d'erreur) | 2h | Laien Wu | 7.2 |
| 7.4 | Tests monitoring | 2h | Laien Wu | 7.1 |

### 3.8 Phase 8 -- Finalisation

| ID | Tache | Effort | Responsable | Dependance |
|----|-------|--------|-------------|------------|
| 8.1 | Documentation technique (ADR, C4, catalogue, MERISE) | 8h | Laien Wu | -- |
| 8.2 | Rapport certification (10 documents) | 16h | Laien Wu | 8.1 |
| 8.3 | Slides soutenance (HTML) | 8h | Laien Wu | 8.2 |
| 8.4 | Preparation orale | 4h | Laien Wu | 8.3 |
| 8.5 | Demo end-to-end | 4h | Laien Wu | 8.3 |

---

## 4. Estimation des efforts

### 4.1 Methode d'estimation

Estimation en heures avec methode **Planning Poker** adaptee :
- Les estimations sont partagees en sprint planning avec l'equipe (simulee)
- Chaque membre donne son estimation independamment
- En cas d'ecart > 2x, discussion et re-estimation
- Echelle utilisee :
  - 1-2h = tache triviale
  - 4h = tache simple
  - 8h = tache complexe
  - 16h = tache majeure
  - 24h = epic (a decouper)

### 4.2 Recapitulatif

| Phase | Effort estime | % du projet |
|-------|---------------|-------------|
| 1. Fondations | 39h | 12% |
| 2. Transformation | 16h | 5% |
| 3. Analytics & DWH | 28h | 9% |
| 4. Exposition | 68h | 22% |
| 5. Optimisation avancee | 72h | 23% |
| 6. Streaming & Big Data | 32h | 10% |
| 7. Monitoring | 12h | 4% |
| 8. Finalisation | 40h | 13% |
| **Total** | **307h** | 100% |

---

## 5. Suivi et indicateurs (C5)

### 5.1 Indicateurs de suivi (KPIs)

| Indicateur | Cible | Mesure | Resultat |
|------------|-------|--------|----------|
| Taches completees | 100% | Checklist par phase | 100% |
| Jalons respectes | 8/8 | Dates vs previsionnel | 8/8 |
| Tests passants | 100% | CI/CD (GitHub Actions) | 748/748 |
| Couverture code | >80% | pytest --cov | Atteint |
| Lint clean | 0 erreur | ruff check src/ | 0 erreur |
| Type check clean | 0 erreur | mypy src/ | 0 erreur |

### 5.2 Tableau de bord

```
AVANCEMENT PROJET
================================================================
Phase 1 : Fondations             [████████████████████] 100%
Phase 2 : Transformation         [████████████████████] 100%
Phase 3 : Analytics & DWH        [████████████████████] 100%
Phase 4 : Exposition              [████████████████████] 100%
Phase 5 : Optimisation avancee   [████████████████████] 100%
Phase 6 : Streaming & Big Data   [████████████████████] 100%
Phase 7 : Monitoring              [████████████████████] 100%
Phase 8 : Finalisation            [████████████████████] 100%
================================================================
GLOBAL                           [████████████████████] 100%

Tests : 748 passants / 748 total (37 fichiers)
```

### 5.3 Rituels de suivi

| Rituel | Frequence | Duree | Participants | Objectif |
|--------|-----------|-------|--------------|----------|
| Daily standup | Quotidien | 15 min | Equipe complete | Blocages, synchronisation |
| Sprint planning | Debut de sprint | 1h | Equipe complete | Estimation, planification |
| Sprint review | Bi-mensuel | 1h | Equipe + PO | Demo, validation |
| Retrospective | Bi-mensuel | 45 min | Equipe | Amelioration continue |
| Point formateur | Hebdomadaire | 30 min | Laien Wu + formateur | Avancement certification |

---

## 6. Animation et supervision (C6)

### 6.1 Animation des echanges

L'animation des echanges au sein de l'equipe projet est assuree par le Scrum Master (Lucas Petit) :
- **Sprint planning** : priorisation du backlog avec le PO, estimation collective (Planning Poker)
- **Daily standup** : tour de table structure (fait hier / prevu aujourd'hui / blocages)
- **Sprint review** : demonstration des livrables aux parties prenantes
- **Retrospective** : identification des points d'amelioration (Keep / Stop / Start)

### 6.2 Arbitrages techniques

Les arbitrages techniques sont documentes dans les ADR (Architecture Decision Records) :

| Decision | Date | Justification | ADR |
|----------|------|---------------|-----|
| Parquet comme format de stockage | S1 | Colonnaire, compresse, schema | ADR-001 |
| DuckDB pour le DWH | S1 | OLAP integre, sans serveur | ADR-002 |
| PyArrow au lieu de pandas | S1 | Memoire efficace, type safe | ADR-003 |
| FastAPI pour l'exposition | S7 | OpenAPI auto, async | ADR-004 |
| Airflow pour l'orchestration | S7 | Standard industrie | ADR-005 |
| Delta Lake optionnel | S13 | ACID, time travel | ADR-006 |
| dbt-duckdb pour les transforms | S5 | SQL, tests, lineage | ADR-007 |

### 6.3 Suivi budgetaire

| Poste | Budget prevu | Depense reelle | Ecart |
|-------|-------------|----------------|-------|
| Ressources humaines | 0 EUR | 0 EUR | 0 EUR |
| Infrastructure | 0 EUR | 0 EUR | 0 EUR |
| Licences | 0 EUR | 0 EUR | 0 EUR |
| **Total** | **0 EUR** | **0 EUR** | **0 EUR** |

Le projet etant academique avec une stack 100% open-source et un deploiement local (Docker), aucun depassement budgetaire n'est constate.

### 6.4 Gestion des indicateurs de suivi

Les indicateurs sont mis a jour a chaque fin de sprint :
- **Velocity** : nombre de taches completees par sprint
- **Burndown** : reste a faire vs previsionnel
- **Tests** : nombre de tests passants, couverture
- **Qualite** : nombre d'erreurs lint/mypy

---

## 7. Gestion des risques

### 7.1 Registre des risques

| Risque | Probabilite | Impact | Mitigation | Status |
|--------|-------------|--------|------------|--------|
| API Binance indisponible | Faible | Moyen | Cache local, retry, fallback yfinance | Mitige |
| Retard sur optimisation avancee | Moyen | Haut | Buffer 1 semaine, strategies incrementales | Mitige |
| Bug bloquant en production | Moyen | Moyen | 748 tests, CI/CD, code review | Mitige |
| Indisponibilite d'un membre | Faible | Haut | Documentation exhaustive, bus factor = 1 acceptable (certification) | Accepte |
| Incompatibilite versions | Faible | Moyen | Lockfile uv.lock, Docker images figees | Mitige |
| Donnees corrompues | Faible | Haut | Validation pipeline, Delta Lake rollback | Mitige |

### 7.2 Plan de contingence

- **Retard > 1 semaine** : reduire le scope des fonctionnalites non-critiques (streaming, monitoring)
- **Bug critique** : rollback via Git, Delta Lake time travel pour les donnees
- **API indisponible** : utiliser les donnees en cache local (Parquet)

---

## 8. Accessibilite des documents de planification (RGAA)

Conformement au Referentiel General d'Amelioration de l'Accessibilite :

| Critere | Application |
|---------|-------------|
| Format | Markdown structure, exportable en PDF accessible |
| Tableaux | En-tetes de colonnes identifies |
| Diagrammes | ASCII art (pas d'images), lisible par lecteur d'ecran |
| Langue | Document en francais |
| Navigation | Titres hierarchiques, table des matieres |
