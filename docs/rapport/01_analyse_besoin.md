# Analyse du Besoin (C1)

## 1. Contexte et enjeux

### 1.1 Presentation de l'organisation
L'organisation **CryptoInvest SA** est une societe de gestion d'actifs numeriques souhaitant optimiser ses strategies d'investissement en cryptomonnaies et en actifs traditionnels. Face a la volatilite du marche crypto et a la necessite de diversification multi-classes, la direction souhaite mettre en place une infrastructure data permettant d'analyser les donnees de marche, d'optimiser l'allocation de portefeuille et de fournir des outils de decision en temps reel.

### 1.2 Expression du besoin initial
> "Nous souhaitons disposer d'un outil permettant de collecter automatiquement les donnees de marche crypto et traditionnelles, de les analyser, et de proposer une allocation optimale de portefeuille basee sur la theorie moderne du portefeuille (Markowitz) et des methodes avancees (Black-Litterman, HRP, Risk Parity)."

### 1.3 Enjeux strategiques
- **Performance** : Ameliorer le rendement ajuste au risque des portefeuilles via 6 strategies d'optimisation
- **Automatisation** : Reduire les taches manuelles de collecte de donnees via un pipeline ETL orchestre
- **Scalabilite** : Pouvoir ajouter de nouveaux actifs facilement (84 actifs actuellement : 51 crypto + 33 traditionnels)
- **Conformite** : Respecter les reglementations (RGPD, tracabilite, gouvernance des donnees)
- **Temps reel** : Capturer les donnees de marche en streaming pour des decisions rapides

### 1.4 Identification des metiers impliques

Les metiers identifies se repartissent selon trois familles :

| Famille | Metier | Role dans le projet |
|---------|--------|---------------------|
| **Sources / Generation** | Equipe Trading | Definit les actifs suivis, les indicateurs a calculer, les frequences de mise a jour |
| **Sources / Generation** | Analystes Quantitatifs | Specifie les modeles d'optimisation (Markowitz, Black-Litterman, HRP) et les metriques de risque |
| **Collecte / Stockage** | Data Engineer | Concoit le pipeline ETL, le Data Lake (Bronze/Silver/Gold), le Data Warehouse (DuckDB) |
| **Collecte / Stockage** | DevOps | Deploie l'infrastructure Docker, Kafka, Airflow, monitoring Prometheus/Grafana |
| **Exploitation / Analyse** | Equipe de Gestion | Consulte le dashboard Streamlit (32 pages), utilise l'API REST pour les decisions d'allocation |
| **Exploitation / Analyse** | Direction Generale | Suit les KPI de performance portefeuille, valide les strategies |

---

## 2. Grilles d'entretien

### 2.1 Entretien Direction Generale

| Question | Reponse |
|----------|---------|
| Quels sont les objectifs business du projet ? | Optimiser l'allocation de portefeuille pour maximiser le ratio rendement/risque |
| Quel est le budget alloue ? | Budget limite, privilegier les solutions open-source |
| Quels sont les delais ? | MVP en 3 mois |
| Qui sont les utilisateurs finaux ? | Equipe de gestion, analystes quantitatifs |

### 2.2 Entretien Equipe Trading

| Question | Reponse |
|----------|---------|
| Quelles donnees utilisez-vous actuellement ? | Prix OHLCV manuellement extraits de Binance |
| Quelle frequence de mise a jour ? | Quotidienne pour le batch, temps reel pour le streaming |
| Quels actifs suivez-vous ? | 51 cryptomonnaies (BTC, ETH, etc.) + 33 actifs traditionnels (actions, ETF, matieres premieres) |
| Quels indicateurs calculez-vous ? | Rendements, volatilite, correlations, signaux de trading (SMA, RSI, MACD, Bollinger) |

### 2.3 Entretien IT / Infrastructure

| Question | Reponse |
|----------|---------|
| Quelle infrastructure existante ? | Serveurs Linux, pas de cloud |
| Contraintes techniques ? | Pas de base de donnees lourde (Postgres optionnel pour benchmarks) |
| Competences equipe ? | Python, SQL, Docker, Kafka |
| Exigences securite ? | Donnees publiques, pas de PII — gouvernance RGPD neanmoins appliquee |

---

## 3. Note de synthese

### 3.1 Reformulation du besoin
Le projet vise a creer une **infrastructure data complete** pour :
1. **Collecter** automatiquement les donnees OHLCV depuis 6 sources (API Binance, CSV, JSON, scraping CoinGecko, PostgreSQL, yfinance)
2. **Ingerer en streaming** les donnees temps reel via Kafka (Redpanda) depuis le WebSocket Binance
3. **Stocker** les donnees dans un Data Lake structure (Bronze/Silver/Gold) avec support Delta Lake
4. **Transformer** les donnees brutes en metriques (rendements, volatilite, correlations, facteurs)
5. **Analyser** via un Data Warehouse en schema etoile (DuckDB) avec transforms dbt
6. **Optimiser** l'allocation de portefeuille via 6 strategies (Markowitz, Black-Litterman, HRP, Risk Parity, Min Variance, Max Diversification)
7. **Backtester** les strategies via un moteur walk-forward sur fenetres glissantes
8. **Exposer** les resultats via API REST (35+ endpoints) et un dashboard interactif (32 pages Streamlit)

