"""
Pipeline package for data operations.

Contains modules for:
- ingest: Data ingestion from Binance API
- ingest_sources: Multi-source ingestion (C8 compliance)
- ingest_scraping: Web scraping (CoinGecko)
- ingest_postgres: PostgreSQL database (benchmarks)
- storage: Data persistence
- transform: Data transformation and metrics calculation
- optimize: Portfolio optimization (Markowitz mean-variance)

C8 Compliance - 5 Source Types:
1. API REST (Binance)
2. CSV File (symbols metadata)
3. JSON File (portfolio config)
4. Web Scraping (CoinGecko market rankings)
5. PostgreSQL Database (historical benchmarks)
"""

from .ingest import fetch_klines, fetch_all_symbols, ingest_data, ingest_incremental, fetch_current_prices
from .ingest_sources import (
    ingest_all_sources,
    load_symbols_metadata_csv,
    load_portfolio_config_json,
    enrich_prices_with_metadata,
    get_symbols_by_sector,
    SourceError,
)
from .ingest_scraping import (
    scrape_market_rankings,
    enrich_with_market_data,
    ScrapingError,
)
from .ingest_postgres import (
    load_benchmarks,
    load_benchmarks_fallback,
    load_index_returns,
    get_benchmark_summary,
    test_connection as test_postgres_connection,
    DatabaseError,
)
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
    compute_efficient_frontier,
    compute_and_save_frontier,
    OptimizeError,
)
from .backtest import (
    run_backtest,
    BacktestError,
)

__all__ = [
    # Ingest (API)
    "fetch_klines",
    "fetch_all_symbols",
    "ingest_data",
    "ingest_incremental",
    "fetch_current_prices",
    # Ingest (Multi-source - C8)
    "ingest_all_sources",
    "load_symbols_metadata_csv",
    "load_portfolio_config_json",
    "enrich_prices_with_metadata",
    "get_symbols_by_sector",
    "SourceError",
    # Ingest (Web Scraping - C8)
    "scrape_market_rankings",
    "enrich_with_market_data",
    "ScrapingError",
    # Ingest (PostgreSQL - C8)
    "load_benchmarks",
    "load_benchmarks_fallback",
    "load_index_returns",
    "get_benchmark_summary",
    "test_postgres_connection",
    "DatabaseError",
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
    "compute_efficient_frontier",
    "compute_and_save_frontier",
    "OptimizeError",
    # Backtest
    "run_backtest",
    "BacktestError",
]
