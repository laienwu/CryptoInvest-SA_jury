"""
Minimum variance portfolio optimization module.

Finds the portfolio with the lowest possible volatility (standard deviation)
regardless of expected return. Uses scipy SLSQP optimizer with long-only
constraint (w >= 0) and full investment constraint (sum(w) = 1).

This is a pure risk-minimization approach: useful as a benchmark for
risk-averse investors or as the left-most point on the efficient frontier.

Output: data/output/min_variance.json
"""

import logging
import math
from typing import Any

from src.pipeline.optimize import (
    calculate_portfolio_return,
    calculate_portfolio_variance,
)
from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class MinVarianceError(Exception):
    """Error during minimum variance optimization."""

    def __init__(
        self, message: str, *, operation: str = "min_variance"
    ) -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def optimize_min_variance(
    cov_matrix: list[list[float]],
) -> dict[str, Any]:
    """
    Find portfolio weights that minimize portfolio variance.

    Uses scipy SLSQP to minimize w'Sigma*w subject to long-only (w >= 0)
    and fully invested (sum(w) = 1) constraints.

    Args:
        cov_matrix: Annualized covariance matrix [n x n].

    Returns:
        Dictionary with optimal weights, portfolio volatility, and variance.

    Raises:
        MinVarianceError: If optimization fails.
    """
    from scipy.optimize import minimize

    n = len(cov_matrix)
    if n == 0:
        return {"weights": [], "portfolio_volatility": 0.0, "portfolio_variance": 0.0}

    if n == 1:
        vol = math.sqrt(max(cov_matrix[0][0], 0.0))
        return {
            "weights": [1.0],
            "portfolio_volatility": round(vol, 6),
            "portfolio_variance": round(cov_matrix[0][0], 6),
        }

    # Objective: minimize portfolio variance
    def objective(w: list[float]) -> float:
        return calculate_portfolio_variance(list(w), cov_matrix)

    # Constraints: fully invested
    constraints = [{"type": "eq", "fun": lambda w: sum(w) - 1.0}]

    # Bounds: long-only
    bounds = [(0.0, 1.0)] * n

    # Initial guess: equal weight
    init = [1.0 / n] * n

    result = minimize(
        objective,
        init,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )

    if not result.success:
        raise MinVarianceError(
            f"Optimization failed: {result.message}", operation="optimize"
        )

    optimal = list(result.x)
    # Clean near-zero weights and renormalize
    optimal = [max(0.0, w) for w in optimal]
    total = sum(optimal)
    if total > 0:
        optimal = [w / total for w in optimal]

    port_var = calculate_portfolio_variance(optimal, cov_matrix)
    port_vol = math.sqrt(max(port_var, 0.0))

    return {
        "weights": [round(w, 6) for w in optimal],
        "portfolio_volatility": round(port_vol, 6),
        "portfolio_variance": round(port_var, 6),
    }


def analyze_min_variance(
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run minimum variance optimization using processed data.

    Loads processed returns and covariance from storage, runs the
    optimizer, computes expected return and Sharpe ratio, and compares
    with the equal-weight portfolio.

    Args:
        storage: Storage instance (uses default if None).
        save: Whether to save results to storage.

    Returns:
        Full result dictionary with named weights, metrics, equal-weight
        comparison, and method identifier.

    Raises:
        MinVarianceError: If processed data is missing or incomplete.
    """
    if storage is None:
        storage = get_storage()

    try:
        returns_data = storage.load_processed("returns")
        cov_data = storage.load_processed("covariance")
    except (StorageError, FileNotFoundError) as e:
        raise MinVarianceError(
            "Processed data not found (returns/covariance)", operation="load"
        ) from e

    symbols = returns_data.get("symbols", [])
    mean_returns = returns_data.get("annualized_mean", [])
    cov_matrix = cov_data.get("matrix", [])

    if not symbols or not cov_matrix:
        raise MinVarianceError(
            "Processed data is incomplete", operation="validate"
        )

    n = len(symbols)

    # --- Minimum variance portfolio ---
    opt = optimize_min_variance(cov_matrix)
    weights_list = opt["weights"]

    # Compute expected return
    if mean_returns and len(mean_returns) == n:
        exp_return = calculate_portfolio_return(weights_list, mean_returns)
    else:
        exp_return = 0.0

    port_vol = opt["portfolio_volatility"]
    sharpe = (exp_return / port_vol) if port_vol > 0 else 0.0

    # --- Equal-weight portfolio for comparison ---
    ew = [1.0 / n] * n
    ew_var = calculate_portfolio_variance(ew, cov_matrix)
    ew_vol = math.sqrt(max(ew_var, 0.0))

    if mean_returns and len(mean_returns) == n:
        ew_return = calculate_portfolio_return(ew, mean_returns)
    else:
        ew_return = 0.0

    # Volatility reduction percentage
    if ew_vol > 0:
        vol_reduction_pct = round((1.0 - port_vol / ew_vol) * 100.0, 2)
    else:
        vol_reduction_pct = 0.0

    # Build named weight dict
    weights_dict = {
        symbols[i]: weights_list[i]
        for i in range(n)
    }

    result: dict[str, Any] = {
        "weights": weights_dict,
        "expected_return": round(exp_return, 6),
        "volatility": round(port_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "equal_weight_volatility": round(ew_vol, 6),
        "equal_weight_return": round(ew_return, 6),
        "volatility_reduction_pct": vol_reduction_pct,
        "n_assets": n,
        "method": "min_variance",
    }

    if save:
        storage.save_output(result, "min_variance")
        logger.info(
            "Min variance: %d assets, vol=%.4f (%.1f%% reduction vs equal-weight)",
            n,
            port_vol,
            vol_reduction_pct,
        )

    return result
