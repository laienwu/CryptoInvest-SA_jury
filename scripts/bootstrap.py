"""
One-shot bootstrap: full ingest → transform → optimize → frontier → backtest.

Use for initial setup or when adding new symbols to config.toml.
After this completes, Airflow handles daily incremental updates.
"""

from src.pipeline import ingest_data, optimize_portfolio, transform_data
from src.pipeline.backtest import run_backtest
from src.pipeline.optimize import compute_and_save_frontier
from src.storage import get_storage

storage = get_storage()

print("=== BOOTSTRAP: full ingest (all symbols, full history) ===")
data = ingest_data()
storage.save_raw(data)

print("=== TRANSFORM ===")
transform_data()

print("=== OPTIMIZE ===")
optimize_portfolio()

print("=== FRONTIER ===")
compute_and_save_frontier()

print("=== BACKTEST ===")
run_backtest()

print("=== BOOTSTRAP COMPLETE — Airflow will handle daily updates ===")
