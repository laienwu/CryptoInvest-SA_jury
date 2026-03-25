"""
Portfolio optimization module using Markowitz mean-variance optimization.

This module implements portfolio optimization to find optimal asset weights
that maximize the Sharpe ratio (risk-adjusted return) or minimize variance.

Uses the Markowitz closed-form solution (Σ⁻¹) for frontier, tangency,
and minimum variance portfolios. No numerical optimizer needed for these —
the covariance matrix is positive-definite symmetric.

Constraint:
- Weights sum to 1 (fully invested, short selling allowed)

Output:
- weights.json with optimal portfolio allocation
- Expected return and volatility of the optimal portfolio

Example usage:
    >>> from src.pipeline.optimize import optimize_portfolio
    >>> result = optimize_portfolio()
    >>> print(result["weights"])
"""

import logging
import math
from typing import Any

from src.config import load_config, load_yfinance_config
from src.storage import Storage, get_storage

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class OptimizeError(Exception):
    """Custom exception for optimization errors."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


# =============================================================================
# Matrix Operations (pure Python, no numpy dependency)
# =============================================================================


def matrix_vector_multiply(
    matrix: list[list[float]], vector: list[float]
) -> list[float]:
    """
    Multiply a matrix by a vector.

    Args:
        matrix: 2D list [n x n].
        vector: 1D list [n].

    Returns:
        Result vector [n].
    """
    n = len(matrix)
    result: list[float] = []
    for i in range(n):
        row_sum = sum(matrix[i][j] * vector[j] for j in range(n))
        result.append(row_sum)
    return result


def dot_product(v1: list[float], v2: list[float]) -> float:
    """Calculate dot product of two vectors."""
    return sum(a * b for a, b in zip(v1, v2))



# =============================================================================
# Portfolio Metrics
# =============================================================================


def _validate_weights(weights: list[float], expected_len: int) -> None:
    """Validate portfolio weight vector."""
    if len(weights) != expected_len:
        raise OptimizeError(
            f"Weights length {len(weights)} != expected {expected_len}",
            operation="validate",
        )
    weight_sum = sum(weights)
    if abs(weight_sum - 1.0) > 0.01:
        raise OptimizeError(
            f"Weights sum to {weight_sum:.4f}, expected ~1.0",
            operation="validate",
        )


def calculate_portfolio_return(
    weights: list[float], mean_returns: list[float]
) -> float:
    """
    Calculate expected portfolio return.

    Args:
        weights: Portfolio weights [n].
        mean_returns: Annualized mean returns per asset [n].

    Returns:
        Expected portfolio return (annualized).

    Raises:
        OptimizeError: If weights/returns length mismatch or weights don't sum to ~1.
    """
    _validate_weights(weights, len(mean_returns))
    return dot_product(weights, mean_returns)


def calculate_portfolio_variance(
    weights: list[float], cov_matrix: list[list[float]]
) -> float:
    """
    Calculate portfolio variance.

    Variance = w' * Cov * w

    Args:
        weights: Portfolio weights [n].
        cov_matrix: Annualized covariance matrix [n x n].

    Returns:
        Portfolio variance.

    Raises:
        OptimizeError: If weights length doesn't match matrix dimensions or weights don't sum to ~1.
    """
    _validate_weights(weights, len(cov_matrix))
    # Cov * w
    cov_w = matrix_vector_multiply(cov_matrix, weights)
    # w' * (Cov * w)
    return dot_product(weights, cov_w)


def calculate_portfolio_volatility(
    weights: list[float], cov_matrix: list[list[float]]
) -> float:
    """
    Calculate portfolio volatility (standard deviation).

    Args:
        weights: Portfolio weights [n].
        cov_matrix: Annualized covariance matrix [n x n].

    Returns:
        Portfolio volatility (annualized).
    """
    variance = calculate_portfolio_variance(weights, cov_matrix)
    return math.sqrt(max(0.0, variance))


def calculate_sharpe_ratio(
    weights: list[float],
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    risk_free_rate: float = 0.05,
) -> float:
    """
    Calculate Sharpe ratio of a portfolio.

    Sharpe = (E[R] - Rf) / sigma

    Args:
        weights: Portfolio weights [n].
        mean_returns: Annualized mean returns [n].
        cov_matrix: Annualized covariance matrix [n x n].
        risk_free_rate: Risk-free rate for excess return calculation.

    Returns:
        Sharpe ratio.
    """
    portfolio_return = calculate_portfolio_return(weights, mean_returns)
    portfolio_vol = calculate_portfolio_volatility(weights, cov_matrix)

    if portfolio_vol < 1e-10:
        return 0.0

    return (portfolio_return - risk_free_rate) / portfolio_vol


# =============================================================================
# Risk Contribution
# =============================================================================


def compute_risk_contribution(
    weights: list[float],
    cov_matrix: list[list[float]],
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compute each asset's marginal and percentage contribution to portfolio risk.

    MCTR_i = (Σw)_i / σ_p   (marginal contribution to total risk)
    RC_i = w_i * MCTR_i       (risk contribution)
    PCT_i = RC_i / σ_p        (percentage of total risk)

    Args:
        weights: Portfolio weights [n].
        cov_matrix: Annualized covariance matrix [n x n].
        symbols: Optional symbol names for labeling.

    Returns:
        Dictionary with per-asset risk contributions and portfolio volatility.
    """
    n = len(weights)
    if symbols is None:
        symbols = [f"asset_{i}" for i in range(n)]

    # Σw
    cov_w = matrix_vector_multiply(cov_matrix, weights)
    # σ_p
    portfolio_var = dot_product(weights, cov_w)
    portfolio_vol = math.sqrt(portfolio_var) if portfolio_var > 0 else 0.0

    contributions: list[dict[str, Any]] = []
    for i in range(n):
        mctr = cov_w[i] / portfolio_vol if portfolio_vol > 0 else 0.0
        rc = weights[i] * mctr
        pct = rc / portfolio_vol if portfolio_vol > 0 else 0.0
        contributions.append({
            "symbol": symbols[i],
            "weight": round(weights[i], 6),
            "mctr": round(mctr, 6),
            "risk_contribution": round(rc, 6),
            "pct_contribution": round(pct, 4),
        })

    # Sort by absolute risk contribution descending
    contributions.sort(key=lambda x: abs(x["risk_contribution"]), reverse=True)

    return {
        "contributions": contributions,
        "portfolio_volatility": round(portfolio_vol, 6),
        "n_assets": n,
    }


