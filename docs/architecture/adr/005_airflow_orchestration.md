# ADR-005: Apache Airflow for Pipeline Orchestration

**Status:** Accepted
**Date:** 2025-02-01
**Deciders:** [Your Name] (Data Engineer), Pierre Durand (DevOps)
**Technical Story:** US-009

---

## Context

We need to orchestrate the daily ETL pipeline with:

- Scheduled execution (daily at midnight UTC)
- Task dependency management (ingest → transform → optimize)
- Monitoring and alerting
- Retry logic for failed tasks
- Execution history and logs

Options considered:
1. Apache Airflow
2. Prefect
3. Dagster
4. Cron + custom scripts
5. GitHub Actions

---

## Decision

**We will use Apache Airflow for pipeline orchestration.**

---

## Rationale

### Comparison:

| Criterion | Airflow | Prefect | Dagster | Cron | GitHub Actions |
|-----------|---------|---------|---------|------|----------------|
| Industry standard | Yes | Growing | Growing | Legacy | CI-focused |
| UI for monitoring | Excellent | Good | Good | None | Basic |
| Python-native DAGs | Yes | Yes | Yes | No | YAML |
| Self-hosted | Yes | Yes | Yes | Yes | No |
| Learning curve | Medium | Low | Medium | Low | Low |
| Certification relevance | High | Medium | Medium | Low | Low |

### Key factors:

1. **Industry standard**: Airflow is the most widely used orchestration tool in data engineering. Critical for certification credibility.

2. **Excellent monitoring UI**: Web interface shows DAG structure, task status, execution history, and logs.

3. **Dependency management**: Task dependencies defined declaratively:
   ```python
   ingest >> transform >> optimize
   ```

4. **Rich scheduling**: Cron-like expressions with catchup, backfill support.

5. **Retry logic**: Built-in retry with configurable delays and exponential backoff.

6. **Docker-native**: Official Docker images, easy deployment with docker-compose.

### Why not Prefect/Dagster:
- Less market presence (harder to demonstrate for certification)
- Airflow is explicitly mentioned in industry job descriptions
- Team already familiar with Airflow concepts

### Why not Cron:
- No dependency management
- No monitoring UI
- No retry logic
- No execution history
- Would need custom implementation for basic features

---

## Consequences

### Positive
- Professional-grade orchestration
- Excellent monitoring and debugging
- Industry-recognized skill
- Built-in retry and alerting
- Certification requirement satisfied

### Negative
- Heavier resource footprint than alternatives
- Webserver + Scheduler + DB overhead
- Overkill for single DAG
- Complex initial setup

### Neutral
- PostgreSQL backend (separate from application DB)
- Sequential executor sufficient for MVP

---

## Compliance

| Requirement | Status |
|-------------|--------|
| C15 - ETL integration | DAG orchestrates ingest → transform → optimize |
| C16 - Warehouse management | Scheduling, monitoring, alerting |

---

## Implementation

### DAG Structure

```
portfolio_dag
├── ingest_data          # Extract from all sources
│   └── transform_data   # Calculate metrics
│       └── optimize_portfolio  # Markowitz optimization
└── (parallel branch)
    └── update_warehouse  # Refresh DuckDB tables
```

### DAG Code

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "data-engineer",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["alerts@company.com"],
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "portfolio_optimization",
    default_args=default_args,
    description="Daily crypto portfolio optimization",
    schedule_interval="0 0 * * *",  # Daily at midnight UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["portfolio", "crypto"],
) as dag:

    ingest = PythonOperator(
        task_id="ingest_data",
        python_callable=ingest_all_sources,
    )

    transform = PythonOperator(
        task_id="transform_data",
        python_callable=transform_data,
    )

    optimize = PythonOperator(
        task_id="optimize_portfolio",
        python_callable=optimize_portfolio,
    )

    ingest >> transform >> optimize
```

### Docker Compose Setup

```yaml
services:
  airflow-webserver:
    image: apache/airflow:2.7.0
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://...
    ports:
      - "8081:8080"
    volumes:
      - ./dags:/opt/airflow/dags
      - ./data:/opt/airflow/data

  airflow-scheduler:
    image: apache/airflow:2.7.0
    # ... scheduler config
```

### Monitoring Approach

| What to Monitor | How | Alert Threshold |
|-----------------|-----|-----------------|
| DAG run success | Airflow UI | Any failure |
| Task duration | Airflow metrics | > 10 minutes |
| Data freshness | Custom sensor | > 24 hours |

---

## Alternatives Considered for Future

If scale increases significantly:
- Consider Kubernetes executor for parallel tasks
- Consider Celery executor for distributed workers
- Consider Airflow 2.x TaskFlow API for cleaner code

---

## References

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Airflow Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [Running Airflow in Docker](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html)

---

*Reviewed by: Pierre Durand (DevOps)*
*Approved by: Marie Dupont (Product Owner)*
