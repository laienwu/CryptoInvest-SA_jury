# E1 — Grilles d’entretien

**Modalité d’évaluation :** E1  
**Compétence évaluée :** C1  
**Nature :** Étude de cas

## Objet de l’épreuve

Dans cette épreuve, je démontre ma capacité à analyser un besoin data, à conduire des entretiens avec les parties prenantes, à reformuler le besoin de manière exploitable et à conclure sur une recommandation de cadrage réaliste.

## Contexte du projet

L'organisation **CryptoInvest SA** est une societe de gestion d'actifs numeriques souhaitant optimiser ses strategies d'investissement en cryptomonnaies et en actifs traditionnels. Face a la volatilite du marche crypto et a la necessite de diversification multi-classes, la direction souhaite mettre en place une infrastructure data permettant d'analyser les donnees de marche, d'optimiser l'allocation de portefeuille et de fournir des outils de decision en temps reel.

> disposer d’un outil capable de collecter automatiquement les données de marché, de les analyser et de proposer des allocations optimales de portefeuille à partir de modèles comme Markowitz, Black-Litterman, HRP et Risk Parity.

Les enjeux stratégiques identifiés sont les suivants :
- améliorer le rendement ajusté au risque ;
- automatiser la collecte et le traitement des données ;
- pouvoir gérer un univers de 84 actifs, soit 51 actifs crypto et 33 actifs traditionnels ;
- assurer la traçabilité, la gouvernance et la conformité ;
- intégrer une capacité temps réel pour les usages les plus sensibles.

## Métiers impliqués

J’ai identifié cinq familles de parties prenantes directement concernées :

| Famille | Métier | Rôle dans le projet |
|---------|--------|---------------------|
| Sources / génération | Équipe trading | définit les actifs suivis, les fréquences et les indicateurs attendus |
| Sources / génération | Analystes quantitatifs | précisent les modèles d’optimisation et les métriques de risque |
| Collecte / stockage | Data Engineer | conçoit le pipeline ETL, le Data Lake et le Data Warehouse |
| Collecte / stockage | DevOps | déploie Docker, Airflow, Kafka, le monitoring et la sécurité |
| Exploitation / analyse | Équipe de gestion et direction | consomment les tableaux de bord, suivent les KPI et valident les arbitrages |

## Entretiens conduits

J’ai structuré l’analyse du besoin autour de trois entretiens principaux, dont je vous résume les points essentiels ci-dessous.

