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

import json
import math
from pathlib import Path
from typing import Any

from src.storage import get_storage

# =============================================================================
# Configuration
# =============================================================================

# Risk-free rate for Sharpe ratio calculation (annualized)
# Using approximate 3-month T-bill rate
RISK_FREE_RATE: float = 0.05

# Grid search resolution (for fallback method)
GRID_STEPS: int = 20


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
    """
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
    """
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
    risk_free_rate: float = RISK_FREE_RATE,
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
    risk_free_rate: float = RISK_FREE_RATE,
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
        print(f"  Warning: scipy optimization did not converge: {result.message}")
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


def _grid_search_min_variance(cov_matrix: list[list[float]]) -> list[float]:
    """
    Find minimum variance portfolio using grid search.

    Generates weight combinations and finds the one with minimum variance.

    Args:
        cov_matrix: Covariance matrix.

    Returns:
        Approximate minimum variance weights.
    """
    n = len(cov_matrix)
    best_weights: list[float] = [1.0 / n] * n
    best_variance = calculate_portfolio_variance(best_weights, cov_matrix)

    # Generate weight combinations
    for weights in _generate_weight_combinations(n, GRID_STEPS):
        variance = calculate_portfolio_variance(weights, cov_matrix)
        if variance < best_variance:
            best_variance = variance
            best_weights = weights

    return best_weights


def _grid_search_max_sharpe(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    risk_free_rate: float = RISK_FREE_RATE,
) -> list[float]:
    """
    Find maximum Sharpe ratio portfolio using grid search.

    Args:
        mean_returns: Annualized mean returns.
        cov_matrix: Annualized covariance matrix.
        risk_free_rate: Risk-free rate.

    Returns:
        Approximate optimal weights.
    """
    n = len(mean_returns)
    best_weights: list[float] = [1.0 / n] * n
    best_sharpe = calculate_sharpe_ratio(
        best_weights, mean_returns, cov_matrix, risk_free_rate
    )

    # Generate weight combinations
    for weights in _generate_weight_combinations(n, GRID_STEPS):
        sharpe = calculate_sharpe_ratio(
            weights, mean_returns, cov_matrix, risk_free_rate
        )
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_weights = weights

    return best_weights


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
# Main Optimization Function
# =============================================================================


def optimize_portfolio(
    storage_backend: str = "parquet",
    risk_free_rate: float = RISK_FREE_RATE,
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
        storage_backend: Storage backend to use. Defaults to "parquet".
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
    print("Starting portfolio optimization...")
    print("=" * 50)

    # Get storage instance
    storage = get_storage(storage_backend)

    # Load required data
    print("\nLoading processed data...")
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

    print(f"  Loaded data for {len(symbols)} symbols: {symbols}")

    # Optimization
    print("\nRunning optimization...")
    method = "scipy"

    # Try scipy first
    optimal_weights = _try_scipy_optimization(
        mean_returns, cov_matrix, risk_free_rate
    )

    if optimal_weights is None:
        print("  scipy not available, using grid search...")
        method = "grid_search"
        optimal_weights = _grid_search_max_sharpe(
            mean_returns, cov_matrix, risk_free_rate
        )
    else:
        print("  Using scipy SLSQP optimization")

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

    # Print summary
    print("\n" + "=" * 50)
    print("OPTIMAL PORTFOLIO")
    print("=" * 50)
    print("\nWeights:")
    for symbol, weight in weights_dict.items():
        print(f"  {symbol}: {weight:.2%}")
    print(f"\nExpected Return: {expected_return:.2%}")
    print(f"Volatility:      {volatility:.2%}")
    print(f"Sharpe Ratio:    {sharpe_ratio:.4f}")
    print(f"Method:          {method}")

    # Save to storage
    if save:
        print("\nSaving results...")
        try:
            output_path = storage.save_output(result, "weights")
            print(f"  Saved to: {output_path}")
        except Exception as e:
            raise OptimizeError(
                f"Failed to save results: {e}", operation="save"
            ) from e

    print("\n" + "=" * 50)
    print("Optimization complete!")

    return result


def load_optimal_portfolio(storage_backend: str = "parquet") -> dict[str, Any]:
    """
    Load previously computed optimal portfolio from storage.

    Args:
        storage_backend: Storage backend to use.

    Returns:
        Optimal portfolio data.

    Raises:
        OptimizeError: If loading fails.
    """
    storage = get_storage(storage_backend)

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
    storage_backend: str = "parquet",
    risk_free_rate: float = RISK_FREE_RATE,
) -> dict[str, Any]:
    """
    Calculate metrics for equal-weight portfolio (benchmark).

    Useful for comparison with the optimized portfolio.

    Args:
        storage_backend: Storage backend to use.
        risk_free_rate: Risk-free rate.

    Returns:
        Equal weight portfolio metrics.
    """
    storage = get_storage(storage_backend)

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
# Main execution (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Testing portfolio optimization...")
    print("=" * 50)

    try:
        # Run optimization
        result = optimize_portfolio()

        # Compare with equal weight
        print("\n" + "=" * 50)
        print("COMPARISON WITH EQUAL WEIGHT PORTFOLIO")
        print("=" * 50)

        equal_weight = calculate_equal_weight_portfolio()
        print("\nEqual Weight Portfolio:")
        print(f"  Expected Return: {equal_weight['expected_return']:.2%}")
        print(f"  Volatility:      {equal_weight['volatility']:.2%}")
        print(f"  Sharpe Ratio:    {equal_weight['sharpe_ratio']:.4f}")

        print("\nOptimal Portfolio:")
        print(f"  Expected Return: {result['expected_return']:.2%}")
        print(f"  Volatility:      {result['volatility']:.2%}")
        print(f"  Sharpe Ratio:    {result['sharpe_ratio']:.4f}")

        # Improvement
        sharpe_improvement = (
            result["sharpe_ratio"] - equal_weight["sharpe_ratio"]
        ) / abs(equal_weight["sharpe_ratio"]) * 100
        print(f"\nSharpe Ratio Improvement: {sharpe_improvement:+.1f}%")

    except OptimizeError as e:
        print(f"ERROR: {e.message}")
        if e.operation:
            print(f"  Operation: {e.operation}")
