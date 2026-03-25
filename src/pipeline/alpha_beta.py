"""
Alpha/beta analysis module.

Computes CAPM-style alpha and beta of the portfolio versus one or more
benchmarks (e.g. BTC for crypto, SPY for traditional).

- Beta: sensitivity of portfolio returns to benchmark returns
- Alpha: excess return not explained by market exposure
- R²: fraction of portfolio variance explained by benchmark
- Tracking error: volatility of active returns (portfolio − benchmark)
- Information ratio: alpha / tracking error

Output: data/output/alpha_beta.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class AlphaBetaError(Exception):
    """Error during alpha/beta analysis."""

    def __init__(self, message: str, *, operation: str = "alpha_beta") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def _mean(values: list[float]) -> float:
    """Arithmetic mean."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _covariance(xs: list[float], ys: list[float]) -> float:
    """Sample covariance between two series."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)


def _variance(values: list[float]) -> float:
    """Sample variance."""
    n = len(values)
    if n < 2:
        return 0.0
    m = _mean(values)
    return sum((v - m) ** 2 for v in values) / (n - 1)


def compute_alpha_beta(
    portfolio_returns: list[float],
    benchmark_returns: list[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
) -> dict[str, Any]:
    """
    Compute CAPM alpha and beta of portfolio vs benchmark.

    Args:
        portfolio_returns: List of periodic portfolio returns.
        benchmark_returns: List of periodic benchmark returns (same length).
        risk_free_rate: Annualized risk-free rate.
        periods_per_year: Number of periods per year (365 for daily crypto).

    Returns:
        Dict with beta, alpha (annualized), R², tracking error, information ratio.

    Raises:
        AlphaBetaError: If inputs are invalid.
    """
    if len(portfolio_returns) != len(benchmark_returns):
        raise AlphaBetaError(
            "Portfolio and benchmark return series must have equal length",
            operation="validate",
        )
    if len(portfolio_returns) < 2:
        raise AlphaBetaError(
            "Need at least 2 return observations",
            operation="validate",
        )

    rf_per_period = risk_free_rate / periods_per_year

    # Excess returns over risk-free
    excess_port = [r - rf_per_period for r in portfolio_returns]
    excess_bench = [r - rf_per_period for r in benchmark_returns]

    # Beta = Cov(Rp, Rb) / Var(Rb)
    var_bench = _variance(excess_bench)
    if var_bench == 0:
        beta = 0.0
    else:
        beta = _covariance(excess_port, excess_bench) / var_bench

    # Alpha (annualized) = (mean_excess_port - beta * mean_excess_bench) * periods
    mean_excess_port = _mean(excess_port)
    mean_excess_bench = _mean(excess_bench)
    alpha_periodic = mean_excess_port - beta * mean_excess_bench
    alpha_annual = alpha_periodic * periods_per_year

    # R² = correlation² = (Cov / (std_p * std_b))²
    var_port = _variance(excess_port)
    if var_port > 0 and var_bench > 0:
        corr = _covariance(excess_port, excess_bench) / (
            math.sqrt(var_port) * math.sqrt(var_bench)
        )
        r_squared = corr ** 2
    else:
        r_squared = 0.0

    # Tracking error = std(portfolio - benchmark) annualized
    active_returns = [p - b for p, b in zip(portfolio_returns, benchmark_returns)]
    tracking_error = math.sqrt(_variance(active_returns)) * math.sqrt(periods_per_year)

    # Information ratio = alpha / tracking_error
    info_ratio = alpha_annual / tracking_error if tracking_error > 0 else 0.0

    return {
        "beta": round(beta, 4),
        "alpha_annual": round(alpha_annual, 6),
        "r_squared": round(r_squared, 4),
        "tracking_error": round(tracking_error, 6),
        "information_ratio": round(info_ratio, 4),
        "n_periods": len(portfolio_returns),
        "periods_per_year": periods_per_year,
        "risk_free_rate": risk_free_rate,
    }


def _portfolio_return_series(
    weights: dict[str, float],
    returns_by_symbol: dict[str, list[float]],
) -> list[float]:
    """
    Compute weighted portfolio return series from per-asset returns.

    All return series must be the same length.
    """
    symbols = list(weights.keys())
    if not symbols:
        return []

    n = len(returns_by_symbol.get(symbols[0], []))
    series: list[float] = []

    for i in range(n):
        r = 0.0
        for s in symbols:
            asset_returns = returns_by_symbol.get(s, [])
            if i < len(asset_returns):
                r += weights[s] * asset_returns[i]
        series.append(r)

    return series


def analyze_alpha_beta(
    portfolio_key: str = "weights",
    benchmark_symbol: str = "BTCUSDT",
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run alpha/beta analysis of portfolio vs benchmark.

    Loads portfolio weights and per-asset returns from storage,
    constructs weighted portfolio return series, then regresses
    against the benchmark return series.

    Args:
        portfolio_key: Storage key for portfolio weights.
        benchmark_symbol: Symbol to use as benchmark.
        risk_free_rate: Annualized risk-free rate.
        periods_per_year: Periods per year for annualization.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Alpha/beta analysis results.

    Raises:
        AlphaBetaError: If data is missing or insufficient.
    """
    if storage is None:
        storage = get_storage()

    # Load portfolio weights
    try:
        portfolio = storage.load_output(portfolio_key)
    except (StorageError, FileNotFoundError) as e:
        raise AlphaBetaError(
            f"Portfolio not found (key={portfolio_key})", operation="load"
        ) from e

    weights = portfolio.get("weights", {})
    if not weights:
        raise AlphaBetaError("Portfolio has no weights", operation="validate")

    # Load returns
    try:
        returns_data = storage.load_processed("returns")
    except (StorageError, FileNotFoundError) as e:
        raise AlphaBetaError(
            "Returns data not found", operation="load"
        ) from e

    # Build per-asset return dict
    returns_by_symbol: dict[str, list[float]] = {}
    for symbol in list(weights.keys()) + [benchmark_symbol]:
        symbol_returns = returns_data.get(symbol)
        if symbol_returns is None:
            if symbol == benchmark_symbol:
                raise AlphaBetaError(
                    f"Benchmark {benchmark_symbol} not found in returns data",
                    operation="validate",
                )
            continue
        if isinstance(symbol_returns, list):
            returns_by_symbol[symbol] = symbol_returns
        elif isinstance(symbol_returns, dict) and "values" in symbol_returns:
            returns_by_symbol[symbol] = symbol_returns["values"]

    # Portfolio return series
    portfolio_returns = _portfolio_return_series(weights, returns_by_symbol)
    benchmark_returns = returns_by_symbol.get(benchmark_symbol, [])

    # Align lengths (take the shorter)
    min_len = min(len(portfolio_returns), len(benchmark_returns))
    if min_len < 2:
        raise AlphaBetaError(
            "Insufficient return data for regression", operation="validate"
        )
    portfolio_returns = portfolio_returns[:min_len]
    benchmark_returns = benchmark_returns[:min_len]

    analysis = compute_alpha_beta(
        portfolio_returns, benchmark_returns, risk_free_rate, periods_per_year
    )

    result: dict[str, Any] = {
        "benchmark": benchmark_symbol,
        "portfolio_key": portfolio_key,
        **analysis,
    }

    if save:
        storage.save_output(result, "alpha_beta")
        logger.info(
            "Alpha/beta: β=%.4f, α=%.6f, R²=%.4f, IR=%.4f",
            analysis["beta"],
            analysis["alpha_annual"],
            analysis["r_squared"],
            analysis["information_ratio"],
        )

    return result
