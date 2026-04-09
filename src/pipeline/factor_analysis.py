"""
Factor exposure analysis module.

Computes factor exposures for portfolio assets using multi-factor regression.
Three factors are constructed from cross-sectional asset data:

- Market: equal-weighted average return across all assets
- Momentum: winners minus losers (top half vs bottom half by trailing return)
- Volatility: low-vol minus high-vol (low half vs high half by rolling std)

Each asset is regressed on the factor returns to obtain alpha, betas, and R-squared.

Output: data/output/factor_analysis.json
"""

import logging
import math
from typing import Any

from src.config import load_config
from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class FactorAnalysisError(Exception):
    """Error during factor exposure analysis."""

    def __init__(self, message: str, *, operation: str = "factor_analysis") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


# ---------------------------------------------------------------------------
# Linear algebra helpers (pure Python, no numpy)
# ---------------------------------------------------------------------------


def _transpose(matrix: list[list[float]]) -> list[list[float]]:
    """Transpose a 2D matrix."""
    if not matrix:
        return []
    n_cols = len(matrix[0])
    return [[row[col] for row in matrix] for col in range(n_cols)]


def _mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """Multiply two matrices."""
    n_rows = len(a)
    n_cols = len(b[0])
    n_inner = len(b)
    result: list[list[float]] = [[0.0] * n_cols for _ in range(n_rows)]
    for i in range(n_rows):
        for j in range(n_cols):
            s = 0.0
            for k in range(n_inner):
                s += a[i][k] * b[k][j]
            result[i][j] = s
    return result


def _mat_vec(matrix: list[list[float]], vec: list[float]) -> list[float]:
    """Multiply matrix by column vector, return list."""
    return [sum(row[j] * vec[j] for j in range(len(vec))) for row in matrix]


def _identity(n: int) -> list[list[float]]:
    """Return n x n identity matrix."""
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _gauss_jordan_inverse(matrix: list[list[float]]) -> list[list[float]]:
    """
    Invert a square matrix using Gauss-Jordan elimination.

    Raises:
        FactorAnalysisError: If the matrix is singular.
    """
    n = len(matrix)
    # Augment with identity
    aug = [row[:] + id_row[:] for row, id_row in zip(matrix, _identity(n))]

    for col in range(n):
        # Partial pivoting
        max_row = col
        max_val = abs(aug[col][col])
        for row in range(col + 1, n):
            if abs(aug[row][col]) > max_val:
                max_val = abs(aug[row][col])
                max_row = row
        if max_val < 1e-12:
            raise FactorAnalysisError(
                "Singular matrix in OLS regression", operation="regression"
            )
        aug[col], aug[max_row] = aug[max_row], aug[col]

        # Scale pivot row
        pivot = aug[col][col]
        for j in range(2 * n):
            aug[col][j] /= pivot

        # Eliminate column
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            for j in range(2 * n):
                aug[row][j] -= factor * aug[col][j]

    return [row[n:] for row in aug]


# ---------------------------------------------------------------------------
# OLS regression
# ---------------------------------------------------------------------------


def _ols_regression(y: list[float], x: list[list[float]]) -> dict[str, Any]:
    """
    Ordinary least squares via normal equations: beta = (X'X)^-1 X'y.

    Args:
        y: Dependent variable (n observations).
        x: Independent variables (n observations x k predictors).
           Each inner list is one observation's predictor values.

    Returns:
        Dict with coefficients, r_squared, and residual_std.

    Raises:
        FactorAnalysisError: If matrix is singular or inputs are invalid.
    """
    n = len(y)
    if n == 0 or not x:
        raise FactorAnalysisError(
            "Empty data for regression", operation="regression"
        )
    k = len(x[0])

    xt = _transpose(x)
    xtx = _mat_mul(xt, x)
    xtx_inv = _gauss_jordan_inverse(xtx)
    xty = _mat_vec(xt, y)
    coefficients = _mat_vec(xtx_inv, xty)

    # Fitted values and residuals
    y_hat = _mat_vec(x, coefficients)
    residuals = [y[i] - y_hat[i] for i in range(n)]

    # R-squared
    y_mean = sum(y) / n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    ss_res = sum(r ** 2 for r in residuals)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-15 else 0.0
    r_squared = max(0.0, min(1.0, r_squared))

    # Residual standard deviation
    dof = n - k
    residual_std = math.sqrt(ss_res / dof) if dof > 0 else 0.0

    return {
        "coefficients": [round(c, 8) for c in coefficients],
        "r_squared": round(r_squared, 6),
        "residual_std": round(residual_std, 8),
    }


# ---------------------------------------------------------------------------
# Factor construction
# ---------------------------------------------------------------------------


