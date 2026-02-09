"""
Data transformation module for portfolio optimization.

This module calculates financial metrics from raw OHLCV data:
- Daily returns (log returns)
- Annualized volatility per symbol
- Correlation matrix between symbols
- Covariance matrix for portfolio optimization

All calculations use pyarrow (no numpy/pandas dependency).

Output format:
    Returns: {"symbols": [...], "dates": [...], "values": [[...], ...]}
    Volatility: {"symbols": [...], "values": [...]}
    Correlation: {"symbols": [...], "matrix": [[...], ...]}
    Covariance: {"symbols": [...], "matrix": [[...], ...]}

Example usage:
    >>> from src.pipeline.transform import transform_data
    >>> results = transform_data()
    >>> print(results["correlation"]["matrix"])
"""

import logging
import math
import tomllib
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from src.storage import get_storage

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================


def _load_config() -> dict[str, Any]:
    """Load config from config.toml."""
    config_path = Path(__file__).parent.parent.parent / "config.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    return {}


_config = _load_config()
_portfolio = _config.get("portfolio", {})

DEFAULT_SYMBOLS: list[str] = _portfolio.get(
    "symbols", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
)

# Trading days per year for annualization (crypto = 365)
TRADING_DAYS_PER_YEAR: int = 365


# =============================================================================
# Exceptions
# =============================================================================