[Lien vers les grilles des entretien détaillées ](../annexes/rapport/01_analyse_besoin.md) (section 2. grilles d'entretiens)


### Entretien Direction générale

| Question | Réponse |
|----------|-----------------|
| Quels sont les objectifs business du projet ? | Optimiser l’allocation de portefeuille pour maximiser le couple rendement / risque |
| Quel est le budget alloué ? | Budget limité, priorité aux solutions open source |
| Quels sont les délais attendus ? | MVP en trois mois |
| Qui sont les utilisateurs finaux ? | Équipe de gestion et analystes quantitatifs |

### Entretien Équipe trading

| Question | Réponse |
|----------|-----------------|
| Quelles données sont utilisées aujourd’hui ? | Prix OHLCV récupérés manuellement sur Binance |
| Quelle fréquence de mise à jour est nécessaire ? | Quotidienne pour le batch, temps réel pour certains flux |
| Quels actifs sont suivis ? | 51 cryptomonnaies et 33 actifs traditionnels |
| Quels indicateurs sont attendus ? | Rendements, volatilité, corrélations, ainsi que des signaux comme SMA, RSI, MACD et Bollinger |

### Entretien IT / Infrastructure

| Question | Réponse                                                                                                                  |
|----------|--------------------------------------------------------------------------------------------------------------------------|
| Quelle infrastructure existe déjà ? | Serveurs Linux, on premise pour le MVP, ensuite migration sur cloud                                                      |
| Quelles sont les contraintes techniques ? | Base de donnée légère pour MVP, en suite migration sur Postgres/MongoDB ; PostgreSQL reste optionnel pour les benchmarks |
| Quelles sont les compétences disponibles ? | Python, SQL, Docker, Kafka                                                                                               |
| Quelles sont les exigences de sécurité ? | Données publiques, pas de données personnelles, mais exigence de gouvernance et de traçabilité                           |

## Reformulation du besoin

À l’issue des entretiens, j’ai reformulé le besoin de la façon suivante :

Je dois mettre en place une infrastructure data complète permettant de :
1. collecter automatiquement des données de marché depuis six sources hétérogènes ;
2. stocker les données dans un Data Lake structuré en zones Bronze, Silver et Gold ;
3. calculer des métriques financières fiables à partir des données brutes ;
4. alimenter un entrepôt de données analytique en schéma en étoile ;
5. exécuter plusieurs stratégies d’optimisation de portefeuille ;
6. exposer les résultats via une API REST et un tableau de bord exploitable ;
7. superviser l’ensemble avec orchestration, monitoring et traçabilité.

## Périmètre retenu

J’ai distingué clairement ce qui entre dans le périmètre et ce qui en est exclu.

| Inclus                                                                  | Exclus |
|-------------------------------------------------------------------------|--------|
| collecte multi-sources : API, CSV, JSON, scraping, PostgreSQL, yfinance | exécution automatique d’ordres de trading |
| ingestion streaming via WebSocket Binance et Kafka / Redpanda           | architecture multi-tenant |
| Data Lake Parquet avec Delta Lake optionnel                             | moteur de prédiction par machine learning |
| Data Warehouse DuckDB avec transformations dbt                          | |
| multiple stratégies d’optimisation                                     | |
| moteur de backtesting walk-forward                                      | |
| API REST FastAPI et tableau de bord Streamlit                           | |
| orchestration Airflow et monitoring Prometheus / Grafana                | |

## Moyens mobilisables

Les moyens à ma disposition sont cohérents avec le besoin :

### Moyens humains

| Rôle | Responsabilités principales |
|------|-----------------------------|
| Product Owner | priorisation, validation métier |
| Business Analyst | expression des besoins, documentation, comptes-rendus |
| Data Engineer | architecture, pipeline ETL, API, dossier technique |
| Data Analyst | validation des métriques financières |
| DevOps | infrastructure Docker, monitoring, sécurité, SLA |
| Scrum Master | animation des cérémonies et suivi |

### Moyens techniques

- Python 3.13+, PyArrow, DuckDB, FastAPI, Streamlit, Airflow et Redpanda ;
- Docker Compose avec profils d’exécution ;
- Git, CI/CD, linting, type checking et tests automatisés.

### Moyens financiers

Le projet est conçu avec une logique **100 % open source**, sans coût de licence ni dépendance à un cloud payant.

## Priorisation et objectifs

### Analyse RICE

J’ai priorisé les grandes briques fonctionnelles de la manière suivante :

| Fonctionnalité | Reach | Impact | Confidence | Effort | Score |
|----------------|-------|--------|------------|--------|-------|
| Optimisation multi-stratégies | 5 | 5 | 4 | 2 | 50,0 |
| API REST | 3 | 3 | 5 | 1 | 45,0 |
| Pipeline ETL multi-sources | 5 | 5 | 5 | 3 | 41,7 |
| Backtesting walk-forward | 4 | 5 | 4 | 2 | 40,0 |
| Dashboard Streamlit | 5 | 4 | 5 | 3 | 33,3 |
| Data Warehouse | 4 | 4 | 4 | 2 | 32,0 |
| Streaming Kafka | 3 | 4 | 4 | 3 | 16,0 |

Cette analyse me conduit à traiter d’abord la valeur métier immédiate : l’optimisation, l’API, puis la robustesse du pipeline.

### Objectifs SMART

- **Spécifique** : construire un pipeline collectant six types de sources et les transformant en métriques financières exploitables ;
- **Mesurable** : traiter 51 cryptomonnaies et 33 actifs traditionnels, exposer les résultats et livrer un tableau de bord multi-pages ;
- **Atteignable** : m’appuyer sur une stack que l’équipe maîtrise déjà ;
- **Réaliste** : déployer localement via Docker Compose, sans infrastructure cloud ;
- **Temporel** : livrer un MVP fonctionnel en trois mois.

## Éco-responsabilité et accessibilité

Dès l’expression du besoin, j’ai intégré deux dimensions transverses.

### Éco-responsabilité

- choix de DuckDB pour éviter un SGBD serveur plus lourd ;
- usage de Parquet compressé pour réduire le volume de stockage ;
- usage de PyArrow pour limiter l’empreinte mémoire ;
- planification Airflow pour éviter les traitements inutiles ;
- limitation de la rétention des métriques de supervision.

### Accessibilité

- hiérarchie de titres structurée dans toute la documentation ;
- messages explicites dans l’API ;
- visualisations Streamlit accompagnées de libellés et de légendes ;
- supports de soutenance pensés avec contraste suffisant et lecture lisible.

## Étude de faisabilité

La solution que je recommande est une architecture légère **Data Lake + Data Warehouse** :
- stockage en Parquet, avec Delta Lake optionnel pour les garanties ACID ;
- pipeline batch orchestré par Airflow ;
- pipeline streaming via WebSocket Binance puis Kafka / Redpanda ;
- transformations Python et SQL avec dbt-duckdb ;
- exposition via FastAPI et Streamlit ;
- monitoring avec Prometheus et Grafana.

Les principaux risques identifiés sont :

| Risque | Impact         | Réponse prévue |
|--------|----------------|----------------|
| indisponibilité de Binance | critique       | retry, backoff, cache Parquet local |
| dérive de schéma | élevé          | validation à l’ingestion et tests dbt |
| croissance des volumes | faible à moyen | partitionnement, Delta Lake, requêtes DuckDB |
| latence du streaming | moyen          | micro-batch et architecture Redpanda légère |

## Conclusion

Je conclus que le projet est **faisable techniquement et économiquement** avec les moyens identifiés. Le besoin est suffisamment clair, le périmètre est maîtrisé, la pile technologique est cohérente avec les contraintes, et la trajectoire de réalisation est crédible. Mon cadrage aboutit donc à une recommandation positive de lancement du projet.
