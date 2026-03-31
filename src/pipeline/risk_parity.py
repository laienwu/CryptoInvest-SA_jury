"""
Risk parity portfolio optimization module.

Computes portfolio weights such that each asset contributes equally
to total portfolio risk (volatility). This is an alternative to
Markowitz max-Sharpe that focuses on risk diversification.

Algorithm: iterative inverse-volatility weighting refined by marginal
risk contribution targeting. Starts with 1/σ weights and adjusts until
each asset's percentage risk contribution converges to 1/N.

Output: data/output/risk_parity.json
"""

import logging
import math
from typing import Any

from src.pipeline.optimize import (
    calculate_portfolio_return,
    calculate_portfolio_variance,
    matrix_vector_multiply,
)
from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 200
CONVERGENCE_TOL = 1e-6


class RiskParityError(Exception):
    """Error during risk parity optimization."""

    def __init__(self, message: str, *, operation: str = "risk_parity") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def _normalize_weights(weights: list[float]) -> list[float]:
    """Normalize weights to sum to 1."""
    total = sum(weights)
    if total <= 0:
        n = len(weights)
        return [1.0 / n] * n
    return [w / total for w in weights]


def compute_risk_parity_weights(
    cov_matrix: list[list[float]],
    max_iter: int = MAX_ITERATIONS,
    tol: float = CONVERGENCE_TOL,
) -> dict[str, Any]:
    """
    Compute risk parity weights via iterative rebalancing.

    Starting from inverse-volatility weights, iteratively adjust so each
    asset's risk contribution converges to 1/N of portfolio risk.

    Args:
        cov_matrix: Annualized covariance matrix [n x n].
        max_iter: Maximum iterations for convergence.
        tol: Convergence tolerance on risk contribution deviation.

    Returns:
        Dictionary with weights, risk contributions, and convergence info.
    """
    n = len(cov_matrix)
    if n == 0:
        return {"weights": [], "converged": True, "iterations": 0}

    target_rc = 1.0 / n  # Each asset should contribute 1/N of total risk

    # Initialize with inverse-volatility weights
    vols = [math.sqrt(max(cov_matrix[i][i], 1e-12)) for i in range(n)]
    inv_vols = [1.0 / v for v in vols]
    weights = _normalize_weights(inv_vols)

    converged = False
    iteration = 0
    for iteration in range(1, max_iter + 1):  # noqa: B007 — used after loop
        # Portfolio volatility
        port_var = calculate_portfolio_variance(weights, cov_matrix)
        port_vol = math.sqrt(max(port_var, 1e-12))

        # Marginal risk contribution
        sigma_w = matrix_vector_multiply(cov_matrix, weights)
        risk_contributions = [weights[i] * sigma_w[i] / port_vol for i in range(n)]

        # Percentage risk contribution
        total_rc = sum(risk_contributions)
        if total_rc <= 0:
            break
        pct_rc = [rc / total_rc for rc in risk_contributions]

        # Check convergence: max deviation from target
        max_dev = max(abs(pct_rc[i] - target_rc) for i in range(n))
        if max_dev < tol:
            converged = True
            break

        # Adjust weights: increase weight of under-contributing assets
        new_weights = []
        for i in range(n):
            ratio = target_rc / max(pct_rc[i], 1e-12)
            new_weights.append(weights[i] * math.sqrt(ratio))

        weights = _normalize_weights(new_weights)

    # Final risk contributions
    port_var = calculate_portfolio_variance(weights, cov_matrix)
    port_vol = math.sqrt(max(port_var, 1e-12))
    sigma_w = matrix_vector_multiply(cov_matrix, weights)
    risk_contributions = [weights[i] * sigma_w[i] / port_vol for i in range(n)]
    total_rc = sum(risk_contributions) if sum(risk_contributions) > 0 else 1.0
    pct_rc = [rc / total_rc for rc in risk_contributions]

    return {
        "weights": [round(w, 6) for w in weights],
        "risk_contributions": [round(rc, 6) for rc in risk_contributions],
        "pct_contributions": [round(p, 6) for p in pct_rc],
        "portfolio_volatility": round(port_vol, 6),
        "converged": converged,
        "iterations": iteration,
    }


def optimize_risk_parity(
    portfolio_key: str = "risk_parity",
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run risk parity optimization using processed data.

    Args:
        portfolio_key: Storage key for saving results.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Risk parity portfolio with weights, risk contributions, and metrics.

    Raises:
        RiskParityError: If processed data is missing.
    """
    if storage is None:
        storage = get_storage()

    try:
        returns_data = storage.load_processed("returns")
        cov_data = storage.load_processed("covariance")
    except (StorageError, FileNotFoundError) as e:
        raise RiskParityError(
            "Processed data not found (returns/covariance)", operation="load"
        ) from e

    symbols = returns_data.get("symbols", [])
    mean_returns = returns_data.get("annualized_mean", [])
    cov_matrix = cov_data.get("matrix", [])

    if not symbols or not cov_matrix:
        raise RiskParityError("Processed data is incomplete", operation="validate")

    rp = compute_risk_parity_weights(cov_matrix)
    weights_list = rp["weights"]

    # Compute expected return
    if mean_returns and len(mean_returns) == len(symbols):
        exp_return = calculate_portfolio_return(weights_list, mean_returns)
    else:
        exp_return = 0.0

    port_vol = rp["portfolio_volatility"]
    sharpe = (exp_return / port_vol) if port_vol > 0 else 0.0

    # Build named weight dict
    weights_dict = {
        symbols[i]: weights_list[i]
        for i in range(len(symbols))
    }

    # Per-asset detail
    contributions = [
        {
            "symbol": symbols[i],
            "weight": weights_list[i],
            "risk_contribution": rp["risk_contributions"][i],
            "pct_contribution": rp["pct_contributions"][i],
        }
        for i in range(len(symbols))
    ]

    result: dict[str, Any] = {
        "weights": weights_dict,
        "expected_return": round(exp_return, 6),
        "volatility": round(port_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "contributions": contributions,
        "converged": rp["converged"],
        "iterations": rp["iterations"],
        "n_assets": len(symbols),
        "optimization_method": "risk_parity",
    }

    if save:
        storage.save_output(result, portfolio_key)
        logger.info(
            "Risk parity: %d assets, vol=%.4f, converged=%s (%d iters)",
            len(symbols), port_vol, rp["converged"], rp["iterations"],
        )

    return result
