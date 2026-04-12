# E7 — Mise en condition ops d’un Data Lake

**Modalité d’évaluation :** E7  
**Compétences évaluées :** C18, C19, C20, C21  
**Nature :** Mise en situation

## Objet de l’épreuve

Dans cette épreuve, je démontre ma capacité à concevoir un Data Lake, à intégrer ses composants techniques, à en assurer l’exploitation opérationnelle, à cataloguer les données et à formaliser la gouvernance associée.

## 1. Architecture du Data Lake

J’ai structuré le Data Lake selon une logique de zones clairement séparées :

| Zone | Contenu | Finalité |
|------|---------|----------|
| Bronze batch | données brutes crypto et traditionnelles | conserver l’état source |
| Bronze streaming | klines et order book temps réel | capter le temps réel |
| Silver | données transformées | préparer l’analyse |
| Gold | résultats métier | fournir les sorties directement exploitables |
| Reference | métadonnées et configuration | stabiliser les paramètres de calcul |
| DWH | warehouse DuckDB | supporter l’analyse SQL |

La structure physique comprend :
- `data/raw/klines/` pour les actifs crypto ;
- `data/raw/trad/` pour les actifs traditionnels ;
- `data/streaming/` pour les flux temps réel ;
- `data/processed/` pour les sorties Silver ;
- `data/output/` pour les sorties Gold ;
- `data/reference/` pour les référentiels ;
- `data/warehouse.duckdb` pour la couche analytique.

La structure se représente sous cette vue d'arborescence de projet, dont l'annexe [catalogue de données](../annexes/rapport/09_catalogue_donnees.md) donne des détails supplémentaire
```
data/
├── raw/                    # BRONZE — Donnees brutes
│   ├── klines/             #   51 fichiers crypto (BTCUSDT.parquet, ...)
│   └── trad/               #   33 fichiers traditionnels (SPY.parquet, ...)
├── streaming/              # BRONZE — Donnees temps reel
│   ├── klines/             #   Klines via Kafka (micro-batch)
│   └── orderbook/          #   Carnet d'ordres via Kafka
├── processed/              # SILVER — Donnees transformees
│   ├── returns.parquet     #   Rendements crypto
│   ├── volatility.parquet
│   ├── mean_returns.parquet
│   ├── correlation.parquet
│   ├── covariance.parquet
│   ├── returns_trad.parquet     # Rendements trad
│   ├── volatility_trad.parquet
│   ├── mean_returns_trad.parquet
│   ├── correlation_trad.parquet
│   └── covariance_trad.parquet
├── output/                 # GOLD — Resultats metier
│   ├── weights.json        #   Allocation crypto
│   ├── frontier.json       #   Frontiere efficiente crypto
│   ├── backtest.json       #   Backtesting crypto
│   ├── weights_trad.json   #   Allocation trad
│   ├── frontier_trad.json  #   Frontiere efficiente trad
│   └── backtest_trad.json  #   Backtesting trad
├── reference/              # REFERENCE — Donnees statiques
│   ├── symbols_metadata.csv
│   └── portfolio_config.json
└── warehouse.duckdb        # DWH — Star schema (DuckDB)

dbt_project/target/         # DBT — Modeles compiles et materialises

```
## 2. Choix techniques d’architecture

Les décisions majeures prises pour le Data Lake sont :
- [**Parquet**](../annexes/architecture/adr/001_storage_parquet.md)comme format principal, pour son caractère colonnaire, compressé et standard ;;
- [**DuckDB**](../annexes/architecture/adr/002_duckdb_warehouse.md) comme entrepôt analytique associé ;
- [**Delta Lake**](../annexes/architecture/adr/006_delta_lake.md) comme option de stockage ACID pour les cas nécessitant time travel et protection contre les écritures concurrentes ;
- **MinIO** comme backend objet optionnel compatible S3 ;
- **Docker Compose** pour la portabilité et la reproductibilité ;
- **Redpanda** pour le streaming léger compatible Kafka.

Ces choix permettent d’obtenir une architecture à la fois :
- sobre ;
- portable ;
- modulaire ;
- suffisamment évolutive pour le périmètre du projet.

## 3. Intégration des composants

L’intégration des composants repose sur une chaîne cohérente :
- producteurs d’ingestion batch ;
- producteurs et consommateurs streaming ;
- stockage fichier dans le Data Lake ;
- transformations Python et SQL ;
- orchestration Airflow ;
- exposition API et dashboard ;
- monitoring et observabilité.

