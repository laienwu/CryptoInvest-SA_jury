# E6 — Maintien en conditions opérationnelles d’un DWH

**Modalité d’évaluation :** E6  
**Compétences évaluées :** C16, C17  
**Nature :** Étude de cas fictive

## Objet de l’épreuve

Dans cette épreuve, je démontre ma capacité à maintenir un entrepôt de données en conditions opérationnelles, à le superviser dans la durée et à gérer l’évolution des dimensions lorsque les données sources changent.

## 1. Stratégie de maintien en conditions opérationnelles

Mon approche de MCO repose sur quatre piliers :
- exploitation documentée ;
- supervision continue ;
- procédures de reprise ;
- gestion maîtrisée des changements.

Le DWH n’est pas isolé : il dépend des flux du Data Lake, des transformations dbt, du DAG Airflow et des mécanismes de monitoring.

## 2. Outils de supervision

### 2.1 Orchestration

Le DAG principal orchestre les traitements quotidiens en deux branches parallèles :
- une branche crypto ;
- une branche traditionnelle ;
- puis une consolidation vers `dbt_run`.

Chaque tâche bénéficie :
- d’une planification quotidienne ;
- de tentatives automatiques en cas d’échec ;
- d’un historique d’exécution ;
- d’un accès aux logs.

### 2.2 Monitoring

Les métriques suivies sont les suivantes :
[lien vers les détails des KPI considérés](../annexes/business/kpi_dashboard.md)

| Indicateur | Seuil / objectif |
|------------|------------------|
| latence API p95 | alerte au-delà de 2 secondes |
| taux d’erreur API | alerte au-delà de 5 % |
| succès du DAG | toute tâche en échec déclenche une investigation |
| lag consommateur Kafka | alerte au-delà d’un seuil défini |
| espace disque | vigilance au-delà de 80 % |
| fraîcheur des données | alerte si la dernière mise à jour est trop ancienne |

Prometheus collecte les métriques, Grafana les visualise, et Airflow constitue la première interface de diagnostic des exécutions.

### 2.3 SLA et objectifs de reprise

[lien vers SLA détaillé](../annexes/operations/sla.md)

Le cadre opérationnel est complété par :
- des objectifs de niveau de service ;
- un runbook d’exploitation ;
- un plan de réponse aux incidents ;
- des procédures de redémarrage et de reprise.

L’idée directrice est la suivante : les données Bronze et Silver sont régénérables depuis les sources, le Gold est recalculable, et le warehouse peut être reconstruit via dbt. Cela réduit fortement le risque de perte irréversible.

## 3. Procédures d’exploitation

Ci-dessous le lien vers le runbook pour plus de détails sur les différents process d'orchestration et ochestration.
[runbook lien](../annexes/operations/runbook.md)

En résumé, j’ai documenté les procédures suivantes :
- démarrage, arrêt et redémarrage des services ;
- consultation des logs ;
- accès aux conteneurs ;
- relance de l’API ;
- redémarrage d’Airflow ;
- relance ciblée des tâches ;
- reconstitution des données et du warehouse ;
- escalade en cas d’incident.

J’ai également précisé :
- les interlocuteurs ;
- les délais de réponse ;
- les cas d’usage les plus fréquents ;
- les conditions de reprise après incident.

## 4. Gestion des incidents

Le lien vers les [procédures détaillées pour gestion des incides](../annexes/operations/incident_response.md)
dont l'essence se résume ci-dessous. 

Le plan de réponse aux incidents prévoit une démarche structurée :
1. qualification de l’incident ;
2. collecte des preuves et des logs ;
3. analyse de la cause racine ;
4. traitement correctif ;
5. validation du retour à la normale ;
6. capitalisation.

Les scénarios traités couvrent notamment :
- API indisponible ;
- échec de tâche Airflow ;
- données corrompues ;
- surcharge ou saturation de ressources ;
- écart sur la qualité des données.

## 5. Gestion des variations de dimensions

La dimension sensible du projet est `dim_symbol`.
Je détaille dans le rapport [dimensions SCD](../annexes/rapport/08_scd_dimensions.md) la gestion des évolutions/varations des dimensions selon le type d'évolution.

### 5.1 Choix retenu à date

J’utilise actuellement une logique de **SCD Type 1 implicite** :
- lorsqu’un nouveau symbole apparaît, il est ajouté ;
- lorsqu’une correction est nécessaire, la valeur est écrasée ;
- je ne conserve pas d’historique détaillé des changements.

Ce choix est adapté au projet car :
- les changements de symboles sont rares ;
- la priorité est la simplicité de mise en œuvre ;
- le besoin d’audit historique détaillé n’est pas central dans le périmètre actuel.

### 5.2 Cas d’évolution identifiés

Les évolutions prises en compte sont :
- ajout d’un nouveau symbole crypto ;
- ajout d’un actif traditionnel ;
- delisting ;
- renommage d’un actif ;
- correction de métadonnées.

### 5.3 Évolution vers SCD Type 2

J’ai toutefois préparé une évolution vers **SCD Type 2** lorsque la traçabilité complète devient nécessaire. Dans ce cas :
- une clé technique est introduite ;
- chaque changement ferme la version courante ;
- une nouvelle ligne est créée avec `valid_from`, `valid_to` et `is_current`.

Cette approche devient pertinente si :
- un audit réglementaire l’exige ;
- l’historisation des delistings devient nécessaire ;
- l’on veut analyser les performances par version d’actif ou de métadonnées.

## 6. Impact des variations sur les ETL

Aujourd’hui, les ETL fonctionnent en logique Type 1 :
- ingestion des nouvelles données ;
- mise à jour simple des symboles ;
- absence d’historisation détaillée.

Avec un passage en Type 2, l’ETL évoluerait ainsi :
- détection du changement dans les métadonnées ;
- fermeture de la ligne en cours ;
- insertion d’une nouvelle version ;
- journalisation du changement ;
- adaptation des jointures entre faits et dimensions.

J’ai donc démontré à la fois la capacité à exploiter un schéma simple et la capacité à préparer une évolution plus avancée.

## 7. Synthèse

Le maintien en conditions opérationnelles que je propose ne se limite pas à surveiller un service. Il combine :
- exploitation documentée ;
- supervision outillée ;
- gestion des incidents ;
- reconstruction possible du warehouse ;
- gestion raisonnée des variations dimensionnelles.

Je démontre ainsi que le DWH peut être non seulement construit, mais aussi maintenu durablement dans un cadre opérationnel crédible.