class TransformError(Exception):
    """Custom exception for transformation errors."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


# =============================================================================
# Data Alignment
# =============================================================================


def _align_data_by_date(
    raw_data: dict[str, list[dict]],
) -> tuple[list[str], list[str], list[list[float]]]:
    """
    Align data across symbols by common dates.

    Different symbols may have slightly different date ranges or missing data.
    This function finds the intersection of dates and aligns close prices.

    Args:
        raw_data: Dictionary mapping symbol to list of OHLCV records.

    Returns:
        Tuple of (symbols, dates, prices_matrix) where:
        - symbols: List of symbol names
        - dates: List of common dates (sorted chronologically)
        - prices_matrix: 2D list [n_symbols][n_dates] of close prices

    Raises:
        TransformError: If no common dates found or data is invalid.
    """
    if not raw_data:
        raise TransformError("No data provided for alignment", operation="align")

    symbols = list(raw_data.keys())

    # Build date -> close price mapping for each symbol
    symbol_prices: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()

    for symbol, records in raw_data.items():
        if not records:
            raise TransformError(
                f"No records for symbol {symbol}", operation="align"
            )

        prices_by_date: dict[str, float] = {}
        for record in records:
            date = record["timestamp"]
            close = record["close"]
            prices_by_date[date] = close
            all_dates.add(date)

        symbol_prices[symbol] = prices_by_date

    # Find common dates (intersection)
    common_dates: set[str] = all_dates.copy()
    for symbol in symbols:
        symbol_dates = set(symbol_prices[symbol].keys())
        common_dates = common_dates.intersection(symbol_dates)

    if not common_dates:
        raise TransformError(
            "No common dates found across symbols", operation="align"
        )

    # Sort dates chronologically
    dates = sorted(common_dates)

    logger.info(f"Aligned data: {len(symbols)} symbols, {len(dates)} common dates")
    logger.info(f"Date range: {dates[0]} to {dates[-1]}")

    # Build price matrix [n_symbols][n_dates]
    prices_matrix: list[list[float]] = []
    for symbol in symbols:
        symbol_row = [symbol_prices[symbol][date] for date in dates]
        prices_matrix.append(symbol_row)

    return symbols, dates, prices_matrix


# =============================================================================
# Financial Calculations (using pyarrow compute)
# =============================================================================


def calculate_log_returns(prices: list[list[float]]) -> list[list[float]]:
    """
    Calculate log returns from price series.

    Log returns: r_t = ln(P_t / P_{t-1})

    Advantages of log returns:
    - Additive over time (useful for multi-period analysis)
    - Symmetric for gains and losses
    - Better statistical properties (closer to normal distribution)

    Args:
        prices: 2D list [n_symbols][n_dates] of prices.

    Returns:
        2D list [n_symbols][n_dates-1] of log returns.
    """
    returns: list[list[float]] = []

    for symbol_prices in prices:
        # Convert to pyarrow array for computation
        arr = pa.array(symbol_prices, type=pa.float64())

        # Calculate log prices
        log_prices = pc.ln(arr).to_pylist()

        # Calculate differences: r_t = ln(P_t) - ln(P_{t-1})
        symbol_returns = [
            log_prices[i] - log_prices[i - 1]
            for i in range(1, len(log_prices))
        ]
        returns.append(symbol_returns)

    return returns


def calculate_mean(values: list[float]) -> float:
    """Calculate mean of a list of values using pyarrow."""
    arr = pa.array(values, type=pa.float64())
    result: float = pc.mean(arr).as_py()
    return result


def calculate_stddev(values: list[float], ddof: int = 1) -> float:
    """
    Calculate sample standard deviation using pyarrow.

    Args:
        values: List of values.
        ddof: Delta degrees of freedom (1 for sample std, 0 for population).

    Returns:
        Standard deviation.
    """
    arr = pa.array(values, type=pa.float64())
    # pyarrow stddev uses ddof=0 by default
    # We need to adjust manually for sample std (ddof=1)
    n = len(values)
    variance = pc.variance(arr).as_py()

    if ddof == 0:
        return math.sqrt(variance)
    else:
        # Adjust from population variance to sample variance
        # Sample variance = population_variance * n / (n - ddof)
        sample_variance = variance * n / (n - ddof)
        return math.sqrt(sample_variance)


def calculate_volatility(returns: list[list[float]]) -> list[float]:
    """
    Calculate annualized volatility for each symbol.

    Volatility = std(returns) * sqrt(trading_days_per_year)

    Args:
        returns: 2D list [n_symbols][n_periods] of returns.

    Returns:
        List [n_symbols] of annualized volatilities.
    """
    volatilities: list[float] = []

    for symbol_returns in returns:
        # Standard deviation of returns (sample std, ddof=1)
        daily_std = calculate_stddev(symbol_returns, ddof=1)

        # Annualize: multiply by sqrt of trading days
        annualized_vol = daily_std * math.sqrt(TRADING_DAYS_PER_YEAR)
        volatilities.append(annualized_vol)

    return volatilities


def calculate_covariance(x: list[float], y: list[float], ddof: int = 1) -> float:
    """
    Calculate sample covariance between two series.

    Cov(X, Y) = sum((x_i - mean_x) * (y_i - mean_y)) / (n - ddof)

    Args:
        x: First series.
        y: Second series.
        ddof: Delta degrees of freedom.

    Returns:
        Covariance value.
    """
    n = len(x)
    mean_x = calculate_mean(x)
    mean_y = calculate_mean(y)

    # Sum of products of deviations
    sum_products = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))

    return sum_products / (n - ddof)


def calculate_correlation(x: list[float], y: list[float]) -> float:
    """
    Calculate Pearson correlation between two series.

    Corr(X, Y) = Cov(X, Y) / (std_x * std_y)

    Args:
        x: First series.
        y: Second series.

    Returns:
        Correlation coefficient (-1 to 1).
    """
    cov = calculate_covariance(x, y, ddof=1)
    std_x = calculate_stddev(x, ddof=1)
    std_y = calculate_stddev(y, ddof=1)

    if std_x == 0 or std_y == 0:
        return 0.0

    return cov / (std_x * std_y)


def calculate_correlation_matrix(returns: list[list[float]]) -> list[list[float]]:
    """
    Calculate correlation matrix between symbols.

    Correlation measures linear relationship between asset returns.
    Values range from -1 (perfect negative) to 1 (perfect positive).

    Args:
        returns: 2D list [n_symbols][n_periods] of returns.

    Returns:
        2D list [n_symbols][n_symbols] correlation matrix.
    """
    n_symbols = len(returns)
    matrix: list[list[float]] = []

    for i in range(n_symbols):
        row: list[float] = []
        for j in range(n_symbols):
            if i == j:
                corr = 1.0  # Correlation with itself is always 1
            else:
                corr = calculate_correlation(returns[i], returns[j])
            row.append(corr)
        matrix.append(row)

    return matrix


def calculate_covariance_matrix(returns: list[list[float]]) -> list[list[float]]:
    """
    Calculate annualized covariance matrix between symbols.

    Covariance matrix is essential for Markowitz portfolio optimization.
    Annualized by multiplying by trading days per year.

    Args:
        returns: 2D list [n_symbols][n_periods] of returns.

    Returns:
        2D list [n_symbols][n_symbols] annualized covariance matrix.
    """
    n_symbols = len(returns)
    matrix: list[list[float]] = []

    for i in range(n_symbols):
        row: list[float] = []
        for j in range(n_symbols):
            cov = calculate_covariance(returns[i], returns[j], ddof=1)
            # Annualize: multiply by trading days
            annualized_cov = cov * TRADING_DAYS_PER_YEAR
            row.append(annualized_cov)
        matrix.append(row)

    return matrix


def calculate_mean_returns(returns: list[list[float]]) -> list[float]:
    """
    Calculate annualized mean returns for each symbol.

    Args:
        returns: 2D list [n_symbols][n_periods] of returns.

    Returns:
        List [n_symbols] of annualized mean returns.
    """
    mean_returns: list[float] = []

    for symbol_returns in returns:
        # Mean daily return
        daily_mean = calculate_mean(symbol_returns)

        # Annualize: multiply by trading days
        annualized_mean = daily_mean * TRADING_DAYS_PER_YEAR
        mean_returns.append(annualized_mean)

    return mean_returns


# =============================================================================
# Main Transform Function
# =============================================================================


def transform_data(
    symbols: list[str] | None = None,
    save: bool = True,
    storage_backend: str = "parquet",
) -> dict[str, Any]:
    """
    Main entry point for data transformation.

    This is the primary function to call for the TRANSFORM pipeline step.
    Loads raw OHLCV data, calculates financial metrics, and optionally saves
    the results to storage.

    Args:
        symbols: List of symbols to transform. If None, transforms all available.
        save: Whether to save results to storage. Defaults to True.
        storage_backend: Storage backend to use. Defaults to "parquet".

    Returns:
        Dictionary containing all computed metrics:
        {
            "returns": {"symbols": [...], "dates": [...], "values": [[...], ...]},
            "volatility": {"symbols": [...], "values": [...]},
            "mean_returns": {"symbols": [...], "values": [...]},
            "correlation": {"symbols": [...], "matrix": [[...], ...]},
            "covariance": {"symbols": [...], "matrix": [[...], ...]}
        }

    Raises:
        TransformError: If transformation fails.

    Example:
        >>> results = transform_data()
        >>> print(results["volatility"])
        {'symbols': ['BTCUSDT', ...], 'values': [0.45, ...]}
    """
    logger.info("Starting data transformation")

    # Get storage instance
    storage = get_storage(storage_backend)

    # Load raw data
    logger.info("Loading raw data")
    try:
        raw_data = storage.load_raw(symbols)
    except Exception as e:
        raise TransformError(f"Failed to load raw data: {e}", operation="load") from e

    # Align data by date
    logger.info("Aligning data across symbols")
    symbols_list, dates, prices_matrix = _align_data_by_date(raw_data)

    # Calculate log returns
    logger.info("Calculating log returns")
    returns = calculate_log_returns(prices_matrix)
    # Dates for returns (one less than prices due to differencing)
    returns_dates = dates[1:]

    logger.info(f"Returns shape: {len(returns)} symbols x {len(returns[0])} periods")
    logger.info(f"Returns date range: {returns_dates[0]} to {returns_dates[-1]}")

    # Calculate metrics
    logger.info("Calculating volatility")
    volatility = calculate_volatility(returns)
    for i, symbol in enumerate(symbols_list):
        logger.debug(f"{symbol}: {volatility[i]:.2%} annualized")

    logger.info("Calculating mean returns")
    mean_returns = calculate_mean_returns(returns)
    for i, symbol in enumerate(symbols_list):
        logger.debug(f"{symbol}: {mean_returns[i]:.2%} annualized")

    logger.info("Calculating correlation matrix")
    correlation = calculate_correlation_matrix(returns)

    logger.info("Calculating covariance matrix")
    covariance = calculate_covariance_matrix(returns)

    # Prepare results in storage-compatible format
    results: dict[str, Any] = {
        "returns": {
            "symbols": symbols_list,
            "dates": returns_dates,
            "values": returns,
        },
        "volatility": {
            "symbols": symbols_list,
            "values": volatility,
        },
        "mean_returns": {
            "symbols": symbols_list,
            "values": mean_returns,
        },
        "correlation": {
            "symbols": symbols_list,
            "matrix": correlation,
        },
        "covariance": {
            "symbols": symbols_list,
            "matrix": covariance,
        },
    }

    # Save to storage
    if save:
        logger.info("Saving processed data")
        try:
            storage.save_processed(results["returns"], "returns")
            storage.save_processed(results["volatility"], "volatility")
            storage.save_processed(results["mean_returns"], "mean_returns")
            storage.save_processed(results["correlation"], "correlation")
            storage.save_processed(results["covariance"], "covariance")
        except Exception as e:
            raise TransformError(
                f"Failed to save processed data: {e}", operation="save"
            ) from e

    logger.info("Transformation complete")
    logger.info(f"Symbols: {len(symbols_list)}")
    logger.info(f"Data points per symbol: {len(returns_dates)}")

    return results


def load_processed_metrics(
    storage_backend: str = "parquet",
) -> dict[str, Any]:
    """
    Load previously computed metrics from storage.

    Convenience function to load all processed metrics at once.

    Args:
        storage_backend: Storage backend to use. Defaults to "parquet".

    Returns:
        Dictionary containing all metrics (same structure as transform_data output).

    Raises:
        TransformError: If loading fails.
    """
    storage = get_storage(storage_backend)

    try:
        results = {
            "returns": storage.load_processed("returns"),
            "volatility": storage.load_processed("volatility"),
            "mean_returns": storage.load_processed("mean_returns"),
            "correlation": storage.load_processed("correlation"),
            "covariance": storage.load_processed("covariance"),
        }
        return results
    except Exception as e:
        raise TransformError(
            f"Failed to load processed metrics: {e}", operation="load"
        ) from e


# =============================================================================
# Utility Functions
# =============================================================================


def print_correlation_matrix(correlation: dict[str, Any]) -> None:
    """
    Pretty-print a correlation matrix.

    Args:
        correlation: Correlation data with 'symbols' and 'matrix' keys.
    """
    symbols = correlation["symbols"]
    matrix = correlation["matrix"]

    # Header
    header = "       " + "  ".join(f"{s[:6]:>8}" for s in symbols)
    print(header)
    print("-" * len(header))

    # Rows
    for i, symbol in enumerate(symbols):
        row = f"{symbol[:6]:>6} "
        row += "  ".join(f"{matrix[i][j]:>8.4f}" for j in range(len(symbols)))
        print(row)


def print_covariance_matrix(covariance: dict[str, Any]) -> None:
    """
    Pretty-print a covariance matrix.

    Args:
        covariance: Covariance data with 'symbols' and 'matrix' keys.
    """
    symbols = covariance["symbols"]
    matrix = covariance["matrix"]

    # Header
    header = "       " + "  ".join(f"{s[:6]:>10}" for s in symbols)
    print(header)
    print("-" * len(header))

    # Rows
    for i, symbol in enumerate(symbols):
        row = f"{symbol[:6]:>6} "
        row += "  ".join(f"{matrix[i][j]:>10.6f}" for j in range(len(symbols)))
        print(row)


# =============================================================================
# Main execution (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Testing data transformation...")
    print("=" * 50)

    try:
        # Run transformation
        results = transform_data()

        # Display results
        print("\n" + "=" * 50)
        print("RESULTS SUMMARY")
        print("=" * 50)

        # Volatility
        print("\nAnnualized Volatility:")
        for i, symbol in enumerate(results["volatility"]["symbols"]):
            vol = results["volatility"]["values"][i]
            print(f"  {symbol}: {vol:.2%}")

        # Mean returns
        print("\nAnnualized Mean Returns:")
        for i, symbol in enumerate(results["mean_returns"]["symbols"]):
            ret = results["mean_returns"]["values"][i]
            print(f"  {symbol}: {ret:.2%}")

        # Correlation matrix
        print("\nCorrelation Matrix:")
        print_correlation_matrix(results["correlation"])

        # Covariance matrix
        print("\nAnnualized Covariance Matrix:")
        print_covariance_matrix(results["covariance"])

    except TransformError as e:
        print(f"ERROR: {e.message}")
        if e.operation:
            print(f"  Operation: {e.operation}")