# =============================================================================
# Optimization Methods
# =============================================================================


def _frontier_scalars(
    cov_matrix: list[list[float]],
    mean_returns: list[float],
) -> tuple[float, float, float, float, list[float], list[float]]:
    """
    Compute the Markowitz closed-form scalars and helper vectors.

    Given Σ (positive-definite covariance) and μ (mean returns):
        A = 1'Σ⁻¹1
        B = 1'Σ⁻¹μ
        C = μ'Σ⁻¹μ
        D = AC - B²

    Returns:
        (A, B, C, D, Σ⁻¹·1, Σ⁻¹·μ)
    """
    from scipy.linalg import inv

    n = len(mean_returns)
    ones = [1.0] * n

    # Σ⁻¹ via scipy (exact for symmetric positive-definite)
    inv_cov = inv([[float(x) for x in row] for row in cov_matrix]).tolist()

    inv_cov_ones = matrix_vector_multiply(inv_cov, ones)
    inv_cov_mu = matrix_vector_multiply(inv_cov, mean_returns)

    a = dot_product(ones, inv_cov_ones)       # 1'Σ⁻¹1
    b = dot_product(ones, inv_cov_mu)          # 1'Σ⁻¹μ
    c = dot_product(mean_returns, inv_cov_mu)  # μ'Σ⁻¹μ
    d = a * c - b * b                           # AC - B²

    return a, b, c, d, inv_cov_ones, inv_cov_mu


def _scipy_max_sharpe(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    risk_free_rate: float = 0.05,
) -> list[float]:
    """
    Analytical tangency (max Sharpe) portfolio.

    w = Σ⁻¹(μ - r_f·1) / 1'Σ⁻¹(μ - r_f·1)

    Unconstrained (short selling allowed).
    """
    a, b, _c, _d, inv_cov_ones, inv_cov_mu = _frontier_scalars(
        cov_matrix, mean_returns
    )

    # Σ⁻¹(μ - r_f·1) = Σ⁻¹μ - r_f·Σ⁻¹·1
    n = len(mean_returns)
    raw = [inv_cov_mu[i] - risk_free_rate * inv_cov_ones[i] for i in range(n)]
    denom = b - risk_free_rate * a  # 1'Σ⁻¹(μ - r_f·1)

    if abs(denom) < 1e-12:
        logger.warning("Tangency portfolio degenerate (all excess returns ≈ 0)")
        return [1.0 / n] * n

    return [w / denom for w in raw]


