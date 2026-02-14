"""
Pipeline package for data operations.

Public API — main entry points for each pipeline stage.
For internal helpers (calculate_log_returns, calculate_sharpe_ratio, etc.),
import directly from the specific submodule.

Modules:
- ingest: Data ingestion from Binance API
- ingest_sources: Multi-source ingestion (C8 compliance)
- ingest_scraping: Web scraping (CoinGecko)
- ingest_postgres: PostgreSQL database (benchmarks)
- transform: Data transformation and metrics calculation
- optimize: Portfolio optimization (Markowitz mean-variance)
- backtest: Walk-forward backtesting

Error handling pattern:
    Each module defines a custom exception with ``message`` plus a
    domain-specific context field (``operation``, ``source``, ``url``,
    ``query``, or ``status_code``).

    Catch strategies are intentional per domain:
    - **Ingest** (best-effort): catch-and-continue — partial data is useful.
    - **Transform / Optimize / Backtest** (all-or-nothing): catch-and-reraise
      with a descriptive custom exception.
"""

# -- Entry points (pipeline stages) ------------------------------------------
# -- Exceptions ---------------------------------------------------------------
from .backtest import BacktestError, run_backtest
from .ingest import ingest_data, ingest_incremental

# -- Source loaders (used in demos / CHEAT_SHEET) -----------------------------
from .ingest_postgres import (
    BenchmarkRepository,
    DatabaseError,
    load_benchmarks,
    load_benchmarks_fallback,
)
from .ingest_scraping import ScrapingError
from .ingest_sources import (
    SourceError,
    ingest_all_sources,
    load_portfolio_config_json,
    load_symbols_metadata_csv,
)
from .optimize import (
    OptimizeError,
    compute_and_save_frontier,
    load_optimal_portfolio,
    optimize_portfolio,
)
from .transform import TransformError, load_processed_metrics, transform_data

__all__ = [
    # Pipeline stages
    "ingest_data",
    "ingest_incremental",
    "ingest_all_sources",
    "transform_data",
    "load_processed_metrics",
    "optimize_portfolio",
    "compute_and_save_frontier",
    "load_optimal_portfolio",
    "run_backtest",
    # Source loaders
    "load_symbols_metadata_csv",
    "load_portfolio_config_json",
    "load_benchmarks",
    "load_benchmarks_fallback",
    # Repository
    "BenchmarkRepository",
    # Exceptions
    "BacktestError",
    "DatabaseError",
    "OptimizeError",
    "ScrapingError",
    "SourceError",
    "TransformError",
]