Les profils Docker permettent de n’activer que les composants nécessaires :
- profil `airflow` pour l’orchestration ;
- profil `streaming` pour Kafka / Redpanda ;
- profil `monitoring` pour Prometheus et Grafana ;
- profils optionnels pour Redis, MinIO et PostgreSQL benchmarks.

Cette organisation facilite :
- la mise en route progressive de la plateforme ;
- les tests ciblés ;
- la maintenance ;
- la démonstration devant le jury.

Ces élments sont détaillés dont [le rapport cadre technique](../annexes/rapport/03_cadre_technique.md) dont le graphe ci-dessous est un aperçu:
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Docker Host                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─── Defaut (pas de profil) ───────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  ┌──────────────────┐       ┌──────────────────┐                     │    │
│  │  │  api (FastAPI)   │◀───── │  streamlit       │                     │    │
│  │  │  Port 8000       │       │  Port 8501       │                     │    │
│  │  │  healthcheck     │       │  healthcheck     │                     │    │
│  │  └──────────────────┘       └──────────────────┘                     │    │
│  │                                                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─── Profil: pipeline ──────┐   ┌─── Profil: airflow ─────────────────┐     │
│  │                           │   │                                     │     │
│  │  ┌─────────────────────┐  │   │  ┌────────────────┐  ┌────────────┐ │     │
│  │  │  pipeline (one-shot)│  │   │  │ airflow-       │  │ airflow-   │ │     │
│  │  │  bootstrap.py       │  │   │  │ webserver      │  │ scheduler  │ │     │
│  │  └─────────────────────┘  │   │  │ Port 8081      │  │            │ │     │
│  │                           │   │  └───────┬────────┘  └─────┬──────┘ │     │
│  └───────────────────────────┘   │          │                 │        │     │
│                                  │          └────────┬────────┘        │     │
│                                  │                   ▼                 │     │
│                                  │         ┌────────────────┐          │     │
│                                  │         │ postgres       │          │     │
│                                  │         │ (metadata)     │          │     │
│                                  │         │ Port 5432      │          │     │
│                                  │         └────────────────┘          │     │
│                                  └─────────────────────────────────────┘     │
│                                                                              │
│  ┌─── Profil: streaming ────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │    │
│  │  │ redpanda     │  │ stream-      │  │ stream-      │                │    │
│  │  │ (Kafka)      │  │ producer     │  │ consumer     │                │    │
│  │  │ Port 19092   │  │              │  │              │                │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                │    │
│  │  ┌──────────────┐                                                    │    │
│  │  │ redpanda-    │                                                    │    │
│  │  │ console      │                                                    │    │
│  │  │ Port 8080    │                                                    │    │
│  │  └──────────────┘                                                    │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─── Profil: monitoring ──────────────┐   ┌─── Profils optionnels ─────┐    │
│  │                                     │   │                            │    │
│  │  ┌──────────────┐  ┌──────────────┐ │   │  ┌─────────────────────┐   │    │
│  │  │ prometheus   │  │ grafana      │ │   │  │ redis (cache)       │   │    │
│  │  │ Port 9090    │──│ Port 3000    │ │   │  │ Port 6379           │   │    │
│  │  └──────────────┘  └──────────────┘ │   │  ├─────────────────────┤   │    │
│  │                                     │   │  │ minio (S3)          │   │    │
│  └─────────────────────────────────────┘   │  │ Port 9000/9001      │   │    │
│                                            │  ├─────────────────────┤   │    │
│  ┌─── Profil: benchmarks ──────────────┐   │  │ postgres-benchmarks │   │    │
│  │  ┌──────────────────────────────┐   │   │  │ Port 5433           │   │    │
│  │  │ postgres-benchmarks          │   │   │  └─────────────────────┘   │    │
│  │  │ Port 5433                    │   │   │                            │    │
│  │  └──────────────────────────────┘   │   └────────────────────────────┘    │
│  └─────────────────────────────────────┘                                     │
│                                                                              │
│  ┌─── Volumes partages ─────────────────────────────────────────────────┐    │
│  │  ./data/          (Bronze, Silver, Gold, warehouse.duckdb)           │    │
│  │  ./src/           (code source pipeline)                             │    │
│  │  ./config.toml    (configuration centralisee)                        │    │
│  │  ./dags/          (DAG Airflow)                                      │    │
│  │  ./dbt_project/   (modeles dbt)                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 4. Catalogue de données

Vous trouverez mon rapport détaillé de la cartographie des données au lien ci-après: [lien](../annexes/rapport/02_cartographie_donnees.md)

