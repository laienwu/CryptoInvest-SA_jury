"""
Maximum diversification portfolio optimization module.

Maximizes the diversification ratio DR = (w'sigma) / sqrt(w'Sigma*w)
where sigma is the vector of individual asset volatilities and Sigma
is the covariance matrix. A higher diversification ratio means the
portfolio captures more diversification benefit from imperfect correlations.

Uses scipy SLSQP optimizer with long-only constraint (w >= 0) and
full investment constraint (sum(w) = 1).

Output: data/output/max_diversification.json
"""

import logging
import math
from typing import Any

from src.pipeline.optimize import (
    calculate_portfolio_return,
    calculate_portfolio_variance,
    dot_product,
)
from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class MaxDiversificationError(Exception):
    """Error during maximum diversification optimization."""

    def __init__(
        self, message: str, *, operation: str = "max_diversification"
    ) -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def diversification_ratio(
    weights: list[float], cov_matrix: list[list[float]]
) -> float:
    """
    Compute the diversification ratio of a portfolio.

    DR = (w'sigma) / sqrt(w'Sigma*w)

    Where sigma_i = sqrt(Sigma_ii) is each asset's individual volatility.
    A ratio of 1.0 means no diversification benefit (single asset or
    perfectly correlated assets). Higher values indicate more diversification.

    Args:
        weights: Portfolio weights [n].
        cov_matrix: Annualized covariance matrix [n x n].

    Returns:
        Diversification ratio (>= 1.0 for long-only portfolios).
    """
    n = len(weights)
    if n == 0:
        return 1.0

    # Individual asset volatilities
    asset_vols = [math.sqrt(max(cov_matrix[i][i], 0.0)) for i in range(n)]

    # Weighted average volatility: w'sigma
    weighted_avg_vol = dot_product(weights, asset_vols)

    # Portfolio volatility: sqrt(w'Sigma*w)
    port_var = calculate_portfolio_variance(weights, cov_matrix)
    port_vol = math.sqrt(max(port_var, 1e-16))

    if port_vol < 1e-16:
        return 1.0

    return weighted_avg_vol / port_vol


def optimize_max_diversification(
    cov_matrix: list[list[float]],
    mean_returns: list[float] | None = None,
) -> dict[str, Any]:
    """
    Find portfolio weights that maximize the diversification ratio.

    Uses scipy SLSQP to minimize the negative diversification ratio
    subject to long-only (w >= 0) and fully invested (sum(w) = 1)
    constraints.

    Args:
        cov_matrix: Annualized covariance matrix [n x n].
        mean_returns: Optional annualized mean returns (not used in
            objective but included in output if provided).

    Returns:
        Dictionary with optimal weights, diversification ratio, and
        portfolio volatility.

    Raises:
        MaxDiversificationError: If optimization fails.
    """
    from scipy.optimize import minimize

    n = len(cov_matrix)
    if n == 0:
        return {"weights": [], "diversification_ratio": 1.0, "portfolio_volatility": 0.0}

    if n == 1:
        return {
            "weights": [1.0],
            "diversification_ratio": 1.0,
            "portfolio_volatility": math.sqrt(max(cov_matrix[0][0], 0.0)),
        }

    # Objective: minimize negative diversification ratio
    def neg_div_ratio(w: list[float]) -> float:
        return -diversification_ratio(list(w), cov_matrix)

    # Constraints: fully invested
    constraints = [{"type": "eq", "fun": lambda w: sum(w) - 1.0}]

    # Bounds: long-only
    bounds = [(0.0, 1.0)] * n

    # Initial guess: equal weight
    init = [1.0 / n] * n

    result = minimize(
        neg_div_ratio,
        init,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )

    if not result.success:
        raise MaxDiversificationError(
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
    dr = diversification_ratio(optimal, cov_matrix)

    return {
        "weights": [round(w, 6) for w in optimal],
        "diversification_ratio": round(dr, 6),
        "portfolio_volatility": round(port_vol, 6),
    }


def analyze_max_diversification(
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run maximum diversification optimization using processed data.

    Loads processed returns and covariance from storage, runs the
    optimizer, and computes expected return and Sharpe ratio.

    Args:
        storage: Storage instance (uses default if None).
        save: Whether to save results to storage.

    Returns:
        Full result dictionary with named weights, metrics, and method.

    Raises:
        MaxDiversificationError: If processed data is missing or incomplete.
    """
    if storage is None:
        storage = get_storage()

    try:
        returns_data = storage.load_processed("returns")
        cov_data = storage.load_processed("covariance")
    except (StorageError, FileNotFoundError) as e:
        raise MaxDiversificationError(
            "Processed data not found (returns/covariance)", operation="load"
        ) from e

    symbols = returns_data.get("symbols", [])
    mean_returns = returns_data.get("annualized_mean", [])
    cov_matrix = cov_data.get("matrix", [])

    if not symbols or not cov_matrix:
        raise MaxDiversificationError(
            "Processed data is incomplete", operation="validate"
        )

    opt = optimize_max_diversification(cov_matrix, mean_returns)
    weights_list = opt["weights"]

    # Compute expected return
    if mean_returns and len(mean_returns) == len(symbols):
        exp_return = calculate_portfolio_return(weights_list, mean_returns)
    else:
        exp_return = 0.0

    port_vol = opt["portfolio_volatility"]
    sharpe = (exp_return / port_vol) if port_vol > 0 else 0.0

    # Build named weight dict
    weights_dict = {
        symbols[i]: weights_list[i]
        for i in range(len(symbols))
    }

    result: dict[str, Any] = {
        "weights": weights_dict,
        "expected_return": round(exp_return, 6),
        "volatility": round(port_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "diversification_ratio": opt["diversification_ratio"],
        "n_assets": len(symbols),
        "method": "max_diversification",
    }

    if save:
        storage.save_output(result, "max_diversification")
        logger.info(
            "Max diversification: %d assets, DR=%.4f, vol=%.4f",
            len(symbols),
            opt["diversification_ratio"],
            port_vol,
        )

    return result