### 3.2 Perimetre fonctionnel

| Inclus | Exclus |
|--------|--------|
| Collecte multi-sources (6 sources : API, CSV, JSON, scraping, PostgreSQL, yfinance) | Trading automatique (execution d'ordres) |
| Streaming temps reel (Kafka/Redpanda, WebSocket Binance, order book) | Machine Learning predictif (prevision de prix) |
| Stockage Data Lake (Parquet, Delta Lake) + Data Warehouse (DuckDB, dbt) | Architecture multi-tenant |
| Calculs statistiques avances (facteurs, tail risk, cointegration) | |
| 6 strategies d'optimisation (Markowitz, BL, HRP, RP, MinVar, MaxDiv) | |
| Backtesting walk-forward multi-strategies | |
| API REST FastAPI (35+ endpoints, cache Redis, metriques Prometheus) | |
| Dashboard Streamlit interactif (32 pages) | |
| Orchestration Airflow (DAG planifie) | |
| Monitoring (Prometheus, Grafana, alertes) | |

### 3.3 Moyens mobilisables

**Equipe projet :**

| Role | Nom | Responsabilites |
|------|------|-----------------|
| Product Owner | Marie Dupont | User stories, KPI, validation metier |
| Business Analyst | Jean-Martin | RACI, notes de reunion, expression des besoins |
| Data Engineer | Laien Wu | Architecture, pipeline ETL, ADR, API, rapport technique |
| Data Analyst | Sophie Bernard | Validation des metriques, tests de coherence |
| DevOps | Pierre Durand | Infrastructure Docker, Kafka, monitoring, SLA, securite |
| Scrum Master | Lucas Petit | Animation des ceremonies agiles |

**Moyens techniques :**
- Python 3.13+, PyArrow, DuckDB, FastAPI, Streamlit, Airflow, Kafka (Redpanda)
- Docker Compose (multi-profils : full, streaming, monitoring, airflow)
- CI/CD : GitHub Actions (lint, tests, type-check)

**Moyens financiers :**
- Budget limite — solutions 100% open-source (pas de services cloud payants)

### 3.4 Analyse RICE

| Fonctionnalite | Reach | Impact | Confidence | Effort | Score |
|----------------|-------|--------|------------|--------|-------|
| Pipeline ETL multi-sources | 5 | 5 | 5 | 3 | 41.7 |
| Data Warehouse (DuckDB + dbt) | 4 | 4 | 4 | 2 | 32.0 |
| API REST (35+ endpoints) | 3 | 3 | 5 | 1 | 45.0 |
| Optimisation multi-strategies | 5 | 5 | 4 | 2 | 50.0 |
| Streaming Kafka | 3 | 4 | 4 | 3 | 16.0 |
| Dashboard Streamlit (32 pages) | 5 | 4 | 5 | 3 | 33.3 |
| Backtesting walk-forward | 4 | 5 | 4 | 2 | 40.0 |

**Priorite** : Optimisation > API > Pipeline > Backtesting > Dashboard > DWH > Streaming

### 3.5 Objectifs SMART

1. **Specifique** : Creer un pipeline ETL collectant les donnees de marche depuis 6 sources heterogenes (API, CSV, JSON, scraping, PostgreSQL, yfinance) et les transformant en metriques financieres exploitables
2. **Mesurable** : Traiter 51 cryptomonnaies + 33 actifs traditionnels avec donnees sur 30 jours, exposer 35+ endpoints API, livrer un dashboard de 32 pages
3. **Atteignable** : Technologies maitrisees par l'equipe (Python, SQL, Docker), stack 100% open-source, architecture locale sans dependance cloud
4. **Realiste** : Architecture deployee localement via Docker Compose, pas de cloud, pas de couts d'infrastructure recurrents
5. **Temporel** : MVP fonctionnel en 3 mois (sprint 1 : ingestion/stockage, sprint 2 : transformation/optimisation, sprint 3 : exposition/dashboard)

### 3.6 Eco-responsabilite

**Cycle de vie simplifie du projet :**

| Phase | Actions eco-responsables | Impact |
|-------|--------------------------|--------|
| **Conception** | Choix de DuckDB (in-process, pas de serveur dedie) au lieu d'un SGBD lourd ; PyArrow au lieu de pandas (empreinte memoire reduite) | Reduction de la consommation CPU/RAM |
| **Developpement** | Architecture locale Docker sans cloud (pas de data center distant) ; format Parquet colonnaire compresse (reduction stockage ~80% vs CSV) | Reduction du stockage et des transferts reseau |
| **Execution** | Airflow DAG planifie (execution a heures definies, pas de polling continu) ; streaming consommateur micro-batch (pas de traitement unitaire) | Reduction des cycles CPU inutiles |
| **Monitoring** | Prometheus avec retention limitee (15j) ; alertes ciblees (pas de scraping excessif) | Limitation de la croissance des donnees de supervision |
| **Fin de vie** | Donnees publiques (pas de PII a purger) ; conteneurs Docker ephemeres (pas de VM persistantes surdimensionnees) | Desengagement propre des ressources |

**Mesures concretes :**
- Compression Snappy/Zstd sur tous les fichiers Parquet (ratio ~5:1)
- Requetes DuckDB en lecture directe sur fichiers (pas de duplication en memoire)
- Cache Redis avec TTL pour eviter les recalculs inutiles
- Delta Lake avec compaction pour limiter la proliferation de fichiers

### 3.7 Accessibilite

**Anticipation de l'effort d'accessibilite tout au long du projet :**

| Livrable | Mesures d'accessibilite |
|----------|-------------------------|
| **Dashboard Streamlit** | Contraste suffisant (fond sombre, texte clair) ; labels explicites sur tous les graphiques ; legende textuelle sur chaque visualisation ; KPI affiches en texte large lisible |
| **API REST** | Documentation OpenAPI auto-generee et consultable ; messages d'erreur explicites avec codes HTTP standards ; schemas Pydantic avec descriptions |
| **Documentation technique** | Structure Markdown avec hierarchie de titres (H1-H4) ; tableaux avec en-tetes ; pas de contenu uniquement visuel sans description textuelle |
| **Presentation soutenance** | Slides HTML avec texte lisible (taille min 18px) ; palette de couleurs accessible ; contenu textuel accompagnant chaque schema |

---

## 4. Etude de faisabilite

### 4.1 Solution preconisee
Architecture **Data Lake + Data Warehouse** legere :
- **Stockage** : Parquet + Delta Lake (Data Lake Bronze/Silver/Gold) + DuckDB (Data Warehouse schema etoile)
- **ETL batch** : Pipeline Python orchestre par Airflow (ingest → transform → optimize → frontier → backtest)
- **ETL streaming** : Binance WebSocket → Kafka (Redpanda) → Consumer micro-batch → Bronze Parquet
- **Transforms SQL** : dbt-duckdb (staging → marts)
- **Exposition** : FastAPI (35+ endpoints, cache Redis, metriques Prometheus) + Streamlit (32 pages)
- **Deploiement** : Docker Compose multi-profils (full, streaming, monitoring, airflow, benchmarks)
- **Monitoring** : Prometheus + Grafana + alertes

### 4.2 Risques identifies

| Risque | Probabilite | Impact | Mitigation |
|--------|-------------|--------|------------|
| API Binance indisponible | Faible | Moyen | Retry avec backoff exponentiel + cache local Parquet |
| Volume de donnees croissant | Faible | Faible | DuckDB scale bien en lecture ; Delta Lake compaction ; partitionnement par symbole |
| Competences equipe | Faible | Moyen | Documentation technique complete (ADR, runbook, rapport) |
| Latence streaming Kafka | Moyenne | Moyen | Micro-batch (pas unitaire) ; Redpanda (plus leger que Kafka JVM) |
| Derive des donnees (schema drift) | Moyenne | Eleve | Validation PyArrow a l'ingestion ; tests dbt ; module validation.py (bronze/silver/gold) |

### 4.3 Conclusions et prochaines etapes

**Faisabilite validee** : le projet est techniquement et economiquement realisable avec les moyens identifies.

1. **Contexte** : CryptoInvest SA necessite une infrastructure data pour optimiser l'allocation de portefeuille sur 84 actifs (crypto + traditionnels)
2. **Objectifs** : Pipeline ETL 6 sources, Data Lake structure, 6 strategies d'optimisation, backtesting, dashboard 32 pages, API REST
3. **Opportunites** : Stack 100% open-source, architecture locale, equipe competente, donnees publiques (pas de contrainte PII)
4. **Faisabilite** : Technologies maitrisees, architecture Docker containerisee, pas de dependance cloud, budget minimal
5. **Priorites (RICE)** : Optimisation (50.0) > API (45.0) > Pipeline (41.7) > Backtesting (40.0) > Dashboard (33.3) > DWH (32.0) > Streaming (16.0)

**Prochaines etapes :**
1. Valider le cadrage avec le commanditaire (Product Owner)
2. Cartographier les donnees disponibles (cf. `02_cartographie_donnees.md`)
3. Definir l'architecture technique detaillee (cf. `03_cadre_technique.md`)
4. Lancer le sprint 1 (ingestion + stockage)
