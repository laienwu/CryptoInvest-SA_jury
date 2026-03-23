"""
One-shot bootstrap: full ingest → transform → optimize → frontier → backtest.

Runs both crypto and traditional (yfinance) pipelines in sequence.
Use for initial setup or when adding new symbols to config.toml.
After this completes, Airflow handles daily incremental updates.
"""

from src.pipeline import ingest_data, optimize_portfolio, transform_data
from src.pipeline.backtest import run_backtest
from src.pipeline.optimize import compute_and_save_frontier
from src.storage import get_storage

storage = get_storage()

# =========================================================================
# Crypto pipeline
# =========================================================================

print("=== BOOTSTRAP: crypto full ingest (all symbols, full history) ===")
data = ingest_data()
storage.save_raw(data)

print("=== CRYPTO: transform ===")
transform_data()

print("=== CRYPTO: optimize ===")
optimize_portfolio()

print("=== CRYPTO: frontier ===")
compute_and_save_frontier()

print("=== CRYPTO: backtest ===")
run_backtest()

# =========================================================================
# Traditional assets pipeline (yfinance)
# =========================================================================

try:
    from src.pipeline.backtest import run_yfinance_backtest
    from src.pipeline.ingest_yfinance import ingest_yfinance_data
    from src.pipeline.optimize import (
        compute_and_save_frontier_trad,
        optimize_yfinance_portfolio,
    )
    from src.pipeline.transform import transform_yfinance_data

    print("=== TRAD: full ingest (yfinance) ===")
    trad_data = ingest_yfinance_data()
    storage.save_raw(trad_data)

    print("=== TRAD: transform ===")
    transform_yfinance_data()

    print("=== TRAD: optimize ===")
    optimize_yfinance_portfolio()

    print("=== TRAD: frontier ===")
    compute_and_save_frontier_trad()

    print("=== TRAD: backtest ===")
    run_yfinance_backtest()

except ImportError:
    print("=== TRAD: skipped (yfinance not installed) ===")

print("=== BOOTSTRAP COMPLETE — Airflow will handle daily updates ===")
