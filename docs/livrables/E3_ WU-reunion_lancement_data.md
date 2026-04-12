# E3 — Réunion de lancement de projet data

**Modalité d’évaluation :** E3  
**Compétences évaluées :** C5, C6, C7  
**Nature :** Jeu de rôle

## Ouverture de la réunion

Bonjour à toutes et à tous. Je vous remercie de votre présence pour la réunion de lancement du projet de plateforme d’optimisation de portefeuille. L’objectif de cette réunion est de partager le cadre du projet, de valider l’organisation retenue, de présenter la feuille de route, puis de préciser les modalités de suivi et de communication.

Le projet vise à mettre en place une plateforme capable de collecter automatiquement les données de marché, de calculer des métriques financières, de produire des allocations optimales de portefeuille et de restituer les résultats à travers une API et un tableau de bord.

[Notes de réunions pour du kickoff](../annexes/business/meeting_notes/2025-01-06_kickoff.md)
## 1. Équipe projet et responsabilités

L’équipe projet est composée des rôles suivants :

| Rôle | Responsabilités principales |
|------|-----------------------------|
| Product Owner | validation métier, priorisation, critères d’acceptation |
| Business Analyst | expression des besoins, documentation et comptes-rendus |
| Data Engineer | architecture, développement du pipeline, API, dossier technique |
| Data Analyst | validation des métriques et contrôle de cohérence |
| DevOps | infrastructure Docker, monitoring, sécurité, SLA |
| Scrum Master | animation des cérémonies, suivi d’avancement, facilitation |

La répartition des responsabilités suit une logique RACI claire :
- le Data Engineer porte l’architecture et le développement ;
- le Product Owner valide les choix métier ;
- le Business Analyst formalise les exigences ;
- la Data Analyste vérifie la pertinence des métriques ;
- le DevOps encadre les aspects d’exploitation ;
- le Scrum Master structure le pilotage du projet.

## 2. Budget et moyens

Le projet est construit avec une logique de sobriété :
- stack 100 % open source ;
- déploiement local via Docker ;
- absence de coût d’infrastructure cloud ;
- absence de licences logicielles payantes.

Dans le cadre de la certification, le coût réel est nul. En équivalent professionnel, l’effort représenterait principalement du temps d’ingénierie et d’infrastructure.

## 3. Feuille de route

J’ai structuré le projet en huit phases.

[Lien vers le rapport détailé de la planification](../annexes/rapport/05_planification.md)

### Phase 1 — Fondations

- initialisation de l’environnement ;
- mise en place du pattern de stockage ;
- ingestion des six sources ;
- configuration centralisée.

### Phase 2 — Transformation

- calcul des rendements ;
- calcul de la volatilité, de la corrélation et de la covariance ;
- tests unitaires des premières transformations.

### Phase 3 — Analytics et Data Warehouse

- construction du schéma en étoile ;
- mise en place de DuckDB ;
- intégration de dbt-duckdb ;
- premières requêtes analytiques SQL.

### Phase 4 — Exposition

- API FastAPI ;
- tableau de bord Streamlit ;
- packaging Docker ;
- première orchestration via Airflow.

### Phase 5 — Optimisation avancée

- six stratégies d’optimisation ;
- moteur de backtesting walk-forward ;
- Monte Carlo, stress tests, drawdown, attribution ;
- signaux de trading et analyses avancées.

### Phase 6 — Streaming et Big Data

- WebSocket Binance ;
- Kafka / Redpanda ;
- consommation micro-batch ;
- Delta Lake optionnel.

### Phase 7 — Monitoring et observabilité

- Prometheus ;
- Grafana ;
- alertes ;
- métriques métier.

### Phase 8 — Finalisation

- documentation complète ;
- préparation de la soutenance ;
- démonstration de bout en bout.

## 4. Jalons de validation