def _mean(values: list[float]) -> float:
    """Arithmetic mean, returns 0.0 for empty list."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: list[float]) -> float:
    """Sample standard deviation, returns 0.0 for fewer than 2 values."""
    n = len(values)
    if n < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))


def compute_market_factor(
    returns_by_asset: dict[str, list[float]],
) -> list[float]:
    """
    Equal-weighted average return across all assets per period.

    Args:
        returns_by_asset: {symbol: [r0, r1, ...]} aligned return series.

    Returns:
        List of market factor returns per period.
    """
    if not returns_by_asset:
        return []

    assets = list(returns_by_asset.keys())
    n_periods = len(returns_by_asset[assets[0]])

    market: list[float] = []
    for t in range(n_periods):
        period_returns = [
            returns_by_asset[a][t]
            for a in assets
            if t < len(returns_by_asset[a])
        ]
        market.append(_mean(period_returns))

    return market


def compute_momentum_factor(
    returns_by_asset: dict[str, list[float]],
    window: int = 20,
) -> list[float]:
    """
    Cross-sectional momentum factor.

    For each period, rank assets by trailing ``window``-period cumulative return.
    Factor return = avg return of top half minus avg return of bottom half.

    Args:
        returns_by_asset: {symbol: [r0, r1, ...]} aligned return series.
        window: Lookback window for trailing returns.

    Returns:
        Momentum factor return per period (shorter than input by ``window``).
    """
    if not returns_by_asset:
        return []

    assets = list(returns_by_asset.keys())
    n_periods = len(returns_by_asset[assets[0]])

    momentum: list[float] = []
    for t in range(window, n_periods):
        # Trailing cumulative return per asset
        trailing: list[tuple[str, float]] = []
        for a in assets:
            series = returns_by_asset[a]
            if t > len(series):
                continue
            cum = 1.0
            for i in range(t - window, t):
                cum *= (1.0 + series[i])
            trailing.append((a, cum - 1.0))

        if len(trailing) < 2:
            momentum.append(0.0)
            continue

        # Sort by trailing return descending
        trailing.sort(key=lambda x: x[1], reverse=True)
        mid = len(trailing) // 2

        winners = [returns_by_asset[a][t] for a, _ in trailing[:mid]]
        losers = [returns_by_asset[a][t] for a, _ in trailing[mid:]]

        momentum.append(_mean(winners) - _mean(losers))

    return momentum


def compute_volatility_factor(
    returns_by_asset: dict[str, list[float]],
    window: int = 20,
) -> list[float]:
    """
    Low-volatility minus high-volatility factor.

    For each period, rank assets by rolling standard deviation over ``window``
    periods. Factor return = avg return of low-vol half minus avg return of
    high-vol half.

    Args:
        returns_by_asset: {symbol: [r0, r1, ...]} aligned return series.
        window: Lookback window for rolling volatility.

    Returns:
        Volatility factor return per period.
    """
    if not returns_by_asset:
        return []

    assets = list(returns_by_asset.keys())
    n_periods = len(returns_by_asset[assets[0]])

    vol_factor: list[float] = []
    for t in range(window, n_periods):
        # Rolling vol per asset
        vols: list[tuple[str, float]] = []
        for a in assets:
            series = returns_by_asset[a]
            if t > len(series):
                continue
            window_returns = series[t - window : t]
            vols.append((a, _std(window_returns)))

        if len(vols) < 2:
            vol_factor.append(0.0)
            continue

        # Sort by vol ascending (low vol first)
        vols.sort(key=lambda x: x[1])
        mid = len(vols) // 2

        low_vol = [returns_by_asset[a][t] for a, _ in vols[:mid]]
        high_vol = [returns_by_asset[a][t] for a, _ in vols[mid:]]

        vol_factor.append(_mean(low_vol) - _mean(high_vol))

    return vol_factor


# ---------------------------------------------------------------------------
# Factor regression
# ---------------------------------------------------------------------------


def factor_regression(
    asset_returns: list[float],
    factor_returns: dict[str, list[float]],
) -> dict[str, Any]:
    """
    Regress a single asset's returns on factor returns.

    Adds an intercept (alpha) to the regression automatically.

    Args:
        asset_returns: Return series for one asset.
        factor_returns: {factor_name: [f0, f1, ...]} aligned factor returns.

    Returns:
        Dict with alpha, betas (per factor), r_squared.

    Raises:
        FactorAnalysisError: If data is insufficient or regression fails.
    """
    factor_names = list(factor_returns.keys())
    if not factor_names:
        raise FactorAnalysisError(
            "No factor returns provided", operation="regression"
        )

    # Align lengths to shortest series
    min_len = len(asset_returns)
    for name in factor_names:
        min_len = min(min_len, len(factor_returns[name]))

    if min_len < len(factor_names) + 1:
        raise FactorAnalysisError(
            f"Need at least {len(factor_names) + 1} observations, got {min_len}",
            operation="regression",
        )

    y = asset_returns[:min_len]
    # Build X matrix: [intercept, factor1, factor2, ...]
    x = [
        [1.0] + [factor_returns[name][t] for name in factor_names]
        for t in range(min_len)
    ]

    result = _ols_regression(y, x)
    coefficients = result["coefficients"]

    betas = {name: round(coefficients[i + 1], 6) for i, name in enumerate(factor_names)}

    return {
        "alpha": round(coefficients[0], 8),
        "betas": betas,
        "r_squared": result["r_squared"],
    }


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


def _extract_returns(raw_data: dict[str, list[dict[str, Any]]]) -> dict[str, list[float]]:
    """
    Extract close-to-close returns from raw kline data.

    Args:
        raw_data: {symbol: [{timestamp, close, ...}, ...]} sorted by time.

    Returns:
        {symbol: [r1, r2, ...]} close-to-close log-style simple returns.
    """
    returns_by_asset: dict[str, list[float]] = {}
    for symbol, records in raw_data.items():
        if len(records) < 2:
            continue
        # Sort by timestamp
        sorted_records = sorted(records, key=lambda r: r["timestamp"])
        closes = [float(r["close"]) for r in sorted_records]
        returns: list[float] = []
        for i in range(1, len(closes)):
            if closes[i - 1] > 0:
                returns.append(closes[i] / closes[i - 1] - 1.0)
            else:
                returns.append(0.0)
        returns_by_asset[symbol] = returns
    return returns_by_asset


def _align_returns(
    returns_by_asset: dict[str, list[float]],
) -> dict[str, list[float]]:
    """Trim all return series to the length of the shortest."""
    if not returns_by_asset:
        return {}
    min_len = min(len(v) for v in returns_by_asset.values())
    return {s: r[:min_len] for s, r in returns_by_asset.items()}


def analyze_factors(
    window: int = 20,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run factor exposure analysis on all assets in raw storage.

    Loads raw kline data, computes close-to-close returns, constructs
    market/momentum/volatility factors, and regresses each asset on the
    factors.

    Args:
        window: Lookback window for momentum and volatility factors.
        storage: Storage instance (uses default if None).
        save: Whether to save results to storage.

    Returns:
        Factor analysis results with per-asset exposures.

    Raises:
        FactorAnalysisError: If data is missing or insufficient.
    """
    if storage is None:
        storage = get_storage()

    # Load raw kline data (only configured symbols to avoid mixing frequencies)
    cfg = load_config()
    try:
        raw_data = storage.load_raw(list(cfg.symbols))
    except (StorageError, FileNotFoundError) as e:
        raise FactorAnalysisError(
            "Raw price data not found", operation="load"
        ) from e

    if not raw_data:
        raise FactorAnalysisError(
            "No symbols found in raw data", operation="validate"
        )

    # Extract and align returns
    returns_by_asset = _extract_returns(raw_data)
    if len(returns_by_asset) < 2:
        raise FactorAnalysisError(
            f"Need at least 2 assets for factor analysis, got {len(returns_by_asset)}",
            operation="validate",
        )

    returns_by_asset = _align_returns(returns_by_asset)
    n_periods_raw = len(next(iter(returns_by_asset.values())))

    if n_periods_raw < window + 2:
        raise FactorAnalysisError(
            f"Insufficient data: need at least {window + 2} periods, got {n_periods_raw}",
            operation="validate",
        )

    # Construct factors
    market_full = compute_market_factor(returns_by_asset)
    momentum = compute_momentum_factor(returns_by_asset, window=window)
    volatility = compute_volatility_factor(returns_by_asset, window=window)

    # Align: momentum and volatility start at index `window`, so trim others
    n_factor_periods = min(len(momentum), len(volatility))
    market = market_full[window : window + n_factor_periods]
    momentum = momentum[:n_factor_periods]
    volatility = volatility[:n_factor_periods]

    factor_returns = {
        "market": market,
        "momentum": momentum,
        "volatility": volatility,
    }

    # Regress each asset
    per_asset: list[dict[str, Any]] = []
    factor_names = ["market", "momentum", "volatility"]

    for symbol in sorted(returns_by_asset.keys()):
        asset_r = returns_by_asset[symbol][window : window + n_factor_periods]
        try:
            reg = factor_regression(asset_r, factor_returns)
            per_asset.append({
                "symbol": symbol,
                "alpha": reg["alpha"],
                "betas": reg["betas"],
                "r_squared": reg["r_squared"],
            })
        except FactorAnalysisError:
            logger.warning("Skipping %s: regression failed", symbol)

    result: dict[str, Any] = {
        "per_asset": per_asset,
        "factors": factor_names,
        "n_assets": len(per_asset),
        "n_periods": n_factor_periods,
        "method": "factor_analysis",
    }

    if save:
        storage.save_output(result, "factor_analysis")
        logger.info(
            "Factor analysis: %d assets, %d periods, 3 factors",
            len(per_asset),
            n_factor_periods,
        )

    return result
