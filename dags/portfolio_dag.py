"""
Portfolio Optimization DAG

Orchestrates two parallel branches:
  Crypto:       ingest → transform → optimize → frontier → backtest
  Traditional:  ingest_trad → transform_trad → optimize_trad → frontier_trad → backtest_trad

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
    description="ETL pipeline for crypto + traditional portfolio optimization",
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["portfolio", "etl", "binance", "yfinance"],
)


# =============================================================================
# Crypto branch
# =============================================================================


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


# =============================================================================
# Traditional assets branch (yfinance)
# =============================================================================


def run_ingest_trad() -> str:
    from src.pipeline.ingest_yfinance import ingest_yfinance_incremental
    from src.storage import get_storage
    storage = get_storage()
    data = ingest_yfinance_incremental()
    storage.save_raw(data)
    return f"Ingested {len(data)} trad symbols (incremental)"


def run_transform_trad() -> str:
    from src.pipeline.transform import transform_yfinance_data
    transform_yfinance_data()
    return "Transform trad complete"


def run_optimize_trad() -> str:
    from src.pipeline.optimize import optimize_yfinance_portfolio
    result = optimize_yfinance_portfolio()
    return f"Optimized trad: sharpe={result.get('sharpe_ratio', 'N/A'):.3f}"


def run_frontier_trad() -> str:
    from src.pipeline.optimize import compute_and_save_frontier_trad
    compute_and_save_frontier_trad()
    return "Frontier trad computed"


def run_backtest_trad() -> str:
    from src.pipeline.backtest import run_yfinance_backtest
    result = run_yfinance_backtest()
    sharpe = result.get("metrics", {}).get("strategy", {}).get("sharpe_ratio", "N/A")
    return f"Backtest trad complete: strategy sharpe={sharpe}"


# =============================================================================
# Crypto tasks
# =============================================================================

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

# =============================================================================
# Traditional assets tasks
# =============================================================================

ingest_trad_task = PythonOperator(
    task_id="ingest_trad",
    python_callable=run_ingest_trad,
    dag=dag,
)

transform_trad_task = PythonOperator(
    task_id="transform_trad",
    python_callable=run_transform_trad,
    dag=dag,
)

optimize_trad_task = PythonOperator(
    task_id="optimize_trad",
    python_callable=run_optimize_trad,
    dag=dag,
)

frontier_trad_task = PythonOperator(
    task_id="frontier_trad",
    python_callable=run_frontier_trad,
    dag=dag,
)

backtest_trad_task = PythonOperator(
    task_id="backtest_trad",
    python_callable=run_backtest_trad,
    dag=dag,
)

# =============================================================================
# Monte Carlo (runs after crypto backtest)
# =============================================================================


def run_monte_carlo_task() -> str:
    from src.pipeline.monte_carlo import run_monte_carlo
    result = run_monte_carlo()
    return f"Monte Carlo complete: {result['config']['n_simulations']} simulations"


monte_carlo_task = PythonOperator(
    task_id="monte_carlo",
    python_callable=run_monte_carlo_task,
    dag=dag,
)

# =============================================================================
# DAG dependencies — two parallel branches + monte carlo
# =============================================================================

# Crypto: ingest → transform → optimize → frontier → backtest → monte_carlo
ingest_task >> transform_task >> optimize_task >> frontier_task >> backtest_task >> monte_carlo_task

# Traditional: ingest_trad → transform_trad → optimize_trad → frontier_trad → backtest_trad
ingest_trad_task >> transform_trad_task >> optimize_trad_task >> frontier_trad_task >> backtest_trad_task