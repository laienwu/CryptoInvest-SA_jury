"""
Portfolio Optimization DAG

Orchestrates: ingest → transform → optimize → frontier → backtest

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

def run_ingest() -> str:
    from src.pipeline import ingest_incremental
    from src.storage import get_storage
    storage = get_storage()
    data = ingest_incremental()
    storage.save_raw(data)
    return f"Ingested {len(data)} symbols (incremental)"


def run_transform() -> str:
    from src.pipeline import transform_data
    transform_data()
    return "Transform complete"


def run_optimize() -> str:
    from src.pipeline import optimize_portfolio
    result = optimize_portfolio()
    return f"Optimized: sharpe={result.get('sharpe_ratio', 'N/A'):.3f}"


def run_frontier() -> str:
    from src.pipeline.optimize import compute_and_save_frontier
    compute_and_save_frontier()
    return "Frontier computed"


def run_backtest() -> str:
    from src.pipeline.backtest import run_backtest
    result = run_backtest()
    sharpe = result.get("metrics", {}).get("strategy", {}).get("sharpe_ratio", "N/A")
    return f"Backtest complete: strategy sharpe={sharpe}"


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

frontier_task = PythonOperator(
    task_id="frontier",
    python_callable=run_frontier,
    dag=dag,
)

backtest_task = PythonOperator(
    task_id="backtest",
    python_callable=run_backtest,
    dag=dag,
)

# DAG dependencies
ingest_task >> transform_task >> optimize_task >> frontier_task >> backtest_task