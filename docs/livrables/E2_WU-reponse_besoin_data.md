# E2 — Réponse à un besoin data

**Modalité d’évaluation :** E2  
**Compétences évaluées :** C1, C2, C3, C4, C6  
**Nature :** Mise en situation

## Objet de l’épreuve

Dans cette épreuve, je présente une réponse complète à un besoin data réel ou simulé. Je montre comment j’ai transformé une demande métier en dispositif cohérent de collecte, de cartographie, d’architecture, de veille et de supervision.

## 1. Besoin reformulé et cible fonctionnelle

À partir des entretiens menés, je reformule le besoin comme suit :

Je dois fournir une plateforme capable de collecter des données de marché issues de six sources, de les structurer dans un Data Lake, de les transformer en métriques financières, de les exploiter dans un entrepôt analytique, puis de restituer les résultats à travers une API et un tableau de bord.

Le système rend les services suivants :
- collecte multi-sources ;
- stockage en zones Bronze, Silver et Gold ;
- transformations financières : rendements, volatilité, corrélation, covariance ;
- entrepôt de données en schéma en étoile ;
- optimisation de portefeuille selon six stratégies ;
- backtesting, Monte Carlo, drawdown et attribution ;
- exposition par API REST et dashboard ;
- streaming temps réel via Kafka / Redpanda ;
- orchestration Airflow ;
- observabilité via Prometheus et Grafana.

Les contraintes fortes qui ont guidé ma réponse sont :

| Contrainte | Conséquence sur la réponse                 |
|------------|--------------------------------------------|
| budget limité | choix exclusif d’outils open source        |
| absence de cloud | déploiement local via Docker Compose       |
| équipe réduite | architecture modulaire, simple à maintenir |
| données publiques uniquement | pas de PII, mais gouvernance et traçabilité maintenues |
| volumétrie modérée | DuckDB, PyArrow et PySpark local suffisent |

## 2. Cartographie des données disponibles

J’ai construit la topographie des données en partant des sources, des formats, des accès et des usages.
Ci-dessous un résumé concis dont vous trouverez les détails dans le document annexe en cliquant sur le lien ci-joint. [_lien vers cartoggraphie des données_](../annexes/rapport/02_cartographie_donnees.md) (section 1. Inventaire des sources)

### 2.1 Sources retenues

| Source | Type | Format | Fréquence | Usage principal |
|--------|------|--------|-----------|-----------------|
| Binance API | API REST publique | JSON | quotidien + temps réel | OHLCV crypto, prix live, métadonnées |
| yfinance | bibliothèque / API | DataFrame converti en dict | quotidien | actions, ETF, obligations, matières premières |
| CSV de référence | fichier structuré | CSV | statique | métadonnées de symboles |
| JSON de configuration | fichier semi-structuré | JSON | statique | contraintes et paramètres de portefeuille |
| CoinGecko | scraping web | HTML parsé | à la demande | enrichissement de contexte marché |
| PostgreSQL benchmarks | base relationnelle | SQL | à la demande | indices de référence et benchmarks |

### 2.2 Volumétrie et fréquence

- Binance : environ 1 530 enregistrements par lot sur 51 symboles et 30 jours ;
- yfinance : environ 990 enregistrements par lot sur 33 actifs et 30 jours ;
- CoinGecko : faible volumétrie, utilisé surtout pour l’enrichissement ;
- PostgreSQL benchmarks : volumétrie très faible ;
- fichiers CSV et JSON : données de référence statiques.

### 2.3 Sémantique métier

Les termes structurants du projet sont :
- **OHLCV** pour les données de chandeliers ;
- **kline** pour les bougies Binance ;
- **rendement**, **volatilité**, **corrélation** et **covariance** pour les mesures produites ;
- **frontière efficiente**, **Sharpe ratio**, **Risk Parity**, **HRP** et **Black-Litterman** pour les usages analytiques ;
- **Bronze / Silver / Gold** pour le cycle de vie des données.

### 2.4 Modèles de données