def _scipy_max_sharpe_long_only(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    risk_free_rate: float = 0.05,
) -> list[float]:
    """
    Long-only max-Sharpe portfolio via scipy SLSQP.

    Maximises (μ_p - r_f) / σ_p subject to:
    - sum(w) = 1
    - w >= 0  (no short selling)
    """
    from scipy.optimize import minimize

    n = len(mean_returns)

    def neg_sharpe(weights: list[float]) -> float:
        w = list(weights)
        port_return = dot_product(w, mean_returns)
        var = calculate_portfolio_variance(w, cov_matrix)
        vol = math.sqrt(max(0.0, var)) if var > 0 else 1e-10
        return -(port_return - risk_free_rate) / vol

    constraints = [{"type": "eq", "fun": lambda w: sum(w) - 1.0}]
    bounds = [(0.0, 1.0)] * n

    result = minimize(
        neg_sharpe,
        [1.0 / n] * n,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )

    if result.success:
        return [max(0.0, w) for w in result.x]

    logger.warning("Long-only optimization failed, falling back to equal weights")
    return [1.0 / n] * n


def optimize_minimum_variance(cov_matrix: list[list[float]]) -> list[float]:
    """
    Analytical global minimum variance portfolio.

    w = Σ⁻¹·1 / (1'·Σ⁻¹·1)

    Unconstrained (short selling allowed).

    Args:
        cov_matrix: Annualized covariance matrix [n x n].

    Returns:
        Minimum variance portfolio weights.
    """
    from scipy.linalg import inv

    n = len(cov_matrix)
    ones = [1.0] * n

    inv_cov = inv([[float(x) for x in row] for row in cov_matrix]).tolist()
    inv_cov_ones = matrix_vector_multiply(inv_cov, ones)
    a = dot_product(ones, inv_cov_ones)  # 1'Σ⁻¹1

    return [w / a for w in inv_cov_ones]




def _linspace(start: float, end: float, num: int) -> list[float]:
    """
    Generate evenly spaced values between start and end (inclusive).

    Pure Python equivalent of numpy.linspace.

    Args:
        start: Start value.
        end: End value.
        num: Number of points.

    Returns:
        List of evenly spaced values.
    """
    if num <= 0:
        return []
    if num == 1:
        return [start]
    step = (end - start) / (num - 1)
    return [start + i * step for i in range(num)]


def _optimize_for_target_return(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    target_return: float,
    long_only: bool = False,
) -> list[float] | None:
    """
    Find minimum variance portfolio for a given target return via scipy SLSQP.

    Minimizes w'*Cov*w subject to:
    - sum(w) = 1
    - w'*mu = target_return
    - (optional) w >= 0 when long_only=True

    Args:
        mean_returns: Annualized mean returns per asset.
        cov_matrix: Annualized covariance matrix.
        target_return: Target portfolio return.
        long_only: If True, enforce non-negativity (w >= 0).
            False (default) allows short selling for the full frontier parabola.

    Returns:
        Optimal weights or None if infeasible.
    """
    from scipy.optimize import minimize

    n = len(mean_returns)

    def portfolio_var(weights: list[float]) -> float:
        return calculate_portfolio_variance(list(weights), cov_matrix)

    constraints = [
        {"type": "eq", "fun": lambda w: sum(w) - 1},
        {"type": "eq", "fun": lambda w: dot_product(list(w), mean_returns) - target_return},
    ]
    bounds = [(0, 1)] * n if long_only else None

    result = minimize(
        portfolio_var,
        [1.0 / n] * n,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )

    if result.success:
        return list(result.x)
    return None


