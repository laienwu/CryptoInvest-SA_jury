"""
Portfolio Optimization DAG

Orchestrates: ingest → transform → optimize

Schedule: Daily at 00:00 UTC
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-engineer",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "portfolio_optimization",
    default_args=default_args,
    description="ETL pipeline for portfolio optimization",
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["portfolio", "etl", "binance"],
)


def run_ingest():
    from src.pipeline import ingest_incremental
    from src.storage import get_storage
    storage = get_storage()
    data = ingest_incremental()
    storage.save_raw(data)
    return f"Ingested {len(data)} symbols (incremental)"


def run_transform():
    from src.pipeline import transform_data
    transform_data()
    return "Transform complete"


def run_optimize():
    from src.pipeline import optimize_portfolio
    result = optimize_portfolio()
    return f"Optimized: {result['weights']}"


ingest_task = PythonOperator(
    task_id="ingest",
    python_callable=run_ingest,
    dag=dag,
)

transform_task = PythonOperator(
    task_id="transform",
    python_callable=run_transform,
    dag=dag,
)

optimize_task = PythonOperator(
    task_id="optimize",
    python_callable=run_optimize,
    dag=dag,
)

# DAG dependencies
ingest_task >> transform_task >> optimize_task