J’ai organisé les données selon quatre niveaux complémentaires :
- **Bronze** : données brutes par source et par symbole ;
- **Silver** : données transformées et normalisées ;
- **Gold** : résultats métier, poids optimaux, frontière efficiente, backtests ;
- **Data Warehouse** : schéma en étoile pour les requêtes analytiques.

Le schéma dimensionnel repose sur :
- `fact_prices` comme table de faits OHLCV ;
- `dim_symbol` comme dimension métier des actifs ;
- `dim_date` comme dimension temporelle ;
- des agrégats `agg_daily_returns` et `portfolio_summary` côté dbt.

## 3. Flux de données et traitements

J’ai décrit les flux de manière complète afin de démontrer la maîtrise de la chaîne de traitement.
[_lien vers cartoggraphie des données_](../annexes/rapport/02_cartographie_donnees.md) (section 5. Flux de donnees)

### 3.1 Pipeline batch crypto

Le flux batch crypto suit le chemin suivant :

Binance API → `ingest.py` → `data/raw/klines/` → `transform.py` → `data/processed/` → `optimize.py` / `backtest.py` → `data/output/` → API / dashboard / DuckDB.

### 3.2 Pipeline batch actifs traditionnels

Le flux traditionnel suit la même logique :

yfinance → `ingest_yfinance.py` → `data/raw/trad/` → `transform.py` → fichiers Silver traditionnels → optimisation et backtest → sortie JSON → exposition API.

### 3.3 Pipeline streaming

Le flux temps réel repose sur :

WebSocket Binance → producteur → Kafka / Redpanda → consommateur micro-batch → `data/streaming/klines/` et `data/streaming/orderbook/`.

### 3.4 Pipeline dbt

Les transformations SQL du Data Warehouse sont exécutées ainsi :

Parquet brut → modèles `stg_klines` et `stg_symbols` → modèles `fact_prices`, `dim_symbol`, `dim_date`, `agg_daily_returns`, `portfolio_summary` → matérialisation dans `warehouse.duckdb`.

### 3.5 Qualité des données

J’ai intégré des contrôles à chaque étage :
- Bronze : schéma OHLCV, prix positifs, cohérence open / high / low / close ;
- Silver : bornage des rendements, volatilité positive, symétrie des matrices ;
- Gold : somme des poids égale à 1, absence de poids négatifs, présence des sorties attendues.

## 4. Cadre technique d’exploitation

Ma réponse technique repose sur une architecture modulaire qui couvre à la fois la collecte, le stockage, l’analyse, l’exposition et l’exploitation.

### 4.1 Composants applicatifs
[_lien vers détails applicatifs_](../annexes/rapport/03_cadre_technique.md) (section 4.Représentation applicative)

| Composant | Technologie retenue | Rôle |
|-----------|---------------------|------|
| ingestion batch | Python + `httpx`, `yfinance`, `BeautifulSoup` | extraction multi-sources |
| ingestion streaming | WebSocket Binance + `kafka-python` | klines et carnet d’ordres en temps réel |
| transformation Python | PyArrow | calcul des métriques et sérialisation Parquet |
| transformation SQL | dbt-duckdb | staging, faits, dimensions, agrégats |
| stockage Lake | Parquet | Bronze, Silver, Gold |
| stockage ACID optionnel | Delta Lake via `delta-rs` | time travel et protection contre les écritures concurrentes |
| entrepôt | DuckDB | OLAP analytique en schéma en étoile |
| exposition | FastAPI + Pydantic | API REST documentée automatiquement |
| restitution | Streamlit + Plotly | tableau de bord d’analyse |
| orchestration | Airflow | DAG quotidien et exécutions planifiées |
| observabilité | Prometheus + Grafana | métriques, alertes, tableaux de bord |