def compute_efficient_frontier(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    n_points: int = 50,
    risk_free_rate: float = 0.05,
) -> dict[str, Any]:
    """
    Compute the minimum variance frontier using the Markowitz closed-form.

    For Σ positive-definite, the frontier is a parabola in (σ², μ) space:
        σ² = (A·μ² − 2B·μ + C) / D

    with A = 1'Σ⁻¹1, B = 1'Σ⁻¹μ, C = μ'Σ⁻¹μ, D = AC − B².

    For each target μ_p, the optimal weights are:
        w(μ_p) = g + h·μ_p
    where g = (C·Σ⁻¹1 − B·Σ⁻¹μ) / D,  h = (A·Σ⁻¹μ − B·Σ⁻¹1) / D.

    Args:
        mean_returns: Annualized mean returns per asset.
        cov_matrix: Annualized covariance matrix (positive-definite).
        n_points: Number of points on the frontier.
        risk_free_rate: Risk-free rate for CML calculation.

    Returns:
        Dictionary with frontier points, special portfolios, asset positions,
        and capital market line data.
    """
    a, b, c, d, inv_cov_ones, inv_cov_mu = _frontier_scalars(
        cov_matrix, mean_returns
    )
    n_assets = len(mean_returns)

    # Closed-form weight vectors: w(μ_p) = g + h·μ_p
    g = [(c * inv_cov_ones[i] - b * inv_cov_mu[i]) / d for i in range(n_assets)]
    h = [(a * inv_cov_mu[i] - b * inv_cov_ones[i]) / d for i in range(n_assets)]

    # Min variance portfolio: vertex of the parabola
    mu_mv = b / a
    sigma_mv = math.sqrt(1.0 / a)
    min_var_weights = [inv_cov_ones[i] / a for i in range(n_assets)]

    # Sweep target returns centered on the min-variance return.
    # Extend 1.5× the asset return range on each side so both arms are visible.
    ret_range = max(mean_returns) - min(mean_returns)
    if ret_range < 1e-10:
        ret_range = abs(mu_mv) + 0.1  # fallback for identical returns
    sweep_lo = mu_mv - 1.5 * ret_range
    sweep_hi = mu_mv + 1.5 * ret_range
    target_returns = _linspace(sweep_lo, sweep_hi, n_points)

    # Build frontier points from the analytical formula
    frontier: list[dict[str, Any]] = []
    for mu_p in target_returns:
        sigma_sq = (a * mu_p * mu_p - 2 * b * mu_p + c) / d
        sigma = math.sqrt(max(sigma_sq, 0.0))
        weights = [g[i] + h[i] * mu_p for i in range(n_assets)]
        frontier.append({
            "volatility": round(sigma, 6),
            "return": round(mu_p, 6),
            "weights": [round(w, 6) for w in weights],
        })

    # Max Sharpe portfolio — pick from efficient (upper) arm of frontier.
    # The analytical tangency formula breaks when r_f > μ_mv (all excess
    # returns negative): the tangent lands on the lower arm.  Instead,
    # scan frontier points on the efficient arm (μ ≥ μ_mv) for the best
    # Sharpe ratio.  This always gives a point ON the visible curve.
    efficient_pts = [p for p in frontier if p["return"] >= round(mu_mv, 6)]
    if efficient_pts:
        best = max(
            efficient_pts,
            key=lambda p: (p["return"] - risk_free_rate) / p["volatility"]
            if p["volatility"] > 1e-10
            else 0.0,
        )
    else:
        best = min(frontier, key=lambda p: p["volatility"])
    max_sharpe = {
        "volatility": best["volatility"],
        "return": best["return"],
        "weights": best["weights"],
    }

    # Min variance portfolio
    min_variance = {
        "volatility": round(sigma_mv, 6),
        "return": round(mu_mv, 6),
        "weights": [round(w, 6) for w in min_var_weights],
    }

    # Individual asset positions
    assets = []
    for i in range(n_assets):
        asset_vol = math.sqrt(cov_matrix[i][i])
        assets.append({
            "symbol_index": i,
            "volatility": round(asset_vol, 6),
            "return": round(mean_returns[i], 6),
        })

    # Capital Market Line: tangent to the frontier at the max-Sharpe point.
    # Frontier slope at (σ₀, μ₀): dμ/dσ = σ₀·D / (A·μ₀ − B).
    # The y-intercept is the implied risk-free rate.
    ms_sigma = max_sharpe["volatility"]
    ms_mu = max_sharpe["return"]
    denom_slope = a * ms_mu - b
    if abs(denom_slope) > 1e-12 and ms_sigma > 1e-10:
        cml_slope = ms_sigma * d / denom_slope
        cml_intercept = ms_mu - cml_slope * ms_sigma
    else:
        cml_slope = 0.0
        cml_intercept = risk_free_rate
    max_x = max((p["volatility"] for p in frontier), default=ms_sigma) * 1.2
    cml_x = [0.0, round(max_x, 6)]
    cml_y = [round(cml_intercept, 6), round(cml_intercept + cml_slope * max_x, 6)]

    return {
        "frontier": frontier,
        "max_sharpe": max_sharpe,
        "min_variance": min_variance,
        "assets": assets,
        "capital_market_line": {"x": cml_x, "y": cml_y},
        "risk_free_rate": risk_free_rate,
    }


