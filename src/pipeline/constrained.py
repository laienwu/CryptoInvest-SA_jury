"""
Constrained portfolio optimizer module.

Extends the Markowitz optimizer with user-defined constraints:
- Per-asset minimum and maximum weight bounds
- Maximum number of assets (cardinality constraint via weight threshold)
- Sector/group exposure limits

Uses scipy SLSQP under the hood, same as the base optimizer.

Output: data/output/weights_constrained.json
"""

import logging
import math
from typing import Any

from src.pipeline.optimize import (
    calculate_portfolio_return,
    calculate_portfolio_variance,
    calculate_portfolio_volatility,
    dot_product,
)
from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class ConstrainedError(Exception):
    """Error during constrained optimization."""

    def __init__(self, message: str, *, operation: str = "constrained") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def optimize_constrained(
    mean_returns: list[float],
    cov_matrix: list[list[float]],
    symbols: list[str],
    min_weights: dict[str, float] | None = None,
    max_weights: dict[str, float] | None = None,
    group_constraints: list[dict[str, Any]] | None = None,
    risk_free_rate: float = 0.0,
) -> dict[str, Any]:
    """
    Find maximum Sharpe ratio portfolio subject to constraints.

    Args:
        mean_returns: Annualized mean returns per asset.
        cov_matrix: Annualized covariance matrix.
        symbols: Asset symbol names (same order as returns/cov).
        min_weights: Min weight per symbol (default 0.0 for all).
        max_weights: Max weight per symbol (default 1.0 for all).
        group_constraints: List of group constraints, each with:
            - symbols: list of symbols in the group
            - max_weight: max combined weight for the group
        risk_free_rate: Risk-free rate for Sharpe calculation.

    Returns:
        Optimized weights, return, volatility, Sharpe, constraints applied.

    Raises:
        ConstrainedError: If optimization fails.
    """
    from scipy.optimize import minimize

    n = len(mean_returns)
    if n < 2:
        raise ConstrainedError(
            "Need at least 2 assets for optimization", operation="validate"
        )
    if len(symbols) != n:
        raise ConstrainedError(
            "Symbols count must match returns count", operation="validate"
        )

    # Build bounds
    min_w = min_weights or {}
    max_w = max_weights or {}
    bounds = [
        (min_w.get(s, 0.0), max_w.get(s, 1.0))
        for s in symbols
    ]

    # Validate bounds feasibility
    total_min = sum(b[0] for b in bounds)
    total_max = sum(b[1] for b in bounds)
    if total_min > 1.0 + 1e-6:
        raise ConstrainedError(
            f"Infeasible: sum of min weights ({total_min:.4f}) > 1.0",
            operation="validate",
        )
    if total_max < 1.0 - 1e-6:
        raise ConstrainedError(
            f"Infeasible: sum of max weights ({total_max:.4f}) < 1.0",
            operation="validate",
        )

    # Objective: negative Sharpe (minimize = maximize Sharpe)
    def neg_sharpe(weights: list[float]) -> float:
        w = list(weights)
        port_return = dot_product(w, mean_returns)
        var = calculate_portfolio_variance(w, cov_matrix)
        vol = math.sqrt(var) if var > 0 else 1e-10
        return -(port_return - risk_free_rate) / vol

    # Constraints
    constraints: list[dict[str, Any]] = [
        {"type": "eq", "fun": lambda w: sum(w) - 1.0},
    ]

    # Group constraints
    if group_constraints:
        for gc in group_constraints:
            group_symbols = gc.get("symbols", [])
            group_max = gc.get("max_weight", 1.0)
            indices = [i for i, s in enumerate(symbols) if s in group_symbols]
            if indices:
                constraints.append({
                    "type": "ineq",
                    "fun": lambda w, idx=indices, mx=group_max: mx - sum(w[i] for i in idx),
                })

    # Initial guess: equal weight (clamped to bounds)
    init = [1.0 / n] * n
    for i in range(n):
        init[i] = max(bounds[i][0], min(bounds[i][1], init[i]))
    # Rescale to sum to 1
    s = sum(init)
    if s > 0:
        init = [w / s for w in init]

    result = minimize(
        neg_sharpe,
        init,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )

    if not result.success:
        raise ConstrainedError(
            f"Optimization failed: {result.message}", operation="optimize"
        )

    optimal = list(result.x)
    # Clean near-zero weights
    optimal = [max(0, w) for w in optimal]
    total = sum(optimal)
    if total > 0:
        optimal = [w / total for w in optimal]

    port_return = calculate_portfolio_return(optimal, mean_returns)
    port_vol = calculate_portfolio_volatility(optimal, cov_matrix)
    sharpe = (port_return - risk_free_rate) / port_vol if port_vol > 0 else 0.0

    weights_dict = {s: round(w, 6) for s, w in zip(symbols, optimal) if w > 1e-6}

    constraints_applied: dict[str, Any] = {
        "min_weights": {s: bounds[i][0] for i, s in enumerate(symbols) if bounds[i][0] > 0},
        "max_weights": {s: bounds[i][1] for i, s in enumerate(symbols) if bounds[i][1] < 1.0},
        "n_active": sum(1 for w in optimal if w > 1e-6),
    }
    if group_constraints:
        constraints_applied["groups"] = group_constraints

    return {
        "weights": weights_dict,
        "expected_return": round(port_return, 6),
        "volatility": round(port_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "risk_free_rate": risk_free_rate,
        "constraints": constraints_applied,
        "n_assets": len(weights_dict),
        "optimization_method": "constrained_max_sharpe",
    }


def analyze_constrained(
    min_weights: dict[str, float] | None = None,
    max_weights: dict[str, float] | None = None,
    group_constraints: list[dict[str, Any]] | None = None,
    risk_free_rate: float = 0.0,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run constrained optimization using processed data from storage.

    Args:
        min_weights: Minimum weight per symbol.
        max_weights: Maximum weight per symbol.
        group_constraints: Group exposure limits.
        risk_free_rate: Risk-free rate.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Constrained portfolio optimization results.

    Raises:
        ConstrainedError: If data is missing or optimization fails.
    """
    if storage is None:
        storage = get_storage()

    try:
        cov_data = storage.load_processed("covariance")
        returns_data = storage.load_processed("mean_returns")
    except (StorageError, FileNotFoundError) as e:
        raise ConstrainedError(
            "Processed data not found (covariance/mean_returns)", operation="load"
        ) from e

    symbols = cov_data.get("symbols", [])
    cov_matrix = cov_data.get("matrix", [])
    mean_returns = returns_data.get("values", [])

    if not symbols or not cov_matrix or not mean_returns:
        raise ConstrainedError(
            "Incomplete processed data", operation="validate"
        )

    result = optimize_constrained(
        mean_returns=mean_returns,
        cov_matrix=cov_matrix,
        symbols=symbols,
        min_weights=min_weights,
        max_weights=max_weights,
        group_constraints=group_constraints,
        risk_free_rate=risk_free_rate,
    )

    if save:
        storage.save_output("weights_constrained", result)
        logger.info(
            "Constrained optimization: %d active assets, Sharpe %.4f",
            result["n_assets"], result["sharpe_ratio"],
        )

    return result
