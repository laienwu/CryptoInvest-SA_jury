"""
Tail risk analysis module — higher moments and distribution shape metrics.

Provides metrics beyond mean and variance to characterize return
distribution tails:

- Skewness: asymmetry of the return distribution
- Excess kurtosis: tail heaviness relative to normal
- Jarque-Bera statistic: normality test
- Omega ratio: gain/loss ratio above a threshold
- Calmar ratio: annualized return / max drawdown
- Max drawdown: largest peak-to-trough decline

Output: data/output/tail_risk.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class TailRiskError(Exception):
    """Error during tail risk analysis."""

    def __init__(self, message: str, *, operation: str = "tail_risk") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def skewness(returns: list[float]) -> float:
    """
    Sample skewness of a return series.

    Uses the adjusted Fisher-Pearson coefficient:
    n / ((n-1)(n-2)) * sum(((x - mean) / std)^3)

    Args:
        returns: List of periodic returns.

    Returns:
        Sample skewness. Positive = right-skewed, negative = left-skewed.

    Raises:
        TailRiskError: If fewer than 3 observations.
    """
    n = len(returns)
    if n < 3:
        raise TailRiskError(
            f"Need at least 3 observations, got {n}", operation="skewness"
        )

    mean = sum(returns) / n
    variance = sum((x - mean) ** 2 for x in returns) / (n - 1)
    std = math.sqrt(variance)

    if std == 0:
        return 0.0

    adjustment = n / ((n - 1) * (n - 2))
    m3 = sum(((x - mean) / std) ** 3 for x in returns)

    return adjustment * m3


def excess_kurtosis(returns: list[float]) -> float:
    """
    Sample excess kurtosis of a return series.

    Uses the bias-corrected formula and subtracts 3 so that
    a normal distribution has excess kurtosis of ~0.

    Args:
        returns: List of periodic returns.

    Returns:
        Excess kurtosis. Positive = heavy tails, negative = light tails.

    Raises:
        TailRiskError: If fewer than 4 observations.
    """
    n = len(returns)
    if n < 4:
        raise TailRiskError(
            f"Need at least 4 observations, got {n}", operation="kurtosis"
        )

    mean = sum(returns) / n
    variance = sum((x - mean) ** 2 for x in returns) / (n - 1)
    std = math.sqrt(variance)

    if std == 0:
        return 0.0

    m4_sum = sum(((x - mean) / std) ** 4 for x in returns)

    # Bias-corrected excess kurtosis
    term1 = (n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3))
    term2 = 3 * ((n - 1) ** 2) / ((n - 2) * (n - 3))

    return term1 * m4_sum - term2


def jarque_bera_statistic(returns: list[float]) -> dict[str, Any]:
    """
    Jarque-Bera test for normality.

    JB = (n/6) * (S^2 + K^2/4) where S = skewness, K = excess kurtosis.
    Under H0 (normal), JB ~ chi-squared(2). Critical value at 95% is 5.99.

    Args:
        returns: List of periodic returns.

    Returns:
        Dict with 'statistic' (float) and 'is_normal' (bool).

    Raises:
        TailRiskError: If fewer than 4 observations (kurtosis requirement).
    """
    n = len(returns)
    if n < 4:
        raise TailRiskError(
            f"Need at least 4 observations, got {n}", operation="jarque_bera"
        )

    s = skewness(returns)
    k = excess_kurtosis(returns)

    jb = (n / 6.0) * (s ** 2 + (k ** 2) / 4.0)
    chi2_95 = 5.991  # chi-squared(2) at 95% confidence

    return {
        "statistic": round(jb, 6),
        "is_normal": jb <= chi2_95,
    }


def omega_ratio(returns: list[float], threshold: float = 0.0) -> float:
    """
    Omega ratio: probability-weighted gains / probability-weighted losses.

    Sum of returns above threshold / absolute sum of returns below threshold.

    Args:
        returns: List of periodic returns.
        threshold: Return threshold (default 0).

    Returns:
        Omega ratio. Higher is better. Returns 0.0 if no losses,
        inf if all gains, 0.0 if empty.
    """
    if not returns:
        return 0.0

    gains = sum(r - threshold for r in returns if r > threshold)
    losses = sum(threshold - r for r in returns if r < threshold)

    if losses == 0:
        return float("inf") if gains > 0 else 0.0

    return gains / losses


def max_drawdown(returns: list[float]) -> float:
    """
    Maximum drawdown from a return series.

    Computes cumulative wealth and finds the largest peak-to-trough decline.

    Args:
        returns: List of periodic returns.

    Returns:
        Max drawdown as a positive fraction (e.g., 0.25 = 25% drawdown).
        Returns 0.0 if no drawdown occurs.
    """
    if not returns:
        return 0.0

    # Build cumulative wealth
    wealth = 1.0
    peak = 1.0
    max_dd = 0.0

    for r in returns:
        wealth *= (1.0 + r)
        if wealth > peak:
            peak = wealth
        dd = (peak - wealth) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    return max_dd


def calmar_ratio(
    returns: list[float],
    annualized_return: float | None = None,
    trading_days: int = 365,
) -> float:
    """
    Calmar ratio: annualized return / max drawdown.

    Args:
        returns: List of periodic returns.
        annualized_return: Pre-computed annualized return. If None,
            computed from mean daily return × trading_days.
        trading_days: Number of trading days per year for annualization.

    Returns:
        Calmar ratio. Returns 0.0 if max drawdown is zero.
    """
    if not returns:
        return 0.0

    mdd = max_drawdown(returns)
    if mdd == 0:
        return 0.0

    if annualized_return is None:
        mean_return = sum(returns) / len(returns)
        annualized_return = mean_return * trading_days

    return annualized_return / mdd


def compute_tail_metrics(
    returns: list[float],
    symbol: str = "portfolio",
) -> dict[str, Any]:
    """
    Compute all tail risk metrics for a single return series.

    Args:
        returns: List of periodic returns.
        symbol: Identifier for the series.

    Returns:
        Dict with symbol, skewness, excess_kurtosis, jarque_bera,
        is_normal, omega_ratio, calmar_ratio, max_drawdown, n_observations.
    """
    n = len(returns)

    # Need at least 4 for kurtosis/JB
    if n < 4:
        return {
            "symbol": symbol,
            "skewness": 0.0,
            "excess_kurtosis": 0.0,
            "jarque_bera": 0.0,
            "is_normal": True,
            "omega_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
            "n_observations": n,
        }

    s = skewness(returns)
    k = excess_kurtosis(returns)
    jb = jarque_bera_statistic(returns)
    omega = omega_ratio(returns)
    mdd = max_drawdown(returns)
    calmar = calmar_ratio(returns)

    return {
        "symbol": symbol,
        "skewness": round(s, 6),
        "excess_kurtosis": round(k, 6),
        "jarque_bera": jb["statistic"],
        "is_normal": jb["is_normal"],
        "omega_ratio": round(omega, 6),
        "calmar_ratio": round(calmar, 6),
        "max_drawdown": round(mdd, 6),
        "n_observations": n,
    }


def analyze_tail_risk(
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run tail risk analysis on portfolio and per-asset returns.

    Loads portfolio weights and per-asset return series from storage,
    computes weighted portfolio returns, and calculates tail metrics
    for both the portfolio and each individual asset.

    Args:
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Dict with portfolio_metrics, per_asset metrics, n_assets, method.

    Raises:
        TailRiskError: If portfolio or returns data is missing.
    """
    if storage is None:
        storage = get_storage()

    # Load portfolio weights
    try:
        portfolio = storage.load_output("weights")
    except (StorageError, FileNotFoundError) as e:
        raise TailRiskError(
            "Portfolio weights not found", operation="load"
        ) from e

    weights = portfolio.get("weights", {})
    if not weights:
        raise TailRiskError("Portfolio has no weights", operation="validate")

    # Load returns data
    try:
        returns_data = storage.load_processed("returns")
    except (StorageError, FileNotFoundError) as e:
        raise TailRiskError("Returns data not found", operation="load") from e

    # Extract per-asset return series
    symbols = list(weights.keys())
    returns_by_symbol: dict[str, list[float]] = {}

    for symbol in symbols:
        symbol_returns = returns_data.get(symbol)
        if symbol_returns is None:
            continue
        if isinstance(symbol_returns, list):
            returns_by_symbol[symbol] = symbol_returns
        elif isinstance(symbol_returns, dict) and "values" in symbol_returns:
            returns_by_symbol[symbol] = symbol_returns["values"]

    if not returns_by_symbol:
        raise TailRiskError(
            "No return data for portfolio symbols", operation="validate"
        )

    # Build weighted portfolio return series
    first_symbol = next(iter(returns_by_symbol))
    n_periods = len(returns_by_symbol[first_symbol])
    portfolio_returns: list[float] = []
    for i in range(n_periods):
        r = sum(
            weights[s] * returns_by_symbol[s][i]
            for s in symbols
            if s in returns_by_symbol and i < len(returns_by_symbol[s])
        )
        portfolio_returns.append(r)

    # Compute portfolio-level tail metrics
    portfolio_metrics = compute_tail_metrics(portfolio_returns, symbol="portfolio")

    # Compute per-asset tail metrics
    per_asset: list[dict[str, Any]] = []
    for symbol in symbols:
        if symbol in returns_by_symbol:
            asset_metrics = compute_tail_metrics(
                returns_by_symbol[symbol], symbol=symbol
            )
            per_asset.append(asset_metrics)

    result: dict[str, Any] = {
        "portfolio_metrics": portfolio_metrics,
        "per_asset": per_asset,
        "n_assets": len(per_asset),
        "method": "tail_risk",
    }

    if save:
        storage.save_output(result, "tail_risk")
        logger.info(
            "Tail risk: skew=%.4f, kurtosis=%.4f, max_dd=%.4f, %d assets",
            portfolio_metrics["skewness"],
            portfolio_metrics["excess_kurtosis"],
            portfolio_metrics["max_drawdown"],
            len(per_asset),
        )

    return result
