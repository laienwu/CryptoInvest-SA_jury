"""
Sortino ratio and downside risk metrics module.

Provides risk metrics that focus on downside volatility rather than
total volatility, giving a more accurate picture of harmful risk:

- Downside deviation: volatility of only negative returns
- Sortino ratio: return / downside deviation (penalizes only losses)
- Upside/downside capture ratios vs benchmark
- Gain-to-pain ratio: sum of returns / abs(sum of negative returns)

Output: data/output/sortino.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class SortinoError(Exception):
    """Error during Sortino/downside risk analysis."""

    def __init__(self, message: str, *, operation: str = "sortino") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def downside_deviation(
    returns: list[float],
    mar: float = 0.0,
    periods_per_year: int = 365,
) -> float:
    """
    Annualized downside deviation below minimum acceptable return.

    Args:
        returns: List of periodic returns.
        mar: Minimum acceptable return per period (default 0).
        periods_per_year: For annualization.

    Returns:
        Annualized downside deviation.
    """
    if len(returns) < 2:
        return 0.0

    downside_sq = [max(0, mar - r) ** 2 for r in returns]
    avg_downside_sq = sum(downside_sq) / len(downside_sq)
    return math.sqrt(avg_downside_sq) * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
) -> float:
    """
    Compute Sortino ratio.

    Sortino = (annualized return - risk_free_rate) / downside_deviation

    Args:
        returns: List of periodic returns.
        risk_free_rate: Annualized risk-free rate.
        periods_per_year: For annualization.

    Returns:
        Sortino ratio (0.0 if downside deviation is zero).
    """
    if len(returns) < 2:
        return 0.0

    mean_return = sum(returns) / len(returns)
    ann_return = mean_return * periods_per_year
    rf_per_period = risk_free_rate / periods_per_year

    dd = downside_deviation(returns, mar=rf_per_period, periods_per_year=periods_per_year)
    if dd == 0:
        return 0.0

    return (ann_return - risk_free_rate) / dd


def upside_capture(
    portfolio_returns: list[float],
    benchmark_returns: list[float],
) -> float:
    """
    Upside capture ratio: portfolio performance in up-market periods.

    Ratio > 1 means portfolio captures more upside than benchmark.
    """
    if len(portfolio_returns) != len(benchmark_returns):
        return 0.0

    up_port = [p for p, b in zip(portfolio_returns, benchmark_returns) if b > 0]
    up_bench = [b for b in benchmark_returns if b > 0]

    if not up_bench:
        return 0.0

    port_mean = sum(up_port) / len(up_port) if up_port else 0.0
    bench_mean = sum(up_bench) / len(up_bench)

    if bench_mean == 0:
        return 0.0

    return port_mean / bench_mean


def downside_capture(
    portfolio_returns: list[float],
    benchmark_returns: list[float],
) -> float:
    """
    Downside capture ratio: portfolio performance in down-market periods.

    Ratio < 1 means portfolio loses less than benchmark in down markets.
    """
    if len(portfolio_returns) != len(benchmark_returns):
        return 0.0

    down_port = [p for p, b in zip(portfolio_returns, benchmark_returns) if b < 0]
    down_bench = [b for b in benchmark_returns if b < 0]

    if not down_bench:
        return 0.0

    port_mean = sum(down_port) / len(down_port) if down_port else 0.0
    bench_mean = sum(down_bench) / len(down_bench)

    if bench_mean == 0:
        return 0.0

    return port_mean / bench_mean


def gain_to_pain_ratio(returns: list[float]) -> float:
    """
    Gain-to-pain ratio: sum of all returns / abs(sum of negative returns).

    Higher is better. Measures how much gain per unit of pain.
    """
    if not returns:
        return 0.0

    total = sum(returns)
    pain = abs(sum(r for r in returns if r < 0))

    if pain == 0:
        return 0.0 if total == 0 else float("inf")

    return total / pain


def compute_sortino_metrics(
    returns: list[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
    benchmark_returns: list[float] | None = None,
) -> dict[str, Any]:
    """
    Compute full suite of downside risk metrics.

    Args:
        returns: Portfolio periodic returns.
        risk_free_rate: Annualized risk-free rate.
        periods_per_year: For annualization.
        benchmark_returns: Optional benchmark returns for capture ratios.

    Returns:
        Dict with all downside risk metrics.
    """
    if len(returns) < 2:
        return {
            "sortino_ratio": 0.0,
            "downside_deviation": 0.0,
            "upside_deviation": 0.0,
            "gain_to_pain": 0.0,
            "upside_capture": None,
            "downside_capture": None,
            "n_periods": len(returns),
            "n_negative": 0,
            "n_positive": 0,
            "worst_return": 0.0,
            "best_return": 0.0,
            "periods_per_year": periods_per_year,
            "risk_free_rate": risk_free_rate,
        }

    rf_per_period = risk_free_rate / periods_per_year

    dd = downside_deviation(returns, mar=rf_per_period, periods_per_year=periods_per_year)
    sr = sortino_ratio(returns, risk_free_rate, periods_per_year)
    gtp = gain_to_pain_ratio(returns)

    # Upside deviation (for asymmetry comparison)
    upside_sq = [max(0, r - rf_per_period) ** 2 for r in returns]
    ud = math.sqrt(sum(upside_sq) / len(upside_sq)) * math.sqrt(periods_per_year)

    n_neg = sum(1 for r in returns if r < 0)
    n_pos = sum(1 for r in returns if r > 0)

    result: dict[str, Any] = {
        "sortino_ratio": round(sr, 4),
        "downside_deviation": round(dd, 6),
        "upside_deviation": round(ud, 6),
        "gain_to_pain": round(gtp, 4),
        "upside_capture": None,
        "downside_capture": None,
        "n_periods": len(returns),
        "n_negative": n_neg,
        "n_positive": n_pos,
        "worst_return": round(min(returns), 6),
        "best_return": round(max(returns), 6),
        "periods_per_year": periods_per_year,
        "risk_free_rate": risk_free_rate,
    }

    if benchmark_returns is not None and len(benchmark_returns) == len(returns):
        result["upside_capture"] = round(upside_capture(returns, benchmark_returns), 4)
        result["downside_capture"] = round(downside_capture(returns, benchmark_returns), 4)

    return result


def analyze_sortino(
    portfolio_key: str = "weights",
    benchmark_symbol: str = "BTCUSDT",
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run Sortino/downside risk analysis on portfolio.

    Args:
        portfolio_key: Storage key for portfolio weights.
        benchmark_symbol: Benchmark for capture ratios.
        risk_free_rate: Annualized risk-free rate.
        periods_per_year: For annualization.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Sortino metrics including capture ratios.

    Raises:
        SortinoError: If data is missing.
    """
    if storage is None:
        storage = get_storage()

    try:
        portfolio = storage.load_output(portfolio_key)
    except (StorageError, FileNotFoundError) as e:
        raise SortinoError(
            f"Portfolio not found (key={portfolio_key})", operation="load"
        ) from e

    weights = portfolio.get("weights", {})
    if not weights:
        raise SortinoError("Portfolio has no weights", operation="validate")

    try:
        returns_data = storage.load_processed("returns")
    except (StorageError, FileNotFoundError) as e:
        raise SortinoError("Returns data not found", operation="load") from e

    # Build portfolio return series
    symbols = list(weights.keys())
    returns_by_symbol: dict[str, list[float]] = {}
    for symbol in symbols + [benchmark_symbol]:
        symbol_returns = returns_data.get(symbol)
        if symbol_returns is None:
            continue
        if isinstance(symbol_returns, list):
            returns_by_symbol[symbol] = symbol_returns
        elif isinstance(symbol_returns, dict) and "values" in symbol_returns:
            returns_by_symbol[symbol] = symbol_returns["values"]

    # Weighted portfolio returns
    if not any(s in returns_by_symbol for s in symbols):
        raise SortinoError("No return data for portfolio symbols", operation="validate")

    first_symbol = next(s for s in symbols if s in returns_by_symbol)
    n = len(returns_by_symbol[first_symbol])
    portfolio_returns: list[float] = []
    for i in range(n):
        r = sum(
            weights[s] * returns_by_symbol[s][i]
            for s in symbols
            if s in returns_by_symbol and i < len(returns_by_symbol[s])
        )
        portfolio_returns.append(r)

    benchmark_returns = returns_by_symbol.get(benchmark_symbol)

    metrics = compute_sortino_metrics(
        portfolio_returns, risk_free_rate, periods_per_year, benchmark_returns
    )

    result: dict[str, Any] = {
        "portfolio_key": portfolio_key,
        "benchmark": benchmark_symbol,
        **metrics,
    }

    if save:
        storage.save_output(result, "sortino")
        logger.info(
            "Sortino: %.4f, downside dev: %.6f, gain/pain: %.4f",
            metrics["sortino_ratio"],
            metrics["downside_deviation"],
            metrics["gain_to_pain"],
        )

    return result