```
                               DATA SOURCES
     +---------------+  +---------------+  +---------------+
     | Binance REST  |  | Binance WS    |  |   yfinance    |
     +---------------+  +---------------+  +---------------+
             |                 |                  |
             |                 |                  |
             +--------+--------+--------+---------+
                      |
                      v

==============================================================
                          BRONZE LAYER
==============================================================

                data/raw/ (Parquet + Delta Lake)

     Crypto datasets (51 files)       Traditional datasets (33 files)
     +---------------------------+    +---------------------------+
     | klines/                   |    | yfinance/                 |
     | streaming/klines/         |    | benchmarks/               |
     | streaming/orderbook/      |    | scraping/                 |
     +---------------------------+    +---------------------------+

                           |
                           | Python ingestion
                           v

==============================================================
                          SILVER LAYER
==============================================================

                data/processed/

        +-------------------------------------------+
        | Derived datasets                          |
        |                                           |
        | - returns                                 |
        | - volatility                              |
        | - correlation                             |
        | - covariance                              |
        +-------------------------------------------+

                           |
                           | portfolio optimisation
                           v

==============================================================
                           GOLD LAYER
==============================================================

                     data/output/

        +-------------------------------------------+
        | Portfolio analytics                       |
        |                                           |
        | - weights                                 |
        | - efficient frontier                      |
        | - backtests                               |
        | - Monte Carlo simulations                 |
        | - stress tests                            |
        +-------------------------------------------+

                           |
                           v

==============================================================
                     DATA WAREHOUSE (DWH)
==============================================================

                       DuckDB + dbt

            +-----------------------------------+
            | fact_prices                       |
            | dim_symbol                        |
            | dim_date                          |
            | agg_daily_returns                 |
            | portfolio_summary                 |
            +-----------------------------------+

                           |
                           v

==============================================================
                         SERVING LAYER
==============================================================

        +-------------------------------------------+
        | FastAPI (45 endpoints)                    |
        | Streamlit (32 pages)                      |
        | Grafana dashboards                        |
        +-------------------------------------------+

```
---

J’ai produit un catalogue de données complet couvrant :
- les jeux de données Bronze ;
- les jeux de données Silver ;
- les jeux de données Gold ;
- les données de référence ;
- les tables et vues du Data Warehouse ;
- le lignage, la rétention, la qualité et les modes d’accès.

### 4.1 Vue d’ensemble

```
+-------------------+--------------------------------------+
| Layer             | Datasets                             |
+-------------------+--------------------------------------+
| Bronze            | 51 crypto datasets                   |
|                   | 33 traditional market datasets       |
|                   | streaming klines and orderbooks      |
+-------------------+--------------------------------------+
| Silver            | returns, volatility, correlation     |
|                   | covariance                           |
+-------------------+--------------------------------------+
| Gold              | portfolio weights                    |
|                   | efficient frontier                   |
|                   | backtests                            |
+-------------------+--------------------------------------+
| Data Warehouse    | fact tables, dimensions, aggregates  |
+-------------------+--------------------------------------+
```

Le catalogue recense :
- 51 fichiers Bronze crypto ;
- 33 fichiers Bronze traditionnels ;
- des flux streaming pour les klines et les carnets d’ordres ;
- des jeux Silver de rendements, volatilité, corrélation et covariance ;
- des sorties Gold de poids, frontière efficiente et backtests ;
- un DWH DuckDB avec faits, dimensions et agrégats.

### 4.2 Métadonnées recensées

Pour chaque dataset, je documente :
- identifiant ;
- localisation ;
- format ;
- source ;
- fréquence d’alimentation ;
- propriétaire ;
- classification ;
- schéma ;
- volumétrie ;
- politique de rétention.

### 4.3 Lignage
```
Sources
   │
   ▼
Bronze datasets
   │
   ▼
Python transformations
   │
   ▼
Silver datasets
   │
   ▼
Optimisation & backtesting
   │
   ▼
Gold datasets
   │
   ▼
dbt models → DuckDB Data Warehouse
   │
   ▼
API / Dashboards / Analytics
```

Le lignage est explicite :
- les sources alimentent la Bronze ;
- les traitements Python alimentent la Silver ;
- l’optimisation et le backtesting alimentent la Gold ;
- dbt matérialise le DWH ;
- l’API et le dashboard consomment le lake et le warehouse.

## 5. Cycle de vie des données