def _load_optimization_inputs(
    storage: Storage | None = None,
) -> tuple[list[str], list[list[float]], list[float], Storage]:
    """Load covariance and mean returns from storage (shared setup)."""
    if storage is None:
        cfg = load_config()
        storage = get_storage(cfg.storage_backend)

    try:
        covariance_data = storage.load_processed("covariance")
        mean_returns_data = storage.load_processed("mean_returns")
    except Exception as e:
        raise OptimizeError(
            f"Failed to load processed data: {e}. "
            "Ensure transform_data() has been run first.",
            operation="load",
        ) from e

    symbols: list[str] = covariance_data["symbols"]
    cov_matrix: list[list[float]] = covariance_data["matrix"]
    mean_returns: list[float] = mean_returns_data["values"]

    logger.info(f"Loaded data for {len(symbols)} symbols: {symbols}")
    return symbols, cov_matrix, mean_returns, storage


def compute_and_save_frontier(
    storage: Storage | None = None,
    n_points: int = 50,
    risk_free_rate: float = 0.05,
    save: bool = True,
) -> dict[str, Any]:
    """
    Compute efficient frontier and save results.

    Loads covariance matrix and mean returns from storage,
    computes the efficient frontier, and saves to output.

    Args:
        storage: Storage instance. If None, resolves from config.
        n_points: Number of frontier points.
        risk_free_rate: Risk-free rate.
        save: Whether to save results.

    Returns:
        Frontier data with symbols attached.
    """
    logger.info("Computing efficient frontier")

    symbols, cov_matrix, mean_returns, storage = _load_optimization_inputs(storage)

    result = compute_efficient_frontier(
        mean_returns, cov_matrix, n_points, risk_free_rate
    )
    result["symbols"] = symbols

    logger.info(f"Frontier points: {len(result['frontier'])}")
    logger.info(f"Max Sharpe return: {result['max_sharpe']['return']:.2%}")
    logger.info(f"Min Variance vol: {result['min_variance']['volatility']:.2%}")

    if save:
        try:
            output_path = storage.save_output(result, "frontier")
            logger.info(f"Saved frontier to: {output_path}")
        except Exception as e:
            raise OptimizeError(
                f"Failed to save frontier: {e}", operation="save"
            ) from e

    logger.info("Frontier computation complete")
    return result


# =============================================================================
# Public Optimization Façade
# =============================================================================


def optimize_weights(
    strategy: str,
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    risk_free_rate: float = 0.05,
) -> list[float]:
    """
    Compute optimal portfolio weights for a given strategy.

    This is the public API that other modules (e.g. backtest) should call.

    Args:
        strategy: "max_sharpe" or "min_variance".
        mean_returns: Annualized mean returns per asset.
        cov_matrix: Annualized covariance matrix.
        risk_free_rate: Risk-free rate for Sharpe calculation.

    Returns:
        Optimal portfolio weights.

    Raises:
        OptimizeError: If unknown strategy.
    """
    if strategy == "max_sharpe":
        return _scipy_max_sharpe(mean_returns, cov_matrix, risk_free_rate)
    elif strategy == "min_variance":
        return optimize_minimum_variance(cov_matrix)
    else:
        raise OptimizeError(
            f"Unknown strategy: {strategy}. Use 'max_sharpe' or 'min_variance'.",
            operation="optimize",
        )


# =============================================================================
# Main Optimization Function
# =============================================================================


