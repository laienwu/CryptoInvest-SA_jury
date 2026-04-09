# ADR-005 : Apache Airflow pour l'orchestration de pipelines

**Statut :** Accepté
**Date :** 2025-02-01
**Décisionnaires :** Laien Wu (Ingénieur de données), Pierre Durand (DevOps)
**Technique Histoire :** US-009

---

## Contexte

Nous devons orchestrer le pipeline ETL avec :

- Exécution planifiée (toutes les heures)
- Deux branches parallèles (crypto + actifs traditionnels)
- Gestion des dépendances des tâches
- Surveillance et alerte
- Logique de nouvelle tentative pour les tâches ayant échoué
- Historique et journaux d'exécution

Options considérées :
1. Apache Airflow
2. Préfet
3. Dague
4. Cron + scripts personnalisés
5. Actions GitHub

---

## Décision

**Nous utiliserons Apache Airflow pour le pipeline orchestration.**

---

## Justification

### Comparaison :

| Critère | Flux d'air | Préfet | Dague | Cron | Actions GitHub |
|-----------|---------|---------|---------|------|----------------|
| Norme industrielle | Oui | Croissance | Croissance | Héritage | Axé sur l'IC |
| Interface utilisateur pour la surveillance | Excellent | Bon | Bon | Aucun | De base |
| DAG natifs Python | Oui | Oui | Oui | Non | YAML |
| Auto-hébergé | Oui | Oui | Oui | Oui | Non |
| Courbe d'apprentissage | Moyen | Faible | Moyen | Faible | Faible |
| Pertinence de la certification | Élevé | Moyen | Moyen | Faible | Faible |

### Facteurs clés :

1. **Norme industrielle** : Airflow est l'outil d'orchestration le plus largement utilisé en ingénierie des données. Critique pour la crédibilité de la certification.

2. **Excellente interface utilisateur de surveillance** : l'interface Web affiche la structure du DAG, l'état des tâches, l'historique d'exécution et les journaux.

3. **Gestion des dépendances** : Dépendances de tâches définies de manière déclarative :
   ```python
   ingest >> transform >> optimize >> frontier >> backtest >> monte_carlo
   [backtest, backtest_trad] >> dbt_run
   ```

4. **Planification riche** : expressions de type Cron avec rattrapage et prise en charge du remplissage.

5. **Logique de nouvelle tentative** : nouvelle tentative intégrée avec des délais configurables et une interruption exponentielle.

6. **Docker-native** : images Docker officielles, déploiement facile avec docker-compose.

### Pourquoi pas Prefect/Dagster :
- Moins de présence sur le marché (plus difficile à démontrer pour la certification)
- Airflow est explicitement mentionné dans les descriptions de poste de l'industrie
- Équipe déjà familiarisée avec Airflow concepts

### Pourquoi pas Cron :
- Aucune gestion des dépendances
- Aucune interface utilisateur de surveillance
- Aucune logique de nouvelle tentative
- Aucun historique d'exécution
- Nécessiterait une implémentation personnalisée pour les bases fonctionnalités

---

## Conséquences

### Positif
- Orchestration de qualité professionnelle
- Excellente surveillance et débogage
- Compétence reconnue par l'industrie
- Nouvelles tentatives et alertes intégrées
- Exigence de certification satisfaite

### Négatif
- Empreinte de ressources plus importante que les alternatives
- Serveur Web + Planificateur + surcharge de base de données
- Surpuissance pour un seul DAG
- Configuration initiale complexe

### Neutre
- Backend PostgreSQL (séparé de la base de données de l'application)
- Exécuteur séquentiel suffisant pour MVP

---

## Conformité

| Exigence | Statut |
|-------------|--------|
| C15 - Intégration ETL | DAG orchestre l'ingestion → la transformation → l'optimisation |
| C16 - Gestion d'entrepôt | Planification, surveillance, alertes |

---

## Mise en œuvre

### Structure du DAG

```
portfolio_optimization
├── Branche Crypto :
│   ingest → transform → optimize → frontier → backtest → monte_carlo
│
├── Branche Traditionnelle (yfinance) :
│   ingest_trad → transform_trad → optimize_trad → frontier_trad → backtest_trad
│
└── dbt_run (après la complétion des deux backtest)
```

Les deux branches s'exécutent en parallèle. Le `monte_carlo` s'exécute après le backtest crypto. La tâche `dbt_run` (BashOperator) attend la fin des deux branches avant de lancer les transformations SQL dbt.

### Code DAG

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "data-engineer",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=10),
}