J’ai défini des règles de rétention adaptées à chaque zone (pour les données MVP) :
(à prendre en considération le réglementaire (AMF), la rétention policy de l'entreprise est de 10 ans pour toutes les données fiancières et extra-financières une fois en production)

| Zone | Rétention |
|------|-----------|
| Bronze batch | 365 jours |
| Bronze streaming | 30 jours |
| Silver | 365 jours |
| Gold | 30 jours |
| Reference | permanente |
| DWH | permanent, mais reconstructible |

La suppression s’appuie sur une logique automatisée :
- filtrage ou purge des données trop anciennes ;
- écrasement des sorties Gold lors des nouvelles exécutions ;
- reconstruction du warehouse après purge si nécessaire.

Cette politique traduit un principe de limitation du stockage, même en l’absence de données personnelles.

## 6. Qualité et monitoring

Ci-joint le [rapport complet du monitoring](../annexes/operations/monitoring.md) 
dont le graphee ci-dessous résume l'architecture de l'ensembles de process de surveillance mis en place:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MONITORING STACK                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐        │
│  │   Services    │──▶│   Metrics     │───▶│   Alerting    │        │
│  │               │    │   Collector   │    │               │        │
│  │ • API         │    │               │    │ • Email       │        │
│  │ • Airflow     │    │ • Health      │    │ • Slack       │        │
│  │ • Pipeline    │    │ • Logs        │    │               │        │
│  └───────────────┘    └───────────────┘    └───────────────┘        │
│                              │                                      │
│                              ▼                                      │
│                    ┌───────────────────┐                            │
│                    │    Dashboard      │                            │
│                    │                   │                            │
│                    │ • Airflow UI      │                            │
│                    │ • Docker stats    │                            │
│                    │ • Custom scripts  │                            │
│                    └───────────────────┘                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```
J’ai intégré des règles de qualité directement au catalogue :
- complétude des colonnes Bronze ;
- positivité des prix ;
- cohérence du schéma OHLCV ;
- absence de valeurs nulles en Silver ;
- symétrie des matrices ;
- poids Gold sommant à 1 ;
- volumes positifs dans le DWH.

Le monitoring associé suit notamment :
- le nombre d’enregistrements ingérés ;
- la taille du répertoire `data/` ;
- la fraîcheur des données ;
- les erreurs d’ingestion ;
- la latence API ;
- le taux d’erreur API ;
- l’état des tests dbt.

## 7. Gouvernance et RGPD

Le projet ne traite pas de données personnelles. Les données manipulées sont des données publiques de marché : prix, volumes, timestamps, symboles, métriques calculées.

Par conséquent :
- le RGPD ne s’applique pas directement au périmètre actuel ;
- aucune PII n’est collectée ;
- aucune personne physique n’est identifiable.

Je mets néanmoins en œuvre une gouvernance préventive.

### 7.1 Principes appliqués

- minimisation des données ;
- transparence sur les sources ;
- traçabilité par logs et historique Git ;
- séparation des accès par groupes ;
- documentation des traitements et des durées de conservation.

### 7.2 Gouvernance des accès

Les accès sont organisés par groupes et non par individus :

| Groupe | Rôle |
|--------|------|
| Admin | administration, maintenance, déploiement |
| Analyst | consultation et analyse |
| Application | accès programmatique pour les services |

La matrice d’accès suit le principe du moindre privilège :
- Bronze en écriture pour l’ingestion, pas pour les analystes ;
- Silver et Gold en lecture pour les analystes ;
- Data Engineer en lecture / écriture ;
- services applicatifs limités à leurs besoins effectifs.

### 7.3 Mesures préventives

Même sans PII, j’ai documenté :
- un registre préventif des traitements ;
- une politique de rétention et de purge ;
- des procédures types de suppression et d’export si le périmètre évolue ;
- des recommandations de sécurité pour une future mise en production avec authentification et chiffrement renforcé.

## 8. Sécurité opérationnelle
[lien vers le rapports des mesures des sécurités opérationnelles](../annexes/operations/security_checklist.md)

Les mesures techniques et organisationnelles retenues sont les suivantes :
- isolation par conteneurs Docker ;
- secrets externalisés dans l’environnement ;
- absence de mots de passe en dur dans le code ;
- journalisation et traçabilité ;
- revue de code et CI/CD ;
- contrôles d’accès logiques selon les rôles ;
- limitation d’exposition réseau.

## Conclusion

Le Data Lake que je mets en condition opérationnelle est plus qu’un espace de stockage. C’est un système organisé, intégré, supervisé, catalogué et gouverné. J’y démontre la maîtrise de l’architecture, des composants, du cycle de vie des données, de la qualité, des accès et de la gouvernance, conformément aux attentes de l’épreuve E7.
