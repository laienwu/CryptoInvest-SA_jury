"""
Pair trading / cointegration analysis module.

Finds cointegrated pairs using the Engle-Granger two-step method and
computes spread z-scores for mean-reversion trading signals.

Steps:
1. Build price-like series from cumulative returns per asset
2. Test all pairwise combinations for cointegration (Engle-Granger)
3. For cointegrated pairs, compute spread and rolling z-score signals

Output: data/output/pairs_analysis.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)

# ADF critical value at 5% significance for 2-variable Engle-Granger test
_ADF_CRITICAL_5PCT = -3.34


class PairsError(Exception):
    """Error during pair trading analysis."""

    def __init__(self, message: str, *, operation: str = "pairs") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


# =============================================================================
# Statistical helpers (pure Python, no numpy/pandas)
# =============================================================================


def _ols_simple(
    y: list[float], x: list[float]
) -> tuple[float, float, list[float]]:
    """
    Simple OLS regression: y = alpha + beta * x + epsilon.

    Args:
        y: Dependent variable series.
        x: Independent variable series (same length as y).

    Returns:
        Tuple of (alpha, beta, residuals).

    Raises:
        PairsError: If inputs are invalid or singular.
    """
    n = len(y)
    if n != len(x):
        raise PairsError(
            "OLS input series must have equal length", operation="ols"
        )
    if n < 3:
        raise PairsError(
            "OLS requires at least 3 observations", operation="ols"
        )

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    ss_xx = sum((xi - mean_x) ** 2 for xi in x)
    if ss_xx == 0.0:
        raise PairsError(
            "OLS independent variable has zero variance", operation="ols"
        )

    ss_xy = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))

    beta = ss_xy / ss_xx
    alpha = mean_y - beta * mean_x

    residuals = [yi - alpha - beta * xi for yi, xi in zip(y, x)]
    return alpha, beta, residuals


def _adf_statistic(series: list[float]) -> float:
    """
    Simplified Augmented Dickey-Fuller test statistic.

    Regresses diff(series) on lag(series) without augmentation lags.
    ADF stat = beta_hat / se(beta_hat).
    More negative values indicate stationarity / cointegration.

    Args:
        series: Time series to test for unit root.

    Returns:
        ADF t-statistic (negative = more likely stationary).

    Raises:
        PairsError: If series is too short.
    """
    n = len(series)
    if n < 4:
        raise PairsError(
            "ADF test requires at least 4 observations", operation="adf"
        )

    # diff(series) = series[t] - series[t-1]
    dy = [series[i] - series[i - 1] for i in range(1, n)]
    # lag(series) = series[t-1]
    y_lag = [series[i] for i in range(n - 1)]

    m = len(dy)
    mean_lag = sum(y_lag) / m
    mean_dy = sum(dy) / m

    ss_lag_lag = sum((yl - mean_lag) ** 2 for yl in y_lag)
    if ss_lag_lag == 0.0:
        return 0.0

    ss_lag_dy = sum(
        (yl - mean_lag) * (d - mean_dy) for yl, d in zip(y_lag, dy)
    )

    beta_hat = ss_lag_dy / ss_lag_lag

    # Residuals of the ADF regression
    alpha_hat = mean_dy - beta_hat * mean_lag
    residuals = [
        d - alpha_hat - beta_hat * yl for d, yl in zip(dy, y_lag)
    ]

    # Standard error of beta_hat
    ssr = sum(r ** 2 for r in residuals)
    dof = m - 2
    if dof <= 0:
        return 0.0

    sigma2 = ssr / dof
    se_beta = math.sqrt(sigma2 / ss_lag_lag) if ss_lag_lag > 0 else 0.0

    if se_beta == 0.0:
        return 0.0

    return beta_hat / se_beta


def engle_granger_test(
    series_a: list[float], series_b: list[float]
) -> dict[str, Any]:
    """
    Engle-Granger two-step cointegration test.

    Step 1: OLS regression of A on B to get residuals.
    Step 2: ADF test on residuals.

    Args:
        series_a: Price-like series for asset A.
        series_b: Price-like series for asset B (same length).

    Returns:
        Dict with adf_statistic, hedge_ratio, is_cointegrated.

    Raises:
        PairsError: If inputs are invalid.
    """
    if len(series_a) != len(series_b):
        raise PairsError(
            "Series must have equal length for cointegration test",
            operation="engle_granger",
        )
    if len(series_a) < 4:
        raise PairsError(
            "Need at least 4 observations for cointegration test",
            operation="engle_granger",
        )

    _alpha, beta, residuals = _ols_simple(series_a, series_b)
    adf_stat = _adf_statistic(residuals)

    return {
        "adf_statistic": round(adf_stat, 4),
        "hedge_ratio": round(beta, 6),
        "is_cointegrated": adf_stat < _ADF_CRITICAL_5PCT,
    }


def compute_spread(
    series_a: list[float], series_b: list[float], hedge_ratio: float
) -> list[float]:
    """
    Compute the spread between two series.

    spread = A - hedge_ratio * B

    Args:
        series_a: Price series for asset A.
        series_b: Price series for asset B (same length).
        hedge_ratio: Hedge ratio from cointegration regression.

    Returns:
        Spread series.

    Raises:
        PairsError: If series lengths differ.
    """
    if len(series_a) != len(series_b):
        raise PairsError(
            "Series must have equal length for spread calculation",
            operation="spread",
        )
    return [a - hedge_ratio * b for a, b in zip(series_a, series_b)]


def z_score_signal(
    spread: list[float], window: int = 20
) -> list[dict[str, Any]]:
    """
    Compute rolling z-score of spread and generate trading signals.

    Args:
        spread: Spread time series.
        window: Rolling window size for mean/std calculation.

    Returns:
        List of dicts with period, z_score, and signal.
        Signals: "long" if z < -2, "short" if z > 2, "neutral" otherwise.

    Raises:
        PairsError: If inputs are invalid.
    """
    if window < 2:
        raise PairsError(
            "Z-score window must be at least 2", operation="z_score"
        )
    if not spread:
        return []

    results: list[dict[str, Any]] = []

    for i in range(len(spread)):
        if i < window - 1:
            # Not enough data for the rolling window yet
            results.append(
                {"period": i, "z_score": 0.0, "signal": "neutral"}
            )
            continue

        window_data = spread[i - window + 1 : i + 1]
        mean = sum(window_data) / window
        var = sum((v - mean) ** 2 for v in window_data) / (window - 1)
        std = math.sqrt(var) if var > 0 else 0.0

        if std == 0.0:
            z = 0.0
        else:
            z = (spread[i] - mean) / std

        if z < -2.0:
            signal = "long"
        elif z > 2.0:
            signal = "short"
        else:
            signal = "neutral"

        results.append(
            {"period": i, "z_score": round(z, 4), "signal": signal}
        )

    return results


def find_all_pairs(
    returns_by_asset: dict[str, list[float]],
    min_observations: int = 50,
) -> list[dict[str, Any]]:
    """
    Test all pairwise combinations of assets for cointegration.

    Builds cumulative price-like series from returns, then runs
    Engle-Granger test on each pair.

    Args:
        returns_by_asset: Dict of {symbol: [returns...]}.
        min_observations: Minimum shared observations required.

    Returns:
        Sorted list (most negative ADF first) of pair results.
    """
    symbols = sorted(returns_by_asset.keys())
    if len(symbols) < 2:
        return []

    # Build price-like series from cumulative returns
    # price[0] = 100, price[t] = price[t-1] * (1 + r[t])
    price_series: dict[str, list[float]] = {}
    for symbol, returns in returns_by_asset.items():
        prices = [100.0]
        for r in returns:
            prices.append(prices[-1] * (1.0 + r))
        price_series[symbol] = prices

    results: list[dict[str, Any]] = []

    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            sym_a = symbols[i]
            sym_b = symbols[j]

            prices_a = price_series[sym_a]
            prices_b = price_series[sym_b]

            # Align to minimum length
            n = min(len(prices_a), len(prices_b))
            if n < min_observations:
                continue

            prices_a = prices_a[:n]
            prices_b = prices_b[:n]

            try:
                test_result = engle_granger_test(prices_a, prices_b)
            except PairsError:
                continue

            results.append(
                {
                    "pair": [sym_a, sym_b],
                    "adf_statistic": test_result["adf_statistic"],
                    "hedge_ratio": test_result["hedge_ratio"],
                    "is_cointegrated": test_result["is_cointegrated"],
                }
            )

    # Sort by ADF statistic (most negative = most cointegrated first)
    results.sort(key=lambda r: r["adf_statistic"])
    return results


def analyze_pairs(
    min_observations: int = 50,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Full pair trading analysis pipeline.

    Loads raw kline data, extracts close prices, computes returns,
    finds cointegrated pairs, and generates z-score signals for the
    top pair.

    Args:
        min_observations: Minimum data points for pair testing.
        storage: Storage backend (uses default if None).
        save: Whether to persist results.

    Returns:
        Analysis results dict.

    Raises:
        PairsError: If data loading fails or insufficient data.
    """
    if storage is None:
        storage = get_storage()

    # Load raw kline data
    try:
        raw_data = storage.load_raw()
    except (StorageError, FileNotFoundError) as e:
        raise PairsError(
            "Raw price data not found", operation="load"
        ) from e

    if not raw_data:
        raise PairsError("No symbols found in raw data", operation="load")

    # Extract close prices and compute returns per symbol
    returns_by_asset: dict[str, list[float]] = {}
    price_series: dict[str, list[float]] = {}

    for symbol, records in raw_data.items():
        if not records or len(records) < 2:
            continue

        # Sort by timestamp to ensure chronological order
        sorted_records = sorted(records, key=lambda r: r["timestamp"])
        closes = [float(r["close"]) for r in sorted_records]

        if len(closes) < 2:
            continue

        # Log returns
        returns = []
        for k in range(1, len(closes)):
            if closes[k - 1] > 0:
                returns.append(math.log(closes[k] / closes[k - 1]))
            else:
                returns.append(0.0)

        returns_by_asset[symbol] = returns
        price_series[symbol] = closes

    if len(returns_by_asset) < 2:
        raise PairsError(
            "Need at least 2 symbols with sufficient data",
            operation="validate",
        )

    # Find all cointegrated pairs
    pairs = find_all_pairs(returns_by_asset, min_observations=min_observations)
    n_cointegrated = sum(1 for p in pairs if p["is_cointegrated"])

    # Compute z-score detail for top pair (if any cointegrated)
    top_pair_detail: dict[str, Any] | None = None
    if pairs and pairs[0]["is_cointegrated"]:
        top = pairs[0]
        sym_a, sym_b = top["pair"]
        prices_a = price_series[sym_a]
        prices_b = price_series[sym_b]
        n = min(len(prices_a), len(prices_b))
        prices_a = prices_a[:n]
        prices_b = prices_b[:n]

        spread = compute_spread(prices_a, prices_b, top["hedge_ratio"])
        z_scores = z_score_signal(spread)

        top_pair_detail = {
            "pair": top["pair"],
            "hedge_ratio": top["hedge_ratio"],
            "adf_statistic": top["adf_statistic"],
            "z_scores": z_scores[-10:],  # Last 10 signals
            "current_signal": z_scores[-1]["signal"] if z_scores else "neutral",
        }

    result: dict[str, Any] = {
        "pairs": pairs,
        "n_pairs_tested": len(pairs),
        "n_cointegrated": n_cointegrated,
        "top_pair_detail": top_pair_detail,
        "method": "pairs_analysis",
    }

    if save:
        storage.save_output(result, "pairs_analysis")
        logger.info(
            "Pairs analysis: %d tested, %d cointegrated",
            len(pairs),
            n_cointegrated,
        )

    return result