dag = DAG(
    "portfolio_optimization",
    default_args=default_args,
    description="ETL pipeline for crypto + traditional portfolio optimization",
    schedule_interval="@hourly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["portfolio", "etl", "binance", "yfinance"],
)

# --- Crypto branch ---
ingest = PythonOperator(task_id="ingest", python_callable=run_ingest, dag=dag)
transform = PythonOperator(task_id="transform", python_callable=run_transform, dag=dag)
optimize = PythonOperator(task_id="optimize", python_callable=run_optimize, dag=dag)
frontier = PythonOperator(task_id="frontier", python_callable=run_frontier, dag=dag)
backtest = PythonOperator(task_id="backtest", python_callable=run_backtest, dag=dag)
monte_carlo = PythonOperator(task_id="monte_carlo", python_callable=run_monte_carlo_task, dag=dag)

# --- Traditional branch ---
ingest_trad = PythonOperator(task_id="ingest_trad", python_callable=run_ingest_trad, dag=dag)
transform_trad = PythonOperator(task_id="transform_trad", python_callable=run_transform_trad, dag=dag)
optimize_trad = PythonOperator(task_id="optimize_trad", python_callable=run_optimize_trad, dag=dag)
frontier_trad = PythonOperator(task_id="frontier_trad", python_callable=run_frontier_trad, dag=dag)
backtest_trad = PythonOperator(task_id="backtest_trad", python_callable=run_backtest_trad, dag=dag)

# --- dbt transforms (BashOperator) ---
dbt_run = BashOperator(
    task_id="dbt_run",
    bash_command="cd /opt/airflow/dbt_project && dbt clean --profiles-dir . && dbt run --profiles-dir .",
    dag=dag,
)

# --- Dependencies ---
# Crypto: ingest → transform → optimize → frontier → backtest → monte_carlo
ingest >> transform >> optimize >> frontier >> backtest >> monte_carlo

# Traditional: ingest_trad → transform_trad → optimize_trad → frontier_trad → backtest_trad
ingest_trad >> transform_trad >> optimize_trad >> frontier_trad >> backtest_trad

# dbt runs after both branches complete
[backtest, backtest_trad] >> dbt_run
```

### Configuration de Docker Compose

```yaml
x-airflow-common: &airflow-common
  build:
    context: .
    dockerfile: Dockerfile.airflow  # apache/airflow:2.8.1-python3.11
  environment:
    - AIRFLOW__CORE__EXECUTOR=LocalExecutor
    - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://...
    - PYTHONPATH=/opt/airflow
  volumes:
    - ./dags:/opt/airflow/dags
    - ./src:/opt/airflow/src
    - ./data:/opt/airflow/data
    - ./config.toml:/opt/airflow/config.toml
    - ./dbt_project:/opt/airflow/dbt_project

services:
  airflow-webserver:
    <<: *airflow-common
    ports:
      - "8081:8080"

  airflow-scheduler:
    <<: *airflow-common
    # ... scheduler config
```

L'image Airflow est construite via `Dockerfile.airflow` basé sur `apache/airflow:2.8.1-python3.11` avec les dépendances projet (PyArrow, DuckDB, scipy, yfinance, dbt-duckdb).

### Approche de surveillance

| Que surveiller | Comment | Seuil d'alerte |
|-----------------|-----|-----------------|
| Succès de l'exécution du DAG | Interface utilisateur du flux d'air | Tout échec |
| Durée de la tâche | Mesures du débit d'air | > 10 minutes |
| Fraîcheur des données | Capteur personnalisé | > 24 heures |

---

## Alternatives envisagées pour l'avenir

Si l'échelle augmente de manière significative :
- Envisagez l'exécuteur Kubernetes pour les tâches parallèles
- Envisagez le céleri exécuteur pour les travailleurs distribués
- Envisagez l'API TaskFlow d'Airflow 2.x pour un code plus propre

---

## Références

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Meilleures pratiques en matière de flux d'air](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [Exécuter le flux d'air dans Docker](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html)

---

*Révisé par : Pierre Durand (DevOps)*
*Approuvé par : Marie Dupont (Product Owner)*