def optimize_portfolio(
    storage: Storage | None = None,
    risk_free_rate: float = 0.05,
    save: bool = True,
) -> dict[str, Any]:
    """
    Main entry point for portfolio optimization.

    Loads processed data (covariance, mean returns) and computes optimal
    portfolio weights using Markowitz mean-variance optimization.

    Algorithm:
    1. Load covariance matrix and mean returns from storage
    2. Maximize Sharpe ratio via scipy SLSQP
    3. Save results to storage

    Args:
        storage: Storage instance. If None, resolves from config.
        risk_free_rate: Risk-free rate for Sharpe calculation.
        save: Whether to save results to storage.

    Returns:
        Dictionary containing:
        {
            "symbols": [...],
            "weights": {...},  # symbol -> weight mapping
            "expected_return": float,
            "volatility": float,
            "sharpe_ratio": float,
            "method": str  # "scipy"
        }

    Raises:
        OptimizeError: If optimization fails.
    """
    logger.info("Starting portfolio optimization")

    symbols, cov_matrix, mean_returns, storage = _load_optimization_inputs(storage)

    # Optimization (long-only: no short selling)
    logger.info("Running long-only max-Sharpe optimization")
    optimal_weights = _scipy_max_sharpe_long_only(mean_returns, cov_matrix, risk_free_rate)
    method = "scipy_long_only"

    # Calculate portfolio metrics
    expected_return = calculate_portfolio_return(optimal_weights, mean_returns)
    volatility = calculate_portfolio_volatility(optimal_weights, cov_matrix)
    sharpe_ratio = calculate_sharpe_ratio(
        optimal_weights, mean_returns, cov_matrix, risk_free_rate
    )

    # Build weights dictionary
    weights_dict = {
        symbol: round(weight, 6) for symbol, weight in zip(symbols, optimal_weights)
    }

    # Build result
    result: dict[str, Any] = {
        "symbols": symbols,
        "weights": weights_dict,
        "weights_list": [round(w, 6) for w in optimal_weights],
        "expected_return": round(expected_return, 6),
        "volatility": round(volatility, 6),
        "sharpe_ratio": round(sharpe_ratio, 6),
        "risk_free_rate": risk_free_rate,
        "method": method,
    }

    # Log summary
    logger.info("OPTIMAL PORTFOLIO")
    logger.info("Weights:")
    for symbol, weight in weights_dict.items():
        logger.info(f"  {symbol}: {weight:.2%}")
    logger.info(f"Expected Return: {expected_return:.2%}")
    logger.info(f"Volatility: {volatility:.2%}")
    logger.info(f"Sharpe Ratio: {sharpe_ratio:.4f}")
    logger.info(f"Method: {method}")

    # Save to storage
    if save:
        logger.info("Saving results")
        try:
            output_path = storage.save_output(result, "weights")
            logger.info(f"Saved to: {output_path}")
        except Exception as e:
            raise OptimizeError(
                f"Failed to save results: {e}", operation="save"
            ) from e

    logger.info("Optimization complete")

    return result


def load_optimal_portfolio(storage: Storage | None = None) -> dict[str, Any]:
    """
    Load previously computed optimal portfolio from storage.

    Args:
        storage: Storage instance. If None, resolves from config.

    Returns:
        Optimal portfolio data.

    Raises:
        OptimizeError: If loading fails.
    """
    if storage is None:
        cfg = load_config()
        storage = get_storage(cfg.storage_backend)

    try:
        return storage.load_output("weights")
    except Exception as e:
        raise OptimizeError(
            f"Failed to load optimal portfolio: {e}", operation="load"
        ) from e


# =============================================================================
# Additional Portfolio Calculations
# =============================================================================


def calculate_equal_weight_portfolio(
    storage: Storage | None = None,
    risk_free_rate: float = 0.05,
) -> dict[str, Any]:
    """
    Calculate metrics for equal-weight portfolio (benchmark).

    Useful for comparison with the optimized portfolio.

    Args:
        storage: Storage instance. If None, resolves from config.
        risk_free_rate: Risk-free rate.

    Returns:
        Equal weight portfolio metrics.
    """
    if storage is None:
        cfg = load_config()
        storage = get_storage(cfg.storage_backend)

    covariance_data = storage.load_processed("covariance")
    mean_returns_data = storage.load_processed("mean_returns")

    symbols = covariance_data["symbols"]
    cov_matrix = covariance_data["matrix"]
    mean_returns = mean_returns_data["values"]

    n = len(symbols)
    weights = [1.0 / n] * n

    expected_return = calculate_portfolio_return(weights, mean_returns)
    volatility = calculate_portfolio_volatility(weights, cov_matrix)
    sharpe_ratio = calculate_sharpe_ratio(
        weights, mean_returns, cov_matrix, risk_free_rate
    )

    return {
        "symbols": symbols,
        "weights": {symbol: 1.0 / n for symbol in symbols},
        "expected_return": expected_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
    }


