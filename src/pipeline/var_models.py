"""
Value-at-Risk comparison module.

Implements three VaR estimation methods for portfolio risk measurement:

1. Historical VaR/CVaR — empirical percentile of observed returns
2. Parametric VaR/CVaR — assumes normal distribution (mean + std)
3. Cornish-Fisher VaR/CVaR — adjusts for skewness and kurtosis

Each method returns loss as a positive number (convention: VaR = 0.05 means
a 5% loss at the given confidence level).

Output: data/output/var_analysis.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class VaRError(Exception):
    """Error during Value-at-Risk computation."""

    def __init__(self, message: str, *, operation: str = "var") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


# =============================================================================
# Internal helpers
# =============================================================================


def _norm_ppf(p: float) -> float:
    """
    Inverse cumulative normal distribution (quantile function).

    Uses the rational approximation from Abramowitz & Stegun (formula 26.2.23).
    Accurate to ~4.5e-4 for the central region.

    Args:
        p: Probability in (0, 1).

    Returns:
        z such that P(Z <= z) = p for standard normal Z.

    Raises:
        VaRError: If p is outside (0, 1).
    """
    if p <= 0.0 or p >= 1.0:
        raise VaRError(f"p must be in (0, 1), got {p}", operation="norm_ppf")

    # Abramowitz & Stegun constants
    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308

    if p < 0.5:
        t = math.sqrt(-2.0 * math.log(p))
        z = -(t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t))
    else:
        t = math.sqrt(-2.0 * math.log(1.0 - p))
        z = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)

    return z


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _skewness(returns: list[float]) -> float:
    """
    Sample skewness (Fisher's definition).

    Args:
        returns: List of observed returns.

    Returns:
        Skewness coefficient. Zero for symmetric distributions.

    Raises:
        VaRError: If fewer than 3 observations.
    """
    n = len(returns)
    if n < 3:
        raise VaRError(
            f"Need >= 3 observations for skewness, got {n}",
            operation="skewness",
        )

    mean = sum(returns) / n
    m2 = sum((r - mean) ** 2 for r in returns) / n
    m3 = sum((r - mean) ** 3 for r in returns) / n

    if m2 == 0.0:
        return 0.0

    return float(m3 / (m2 ** 1.5))


def _excess_kurtosis(returns: list[float]) -> float:
    """
    Sample excess kurtosis (subtract 3 so normal = 0).

    Args:
        returns: List of observed returns.

    Returns:
        Excess kurtosis. Zero for normal distributions, positive for fat tails.

    Raises:
        VaRError: If fewer than 4 observations.
    """
    n = len(returns)
    if n < 4:
        raise VaRError(
            f"Need >= 4 observations for kurtosis, got {n}",
            operation="kurtosis",
        )

    mean = sum(returns) / n
    m2 = sum((r - mean) ** 2 for r in returns) / n
    m4 = sum((r - mean) ** 4 for r in returns) / n

    if m2 == 0.0:
        return 0.0

    return (m4 / (m2 ** 2)) - 3.0


# =============================================================================
# Historical VaR / CVaR
# =============================================================================


def historical_var(returns: list[float], confidence: float = 0.95) -> float:
    """
    Historical Value-at-Risk at the given confidence level.

    Sorts returns and picks the (1 - confidence) percentile.

    Args:
        returns: List of observed returns.
        confidence: Confidence level (e.g. 0.95 for 95%).

    Returns:
        VaR as a positive number (loss magnitude).

    Raises:
        VaRError: If returns is empty.
    """
    if not returns:
        raise VaRError("Returns list is empty", operation="historical_var")

    sorted_returns = sorted(returns)
    index = int(math.floor((1.0 - confidence) * len(sorted_returns)))
    # Clamp to valid range
    index = max(0, min(index, len(sorted_returns) - 1))

    return -sorted_returns[index]


def historical_cvar(returns: list[float], confidence: float = 0.95) -> float:
    """
    Historical Conditional Value-at-Risk (Expected Shortfall).

    Average of all returns at or below the VaR threshold.

    Args:
        returns: List of observed returns.
        confidence: Confidence level.

    Returns:
        CVaR as a positive number.

    Raises:
        VaRError: If returns is empty.
    """
    if not returns:
        raise VaRError("Returns list is empty", operation="historical_cvar")

    sorted_returns = sorted(returns)
    cutoff_index = int(math.floor((1.0 - confidence) * len(sorted_returns)))
    cutoff_index = max(1, min(cutoff_index, len(sorted_returns)))

    tail = sorted_returns[:cutoff_index]
    avg_tail = sum(tail) / len(tail)

    return -avg_tail


# =============================================================================
# Parametric (Normal) VaR / CVaR
# =============================================================================


def parametric_var(
    mean: float, std: float, confidence: float = 0.95
) -> float:
    """
    Parametric VaR assuming normal returns.

    VaR = -(mean - z * std) where z = norm_ppf(confidence).

    Args:
        mean: Expected return (per period).
        std: Standard deviation of returns (per period).
        confidence: Confidence level.

    Returns:
        VaR as a positive number.
    """
    z = _norm_ppf(confidence)
    return -(mean - z * std)


def parametric_cvar(
    mean: float, std: float, confidence: float = 0.95
) -> float:
    """
    Parametric CVaR (Expected Shortfall) assuming normal returns.

    CVaR = -(mean - std * phi(z) / (1 - confidence))

    where phi is the standard normal PDF and z = norm_ppf(confidence).

    Args:
        mean: Expected return (per period).
        std: Standard deviation of returns (per period).
        confidence: Confidence level.

    Returns:
        CVaR as a positive number.
    """
    z = _norm_ppf(confidence)
    alpha = 1.0 - confidence
    return -(mean - std * _norm_pdf(z) / alpha)


# =============================================================================
# Cornish-Fisher VaR / CVaR
# =============================================================================


def cornish_fisher_var(
    returns: list[float], confidence: float = 0.95
) -> float:
    """
    Cornish-Fisher VaR adjusting for skewness and kurtosis.

    Adjusts the normal z-score:
        z_cf = z + (z^2-1)*S/6 + (z^3-3z)*K/24 - (2z^3-5z)*S^2/36

    where S = skewness, K = excess kurtosis.

    Args:
        returns: List of observed returns (need >= 4).
        confidence: Confidence level.

    Returns:
        VaR as a positive number.

    Raises:
        VaRError: If insufficient observations.
    """
    if len(returns) < 4:
        raise VaRError(
            f"Need >= 4 observations for Cornish-Fisher, got {len(returns)}",
            operation="cornish_fisher_var",
        )

    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(variance)

    if std == 0.0:
        return -mean

    s = _skewness(returns)
    k = _excess_kurtosis(returns)
    z = _norm_ppf(confidence)

    z_cf = (
        z
        + (z * z - 1.0) * s / 6.0
        + (z * z * z - 3.0 * z) * k / 24.0
        - (2.0 * z * z * z - 5.0 * z) * s * s / 36.0
    )

    return -(mean - z_cf * std)


def cornish_fisher_cvar(
    returns: list[float], confidence: float = 0.95
) -> float:
    """
    Cornish-Fisher CVaR: average of returns below the CF-VaR threshold.

    Uses the Cornish-Fisher adjusted VaR as the cutoff, then averages
    all returns that fall below -VaR.

    Args:
        returns: List of observed returns (need >= 4).
        confidence: Confidence level.

    Returns:
        CVaR as a positive number.

    Raises:
        VaRError: If insufficient observations.
    """
    var = cornish_fisher_var(returns, confidence)
    threshold = -var  # Negative value (loss threshold)

    tail = [r for r in returns if r <= threshold]
    if not tail:
        # Fall back to VaR if no returns below threshold
        return var

    return -sum(tail) / len(tail)


# =============================================================================
# Comparison
# =============================================================================


def compare_var_models(
    returns: list[float], confidence: float = 0.95
) -> dict[str, Any]:
    """
    Run all three VaR/CVaR methods and return a comparison dict.

    Args:
        returns: List of observed returns.
        confidence: Confidence level.

    Returns:
        Dict with keys: historical, parametric, cornish_fisher,
        confidence, n_observations.

    Raises:
        VaRError: If returns has insufficient data for any method.
    """
    if len(returns) < 4:
        raise VaRError(
            f"Need >= 4 observations, got {len(returns)}",
            operation="compare",
        )

    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(variance)

    return {
        "historical": {
            "var": round(historical_var(returns, confidence), 6),
            "cvar": round(historical_cvar(returns, confidence), 6),
        },
        "parametric": {
            "var": round(parametric_var(mean, std, confidence), 6),
            "cvar": round(parametric_cvar(mean, std, confidence), 6),
        },
        "cornish_fisher": {
            "var": round(cornish_fisher_var(returns, confidence), 6),
            "cvar": round(cornish_fisher_cvar(returns, confidence), 6),
        },
        "confidence": confidence,
        "n_observations": len(returns),
    }


# =============================================================================
# Full analysis (storage-aware)
# =============================================================================


def analyze_var(
    confidence: float = 0.95,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run VaR analysis on the current portfolio.

    Loads weights and per-asset returns from storage, constructs a weighted
    portfolio return series, runs all three VaR methods, and adds per-asset
    VaR breakdown.

    Args:
        confidence: Confidence level for VaR.
        storage: Storage backend. Defaults to configured backend.
        save: Whether to save results to storage.

    Returns:
        Dict with portfolio VaR comparison, per-asset VaR, and metadata.

    Raises:
        VaRError: If portfolio or return data is missing.
    """
    if storage is None:
        storage = get_storage()

    # Load portfolio weights
    try:
        portfolio = storage.load_output("weights")
    except (StorageError, FileNotFoundError) as e:
        raise VaRError("Portfolio weights not found", operation="load") from e

    weights = portfolio.get("weights", {})
    if not weights:
        raise VaRError("Portfolio has no weights", operation="validate")

    # Load returns
    try:
        returns_data = storage.load_processed("returns")
    except (StorageError, FileNotFoundError) as e:
        raise VaRError("Returns data not found", operation="load") from e

    # Extract per-asset return lists
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

    if not any(s in returns_by_symbol for s in symbols):
        raise VaRError(
            "No return data for portfolio symbols", operation="validate"
        )

    # Build weighted portfolio return series
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

    # Portfolio-level comparison
    portfolio_var = compare_var_models(portfolio_returns, confidence)

    # Per-asset VaR breakdown
    asset_var: list[dict[str, Any]] = []
    for symbol in symbols:
        if symbol not in returns_by_symbol:
            continue
        s_returns = returns_by_symbol[symbol]
        if len(s_returns) < 4:
            continue
        s_mean = sum(s_returns) / len(s_returns)
        s_var = sum((r - s_mean) ** 2 for r in s_returns) / (len(s_returns) - 1)
        s_std = math.sqrt(s_var)
        asset_var.append({
            "symbol": symbol,
            "weight": round(weights[symbol], 6),
            "historical_var": round(historical_var(s_returns, confidence), 6),
            "parametric_var": round(parametric_var(s_mean, s_std, confidence), 6),
            "cornish_fisher_var": round(cornish_fisher_var(s_returns, confidence), 6),
        })

    result: dict[str, Any] = {
        "confidence": confidence,
        "n_observations": len(portfolio_returns),
        "portfolio": portfolio_var,
        "asset_var": asset_var,
    }

    if save:
        storage.save_output(result, "var_analysis")
        logger.info(
            "VaR analysis: hist=%.4f, param=%.4f, CF=%.4f (%.0f%% confidence)",
            portfolio_var["historical"]["var"],
            portfolio_var["parametric"]["var"],
            portfolio_var["cornish_fisher"]["var"],
            confidence * 100,
        )

    return result