### 4.2 Infrastructure
[_lien vers détails infrastructure_](../annexes/rapport/03_cadre_technique.md) (section 5. Representation d'infrastructure)
L’infrastructure s’appuie sur Docker Compose avec des profils dédiés :
- profil par défaut : API et dashboard ;
- profil `airflow` : webserver, scheduler et base de métadonnées ;
- profil `streaming` : Redpanda, producteur et consommateur ;
- profil `monitoring` : Prometheus et Grafana ;
- profils optionnels : Redis, MinIO, PostgreSQL benchmarks.

### 4.3 Besoins non fonctionnels

[_lien vers tableau des besoins non fonctionnels_](../annexes/rapport/03_cadre_technique.md) (section 2. Besoins non-fonctionnels)

J’ai également formalisé les exigences non fonctionnelles :
- performance : traitement rapide grâce à DuckDB, Parquet et PyArrow ;
- disponibilité : services Docker avec `restart: unless-stopped` et healthchecks ;
- maintenabilité : typage, tests, linting, ADR et documentation complète ;
- sécurité : secrets externalisés et absence de mots de passe versionnés ;
- portabilité : déploiement reproductible sur tout environnement supportant Docker.

## 5. Veille technologique et réglementaire

[_lien vers détails des veilles technologiques_](../annexes/rapport/04_veille.md)

J’ai organisé une veille hebdomadaire d’une heure, avec 30 minutes de lecture et 30 minutes de synthèse. Les thèmes suivis sont :
- data engineering ;
- écosystème Python ;
- DuckDB et OLAP ;
- RGPD et gouvernance des données ;
- streaming et event-driven ;
- dbt et qualité des données ;
- Delta Lake et approches lakehouse.

### 5.1 Méthode de qualification des sources

Chaque source de veille a été évaluée selon :
- auteur identifié ;
- expertise reconnue ;
- notoriété ;
- absence de conflit d’intérêt majeur ;
- publication récente ;
- structure et accessibilité du contenu ;
- possibilité de recouper l’information.

### 5.2 Sources effectivement retenues

- DuckDB Blog ;
- documentation FastAPI ;
- Apache Arrow Blog ;
- CNIL ;
- documentation dbt ;
- Delta Lake / `delta-rs` ;
- Redpanda ;
- documentation Astral pour `uv` et `ruff`.

### 5.3 Décisions issues de la veille

Les recommandations intégrées au projet sont les suivantes :
- adoption de la dernière version stable de DuckDB ;
- validation stricte des schémas et de l’API avec Pydantic ;
- ajout d’un healthcheck pour l’API ;
- intégration de Delta Lake en backend optionnel ;
- intégration de dbt-duckdb pour les transformations SQL ;
- déploiement d’un environnement de streaming léger avec Redpanda ;
- formalisation des mesures RGPD et de gouvernance.

## 6. Supervision de la réalisation

La réponse technique n’est pas seulement documentée : elle est pilotable et supervisable.

J’ai retenu les rituels suivants :
- daily stand-up ;
- [sprint planning](../annexes/business/meeting_notes/2025-01-20_sprint1_review.md) ;
- [sprint review](../annexes/business/user_stories.md) ;
- [rétrospective](../annexes/business/raci_matrix.md) ;
- point hebdomadaire de suivi de la certification.

Les indicateurs de suivi sont :
- avancement des phases ;
- jalons respectés ;
- nombre de tests passants ;
- qualité du code ;
- stabilité des services ;
- suivi des risques majeurs.

Les arbitrages techniques sont tous documentés dans les ADR (ci-dessous les liens pour vous y rendre aux fichiers de détails):
- [Parquet](../annexes/architecture/adr/001_storage_parquet.md);
- [DuckDB](../annexes/architecture/adr/002_duckdb_warehouse.md) ;
- [PyArrow](../annexes/architecture/adr/003_no_pandas.md) ;
- [FastAPI](../annexes/architecture/adr/004_fastapi_exposure.md) ;
- [Airflow](../annexes/architecture/adr/005_airflow_orchestration.md) ;
- [Delta Lake](../annexes/architecture/adr/006_delta_lake.md) ;
- [dbt-duckdb](../annexes/architecture/adr/007_dbt_transforms.md).

## 7. Conclusion

La réponse que j’apporte au besoin data est complète, cohérente et exploitable. J’ai articulé le cadrage du besoin, la cartographie des données, l’architecture, la veille et les mécanismes de supervision de manière à produire une solution techniquement réaliste, maintenable et conforme aux exigences du référentiel.