# =============================================================================
# Traditional Asset Portfolio (yfinance)
# =============================================================================


def _load_trad_optimization_inputs(
    storage: Storage | None = None,
) -> tuple[list[str], list[list[float]], list[float], Storage]:
    """Load covariance and mean returns for traditional assets."""
    if storage is None:
        cfg = load_config()
        storage = get_storage(cfg.storage_backend)

    try:
        covariance_data = storage.load_processed("covariance_trad")
        mean_returns_data = storage.load_processed("mean_returns_trad")
    except Exception as e:
        raise OptimizeError(
            f"Failed to load trad processed data: {e}. "
            "Ensure transform_yfinance_data() has been run first.",
            operation="load",
        ) from e

    symbols: list[str] = covariance_data["symbols"]
    cov_matrix: list[list[float]] = covariance_data["matrix"]
    mean_returns: list[float] = mean_returns_data["values"]

    logger.info(f"Loaded trad data for {len(symbols)} symbols: {symbols}")
    return symbols, cov_matrix, mean_returns, storage


def optimize_yfinance_portfolio(
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Optimize traditional asset portfolio (yfinance symbols).

    Same Markowitz optimization as crypto, but uses ``_trad`` metrics
    and saves to ``weights_trad.json``.

    Args:
        storage: Storage instance. If None, resolves from config.
        save: Whether to save results.

    Returns:
        Optimal portfolio weights for traditional assets.
    """
    logger.info("Starting traditional portfolio optimization")

    yf_cfg = load_yfinance_config()
    risk_free_rate = yf_cfg.risk_free_rate

    symbols, cov_matrix, mean_returns, storage = _load_trad_optimization_inputs(storage)

    optimal_weights = _scipy_max_sharpe_long_only(mean_returns, cov_matrix, risk_free_rate)

    expected_return = calculate_portfolio_return(optimal_weights, mean_returns)
    volatility = calculate_portfolio_volatility(optimal_weights, cov_matrix)
    sharpe_ratio = calculate_sharpe_ratio(
        optimal_weights, mean_returns, cov_matrix, risk_free_rate
    )

    weights_dict = {
        symbol: round(weight, 6) for symbol, weight in zip(symbols, optimal_weights)
    }

    result: dict[str, Any] = {
        "symbols": symbols,
        "weights": weights_dict,
        "weights_list": [round(w, 6) for w in optimal_weights],
        "expected_return": round(expected_return, 6),
        "volatility": round(volatility, 6),
        "sharpe_ratio": round(sharpe_ratio, 6),
        "risk_free_rate": risk_free_rate,
        "method": "scipy",
    }

    logger.info("OPTIMAL TRADITIONAL PORTFOLIO")
    for symbol, weight in weights_dict.items():
        logger.info(f"  {symbol}: {weight:.2%}")
    logger.info(f"Expected Return: {expected_return:.2%}")
    logger.info(f"Sharpe Ratio: {sharpe_ratio:.4f}")

    if save:
        try:
            storage.save_output(result, "weights_trad")
        except Exception as e:
            raise OptimizeError(
                f"Failed to save trad results: {e}", operation="save"
            ) from e

    return result


def compute_and_save_frontier_trad(
    storage: Storage | None = None,
    n_points: int = 50,
    save: bool = True,
) -> dict[str, Any]:
    """
    Compute efficient frontier for traditional assets and save to ``frontier_trad.json``.

    Args:
        storage: Storage instance. If None, resolves from config.
        n_points: Number of frontier points.
        save: Whether to save results.

    Returns:
        Frontier data for traditional assets.
    """
    logger.info("Computing efficient frontier (traditional assets)")

    yf_cfg = load_yfinance_config()
    risk_free_rate = yf_cfg.risk_free_rate

    symbols, cov_matrix, mean_returns, storage = _load_trad_optimization_inputs(storage)

    result = compute_efficient_frontier(
        mean_returns, cov_matrix, n_points, risk_free_rate
    )
    result["symbols"] = symbols

    logger.info(f"Trad frontier points: {len(result['frontier'])}")

    if save:
        try:
            storage.save_output(result, "frontier_trad")
        except Exception as e:
            raise OptimizeError(
                f"Failed to save trad frontier: {e}", operation="save"
            ) from e

    return result
