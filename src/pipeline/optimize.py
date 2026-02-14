"""
Portfolio optimization module using Markowitz mean-variance optimization.

This module implements portfolio optimization to find optimal asset weights
that maximize the Sharpe ratio (risk-adjusted return) or minimize variance.

Approaches:
- If scipy is available: Use SLSQP constrained optimization
- Fallback: Analytical minimum variance portfolio or grid search

Constraints:
- Weights sum to 1 (fully invested)
- Weights >= 0 (long only, no short selling)

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

from src.config import load_config
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


def matrix_inverse_2x2(matrix: list[list[float]]) -> list[list[float]]:
    """
    Invert a 2x2 matrix.

    For the analytical solution with 2 assets.
    """
    a, b = matrix[0][0], matrix[0][1]
    c, d = matrix[1][0], matrix[1][1]

    det = a * d - b * c
    if abs(det) < 1e-10:
        raise OptimizeError("Matrix is singular", operation="invert")

    return [
        [d / det, -b / det],
        [-c / det, a / det],
    ]


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
    return math.sqrt(variance)


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
# Optimization Methods
# =============================================================================


def _try_scipy_optimization(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    risk_free_rate: float = 0.05,
) -> list[float] | None:
    """
    Try to optimize using scipy if available.

    Uses SLSQP to maximize Sharpe ratio subject to:
    - sum(weights) = 1
    - weights >= 0

    Returns:
        Optimal weights or None if scipy not available.
    """
    try:
        from scipy.optimize import minimize
    except ImportError:
        return None

    n_assets = len(mean_returns)

    # Negative Sharpe (we minimize)
    def neg_sharpe(weights: list[float]) -> float:
        return -calculate_sharpe_ratio(
            list(weights), mean_returns, cov_matrix, risk_free_rate
        )

    # Constraints
    constraints = {"type": "eq", "fun": lambda w: sum(w) - 1}

    # Bounds (long only)
    bounds = [(0, 1) for _ in range(n_assets)]

    # Initial guess (equal weights)
    initial_weights = [1.0 / n_assets] * n_assets

    # Optimize
    result = minimize(
        neg_sharpe,
        initial_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    if result.success:
        return list(result.x)
    else:
        logger.warning(f"scipy optimization did not converge: {result.message}")
        return None


def optimize_minimum_variance(cov_matrix: list[list[float]]) -> list[float]:
    """
    Calculate minimum variance portfolio weights (analytical solution).

    For unconstrained case: w = (Cov^-1 * 1) / (1' * Cov^-1 * 1)

    For long-only constraint with many assets, this is approximated
    using iterative projection.

    Args:
        cov_matrix: Annualized covariance matrix [n x n].

    Returns:
        Minimum variance portfolio weights.
    """
    n = len(cov_matrix)

    # For 2 assets, use analytical solution
    if n == 2:
        var_1 = cov_matrix[0][0]
        var_2 = cov_matrix[1][1]
        cov_12 = cov_matrix[0][1]

        denom = var_1 + var_2 - 2 * cov_12
        if abs(denom) < 1e-10:
            return [0.5, 0.5]

        w1 = (var_2 - cov_12) / denom
        w2 = 1 - w1

        # Apply long-only constraint
        w1 = max(0, min(1, w1))
        w2 = 1 - w1

        return [w1, w2]

    # For more assets, use grid search as fallback
    return _grid_search_min_variance(cov_matrix)


def _grid_search_min_variance(
    cov_matrix: list[list[float]], grid_steps: int = 20
) -> list[float]:
    """
    Find minimum variance portfolio using grid search.

    Generates weight combinations and finds the one with minimum variance.

    Args:
        cov_matrix: Covariance matrix.
        grid_steps: Number of discrete steps (resolution).

    Returns:
        Approximate minimum variance weights.
    """
    n = len(cov_matrix)
    best_weights: list[float] = [1.0 / n] * n
    best_variance = calculate_portfolio_variance(best_weights, cov_matrix)

    # Generate weight combinations
    for weights in _generate_weight_combinations(n, grid_steps):
        variance = calculate_portfolio_variance(weights, cov_matrix)
        if variance < best_variance:
            best_variance = variance
            best_weights = weights

    return best_weights


def _grid_search_max_sharpe(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    risk_free_rate: float = 0.05,
    grid_steps: int = 20,
) -> list[float]:
    """
    Find maximum Sharpe ratio portfolio using grid search.

    Args:
        mean_returns: Annualized mean returns.
        cov_matrix: Annualized covariance matrix.
        risk_free_rate: Risk-free rate.
        grid_steps: Number of discrete steps (resolution).

    Returns:
        Approximate optimal weights.
    """
    n = len(mean_returns)
    best_weights: list[float] = [1.0 / n] * n
    best_sharpe = calculate_sharpe_ratio(
        best_weights, mean_returns, cov_matrix, risk_free_rate
    )

    # Generate weight combinations
    for weights in _generate_weight_combinations(n, grid_steps):
        sharpe = calculate_sharpe_ratio(
            weights, mean_returns, cov_matrix, risk_free_rate
        )
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_weights = weights

    return best_weights


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
    tolerance: float = 0.01,
    grid_steps: int = 20,
) -> list[float] | None:
    """
    Find minimum variance portfolio for a given target return.

    Minimizes w'*Cov*w subject to:
    - sum(w) = 1
    - w >= 0
    - w'*mu = target_return

    Falls back to grid search with tolerance matching if scipy is unavailable.

    Args:
        mean_returns: Annualized mean returns per asset.
        cov_matrix: Annualized covariance matrix.
        target_return: Target portfolio return.
        tolerance: Return tolerance for grid search fallback.

    Returns:
        Optimal weights or None if infeasible.
    """
    try:
        from scipy.optimize import minimize

        n_assets = len(mean_returns)

        def portfolio_variance(weights: list[float]) -> float:
            return calculate_portfolio_variance(list(weights), cov_matrix)

        constraints = [
            {"type": "eq", "fun": lambda w: sum(w) - 1},
            {"type": "eq", "fun": lambda w: dot_product(list(w), mean_returns) - target_return},
        ]

        bounds = [(0, 1) for _ in range(n_assets)]
        initial_weights = [1.0 / n_assets] * n_assets

        result = minimize(
            portfolio_variance,
            initial_weights,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-12, "maxiter": 1000},
        )

        if result.success:
            return list(result.x)
        return None

    except ImportError:
        # Fallback: grid search with tolerance matching
        return _grid_search_target_return(
            mean_returns, cov_matrix, target_return, tolerance, grid_steps
        )


def _grid_search_target_return(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    target_return: float,
    tolerance: float = 0.01,
    grid_steps: int = 20,
) -> list[float] | None:
    """
    Find min variance portfolio near a target return using grid search.

    Args:
        mean_returns: Annualized mean returns per asset.
        cov_matrix: Annualized covariance matrix.
        target_return: Target portfolio return.
        tolerance: Acceptable deviation from target.
        grid_steps: Number of discrete steps (resolution).

    Returns:
        Best weights or None if no feasible combination found.
    """
    n = len(mean_returns)
    best_weights: list[float] | None = None
    best_variance = float("inf")

    for weights in _generate_weight_combinations(n, grid_steps):
        port_return = calculate_portfolio_return(weights, mean_returns)
        if abs(port_return - target_return) <= tolerance:
            variance = calculate_portfolio_variance(weights, cov_matrix)
            if variance < best_variance:
                best_variance = variance
                best_weights = weights

    return best_weights


def compute_efficient_frontier(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    n_points: int = 50,
    risk_free_rate: float = 0.05,
    grid_steps: int = 20,
) -> dict[str, Any]:
    """
    Compute the efficient frontier for a set of assets.

    Sweeps target returns from min to max of individual asset returns,
    finding the minimum variance portfolio at each target level.

    Args:
        mean_returns: Annualized mean returns per asset.
        cov_matrix: Annualized covariance matrix.
        n_points: Number of points on the frontier.
        risk_free_rate: Risk-free rate for CML calculation.

    Returns:
        Dictionary with frontier points, special portfolios, asset positions,
        and capital market line data.
    """
    min_ret = min(mean_returns)
    max_ret = max(mean_returns)
    target_returns = _linspace(min_ret, max_ret, n_points)

    # Build frontier points
    frontier: list[dict[str, Any]] = []
    for target in target_returns:
        weights = _optimize_for_target_return(mean_returns, cov_matrix, target, grid_steps=grid_steps)
        if weights is not None:
            vol = calculate_portfolio_volatility(weights, cov_matrix)
            ret = calculate_portfolio_return(weights, mean_returns)
            frontier.append({
                "volatility": round(vol, 6),
                "return": round(ret, 6),
                "weights": [round(w, 6) for w in weights],
            })

    # Max Sharpe portfolio
    max_sharpe_weights = _try_scipy_optimization(mean_returns, cov_matrix, risk_free_rate)
    if max_sharpe_weights is None:
        max_sharpe_weights = _grid_search_max_sharpe(mean_returns, cov_matrix, risk_free_rate)
    max_sharpe_vol = calculate_portfolio_volatility(max_sharpe_weights, cov_matrix)
    max_sharpe_ret = calculate_portfolio_return(max_sharpe_weights, mean_returns)
    max_sharpe = {
        "volatility": round(max_sharpe_vol, 6),
        "return": round(max_sharpe_ret, 6),
        "weights": [round(w, 6) for w in max_sharpe_weights],
    }

    # Min variance portfolio
    min_var_weights = optimize_minimum_variance(cov_matrix)
    min_var_vol = calculate_portfolio_volatility(min_var_weights, cov_matrix)
    min_var_ret = calculate_portfolio_return(min_var_weights, mean_returns)
    min_variance = {
        "volatility": round(min_var_vol, 6),
        "return": round(min_var_ret, 6),
        "weights": [round(w, 6) for w in min_var_weights],
    }

    # Individual asset positions
    n_assets = len(mean_returns)
    assets = []
    for i in range(n_assets):
        asset_vol = math.sqrt(cov_matrix[i][i])
        assets.append({
            "symbol_index": i,
            "volatility": round(asset_vol, 6),
            "return": round(mean_returns[i], 6),
        })

    # Capital Market Line: from (0, Rf) through tangency portfolio
    tangency_sharpe = calculate_sharpe_ratio(
        max_sharpe_weights, mean_returns, cov_matrix, risk_free_rate
    )
    max_x = max((p["volatility"] for p in frontier), default=max_sharpe_vol) * 1.2
    cml_x = [0.0, round(max_x, 6)]
    cml_y = [risk_free_rate, round(risk_free_rate + tangency_sharpe * max_x, 6)]

    return {
        "frontier": frontier,
        "max_sharpe": max_sharpe,
        "min_variance": min_variance,
        "assets": assets,
        "capital_market_line": {"x": cml_x, "y": cml_y},
        "risk_free_rate": risk_free_rate,
    }


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

    symbols = covariance_data["symbols"]
    cov_matrix = covariance_data["matrix"]
    mean_returns = mean_returns_data["values"]

    logger.info(f"Loaded data for {len(symbols)} symbols: {symbols}")

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


def _generate_weight_combinations(
    n_assets: int, steps: int
) -> list[list[float]]:
    """
    Generate all valid weight combinations that sum to 1.

    Uses recursive generation with pruning for efficiency.

    Args:
        n_assets: Number of assets.
        steps: Number of discrete steps (resolution).

    Returns:
        List of weight combinations.
    """
    combinations: list[list[float]] = []

    def _generate(
        current: list[float], remaining_sum: float, idx: int
    ) -> None:
        if idx == n_assets - 1:
            # Last asset gets the remaining weight
            current.append(remaining_sum)
            combinations.append(current.copy())
            current.pop()
            return

        # Try different weights for current asset
        for i in range(steps + 1):
            weight = i / steps
            if weight <= remaining_sum + 1e-10:
                current.append(weight)
                _generate(current, remaining_sum - weight, idx + 1)
                current.pop()

    _generate([], 1.0, 0)
    return combinations


# =============================================================================
# Public Optimization Façade
# =============================================================================


def optimize_weights(
    strategy: str,
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    risk_free_rate: float = 0.05,
    grid_steps: int = 20,
) -> list[float]:
    """
    Compute optimal portfolio weights for a given strategy.

    Encapsulates strategy dispatch (max_sharpe with scipy→grid fallback,
    min_variance). This is the public API that other modules (e.g. backtest)
    should call instead of private optimization functions.

    Args:
        strategy: "max_sharpe" or "min_variance".
        mean_returns: Annualized mean returns per asset.
        cov_matrix: Annualized covariance matrix.
        risk_free_rate: Risk-free rate for Sharpe calculation.
        grid_steps: Grid resolution for fallback search.

    Returns:
        Optimal portfolio weights.

    Raises:
        OptimizeError: If unknown strategy.
    """
    if strategy == "max_sharpe":
        weights = _try_scipy_optimization(mean_returns, cov_matrix, risk_free_rate)
        if weights is None:
            weights = _grid_search_max_sharpe(
                mean_returns, cov_matrix, risk_free_rate, grid_steps
            )
        return weights
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
    2. Try scipy optimization if available (maximize Sharpe ratio)
    3. Fallback to grid search if scipy not available
    4. Save results to storage

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
            "method": str  # "scipy" or "grid_search"
        }

    Raises:
        OptimizeError: If optimization fails.
    """
    logger.info("Starting portfolio optimization")

    cfg = load_config()
    if storage is None:
        storage = get_storage(cfg.storage_backend)

    # Load required data
    logger.info("Loading processed data")
    try:
        covariance_data = storage.load_processed("covariance")
        mean_returns_data = storage.load_processed("mean_returns")
    except Exception as e:
        raise OptimizeError(
            f"Failed to load processed data: {e}. "
            "Ensure transform_data() has been run first.",
            operation="load",
        ) from e

    symbols = covariance_data["symbols"]
    cov_matrix = covariance_data["matrix"]
    mean_returns = mean_returns_data["values"]

    logger.info(f"Loaded data for {len(symbols)} symbols: {symbols}")

    # Optimization
    logger.info("Running optimization")
    optimal_weights = _try_scipy_optimization(
        mean_returns, cov_matrix, risk_free_rate
    )

    if optimal_weights is None:
        logger.info("scipy not available, using grid search")
        method = "grid_search"
        optimal_weights = _grid_search_max_sharpe(
            mean_returns, cov_matrix, risk_free_rate, cfg.grid_steps
        )
    else:
        method = "scipy"
        logger.info("Using scipy SLSQP optimization")

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