| Jalon | Livrable attendu | Critère de validation |
|-------|------------------|-----------------------|
| J1 | pipeline d’ingestion | six sources ingérées et données en zone brute |
| J2 | métriques calculées | rendements, volatilité et corrélations disponibles |
| J3 | DWH opérationnel | schéma en étoile et modèles dbt fonctionnels |
| J4 | API et dashboard | restitution exploitable et documentation API |
| J5 | analytics avancées | stratégies d’optimisation et backtests disponibles |
| J6 | streaming | flux temps réel opérationnels |
| J7 | monitoring | tableaux de bord et alertes actifs |
| J8 | livraison finale | dossier, démonstration et soutenance prêts |

Le chemin critique est le suivant : ingestion, transformation, DWH, exposition, optimisation, finalisation. Tout retard sur ces briques impacte directement la date de livraison.

## 5. Méthode de suivi

Le pilotage du projet repose sur des rituels simples et réguliers :

| Rituel | Fréquence | Objectif |
|--------|-----------|----------|
| Daily stand-up | quotidien | partager l’avancement et remonter les blocages |
| Sprint planning | début de sprint | planifier et estimer les tâches |
| Sprint review | toutes les deux semaines | démontrer les livrables et recueillir la validation |
| Rétrospective | toutes les deux semaines | améliorer l’organisation et les pratiques |
| Point formateur | hebdomadaire | suivre l’avancement du dossier de certification |

Les indicateurs suivis à chaque fin de sprint sont :
- taux d’achèvement des tâches ;
- respect des jalons ;
- nombre de tests passants ;
- qualité du code ;
- incidents et risques ouverts.

## 6. Supervision et arbitrages

J’assure la supervision technique à travers :
- le suivi des indicateurs projet ;
- la documentation systématique des décisions dans les ADR ;
- l’actualisation du registre des risques ;
- le suivi budgétaire ;
- la consolidation de la documentation.

Les principaux arbitrages techniques déjà actés sont :
- Parquet pour le stockage des données du lake ;
- DuckDB pour l’entrepôt analytique ;
- PyArrow pour les transformations mémoire ;
- FastAPI pour l’exposition ;
- Airflow pour l’orchestration ;
- Delta Lake comme option ACID ;
- dbt-duckdb pour les transformations SQL et le lineage.

## 7. Communication projet

La communication est organisée à chaque étape clé :
[lien vers le rapport détaillé sur l'organisation de la communication du project](../annexes/rapport/06_communication.md)

| Moment | Cible | Support |
|--------|------|---------|
| lancement | équipe projet et parties prenantes | réunion de cadrage et support de lancement |
| sprint review | PO, équipe, formateur | démonstration et compte-rendu |
| jalons techniques | parties prenantes concernées | note de synthèse et présentation |
| livraison | jury | rapport professionnel, démonstration, soutenance |

Je veille à ce que les supports soient :
- lisibles ;
- structurés ;
- compréhensibles pour un public non technique et technique ;
- compatibles avec les principes d’accessibilité documentaire.

## 8. Risques et plan de contingence

Les principaux risques identifiés sont :
- indisponibilité temporaire d’une API source ;
- dérive de schéma ;
- retard sur un module avancée ;
- bug bloquant sur la chaîne d’exposition ;
- incompatibilité de versions.

Les réponses prévues sont :
- retries et backoff ;
- validation de schéma ;
- réduction du scope non critique si nécessaire ;
- rollback Git et régénération des données ;
- verrouillage des versions par fichiers de dépendances et images Docker.

## Conclusion de la réunion

Je conclus cette réunion de lancement sur trois messages.

Premièrement, le besoin métier est clair et le périmètre est maîtrisé.  
Deuxièmement, l’organisation projet, les rôles et la feuille de route sont définis.  
Troisièmement, les mécanismes de suivi, de supervision et de communication sont en place pour conduire le projet jusqu’à sa livraison.

Je propose donc de valider le cadrage présenté aujourd’hui et d’engager officiellement la première phase de réalisation.
