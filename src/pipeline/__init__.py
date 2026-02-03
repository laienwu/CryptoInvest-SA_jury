"""
Pipeline package for data operations.

Contains modules for:
- ingest: Data ingestion from Binance API
- storage: Data persistence
- transform: Data transformation and metrics calculation
- optimize: Portfolio optimization (Markowitz mean-variance)
"""

from .ingest import fetch_klines, fetch_all_symbols, ingest_data, ingest_incremental, fetch_current_prices
from .transform import (
    transform_data,
    load_processed_metrics,
    calculate_log_returns,
    calculate_volatility,
    calculate_correlation_matrix,
    calculate_covariance_matrix,
    calculate_mean_returns,
    TransformError,
)
from .optimize import (
    optimize_portfolio,
    load_optimal_portfolio,
    calculate_equal_weight_portfolio,
    calculate_portfolio_return,
    calculate_portfolio_volatility,
    calculate_sharpe_ratio,
    OptimizeError,
)

__all__ = [
    # Ingest
    "fetch_klines",
    "fetch_all_symbols",
    "ingest_data",
    "ingest_incremental",
    "fetch_current_prices",
    # Transform
    "transform_data",
    "load_processed_metrics",
    "calculate_log_returns",
    "calculate_volatility",
    "calculate_correlation_matrix",
    "calculate_covariance_matrix",
    "calculate_mean_returns",
    "TransformError",
    # Optimize
    "optimize_portfolio",
    "load_optimal_portfolio",
    "calculate_equal_weight_portfolio",
    "calculate_portfolio_return",
    "calculate_portfolio_volatility",
    "calculate_sharpe_ratio",
    "OptimizeError",
]
