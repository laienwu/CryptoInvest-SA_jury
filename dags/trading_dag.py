"""
Automated Trading DAG — Binance testnet, every 5 minutes.

Reads the daily universe produced by ``portfolio_optimization.select_universe``
(via ``storage.load_output("universe_latest")``) and runs one SMA-crossover
tick per schedule interval.

Safety posture (see ``src/trading/``):
    - Mainnet is hard-blocked at client init.
    - Default is ``dry_run=True`` — flip via ``TRADING_DRY_RUN=false`` only
      after the run looks clean in rehearsal.

``max_active_runs=1`` + ``catchup=False`` prevents overlapping ticks and
stops backfills from firing synthetic orders into a live testnet account.

Schedule: ``*/5 * * * *`` (every 5 minutes, aligned to the 5m candle close).
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "automated-trading",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 0,  # ticks are idempotent by coid, but reruns still risk dup klines work
    "retry_delay": timedelta(seconds=30),
    "execution_timeout": timedelta(minutes=4),  # under the 5m cadence
}

dag = DAG(
    "automated_trading",
    default_args=default_args,
    description="SMA-crossover tick on Binance testnet, every 5 minutes",
    schedule_interval="*/5 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["trading", "binance", "testnet"],
)


def run_trading_tick() -> str:
    from src.trading import run_tick
    summary = run_tick()
    return (
        f"orders_placed={summary['orders_placed']} "
        f"closed={summary['positions_closed']} "
        f"reconciled={summary['reconciled']} "
        f"dry_run={summary['dry_run']} "
        f"errors={len(summary['errors'])}"
    )


trading_tick_task = PythonOperator(
    task_id="trading_tick",
    python_callable=run_trading_tick,
    dag=dag,
)
