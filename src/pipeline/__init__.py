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

from .backtest import (
    BacktestError,
    run_backtest,
)
from .ingest import (
    fetch_all_symbols,
    fetch_current_prices,
    fetch_klines,
    ingest_data,
    ingest_incremental,
)
from .ingest_postgres import (
    DatabaseError,
    get_benchmark_summary,
    load_benchmarks,
    load_benchmarks_fallback,
    load_index_returns,
)
from .ingest_postgres import (
    test_connection as test_postgres_connection,
)
from .ingest_scraping import (
    ScrapingError,
    enrich_with_market_data,
    scrape_market_rankings,
)
from .ingest_sources import (
    SourceError,
    enrich_prices_with_metadata,
    get_symbols_by_sector,
    ingest_all_sources,
    load_portfolio_config_json,
    load_symbols_metadata_csv,
)
from .optimize import (
    OptimizeError,
    calculate_equal_weight_portfolio,
    calculate_portfolio_return,
    calculate_portfolio_volatility,
    calculate_sharpe_ratio,
    compute_and_save_frontier,
    compute_efficient_frontier,
    load_optimal_portfolio,
    optimize_portfolio,
)
from .transform import (
    TransformError,
    calculate_correlation_matrix,
    calculate_covariance_matrix,
    calculate_log_returns,
    calculate_mean_returns,
    calculate_volatility,
    load_processed_metrics,
    transform_data,
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
