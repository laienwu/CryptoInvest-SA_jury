"""
Custom portfolio evaluation module.

Evaluates user-provided portfolio weights against the processed returns
and covariance data to compute expected return, volatility, and Sharpe ratio.

No output file — results are returned directly via the API.
"""

import logging
import math
from typing import Any

from src.pipeline.optimize import (
    calculate_portfolio_return,
    calculate_portfolio_variance,
    dot_product,
    matrix_vector_multiply,
)
from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class EvaluateError(Exception):
    """Error during custom portfolio evaluation."""

    def __init__(self, message: str, *, operation: str = "evaluate") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def evaluate_custom_portfolio(
    weights: dict[str, float],
    risk_free_rate: float = 0.0,
    storage: Storage | None = None,
) -> dict[str, Any]:
    """
    Evaluate a custom set of portfolio weights.

    Args:
        weights: User-provided weights {symbol: weight}. Must sum to ~1.0.
        risk_free_rate: Annual risk-free rate for Sharpe calculation.
        storage: Storage instance.

    Returns:
        Dictionary with expected return, volatility, Sharpe ratio, and
        per-asset risk contribution.

    Raises:
        EvaluateError: If weights are invalid or data is missing.
    """
    if storage is None:
        storage = get_storage()

    if not weights:
        raise EvaluateError("No weights provided", operation="validate")

    weight_sum = sum(weights.values())
    if abs(weight_sum - 1.0) > 0.01:
        raise EvaluateError(
            f"Weights sum to {weight_sum:.4f}, expected ~1.0",
            operation="validate",
        )

    # Load processed data
    try:
        returns_data = storage.load_processed("returns")
        cov_data = storage.load_processed("covariance")
    except (StorageError, FileNotFoundError) as e:
        raise EvaluateError(
            "Processed data not found (returns/covariance)", operation="load"
        ) from e

    available_symbols = returns_data.get("symbols", [])
    mean_returns = returns_data.get("annualized_mean", [])
    cov_matrix = cov_data.get("matrix", [])

    if not available_symbols or not mean_returns or not cov_matrix:
        raise EvaluateError("Processed data is incomplete", operation="validate")

    # Map user symbols to data indices
    symbol_idx = {s: i for i, s in enumerate(available_symbols)}
    unknown = [s for s in weights if s not in symbol_idx]
    if unknown:
        raise EvaluateError(
            f"Unknown symbols: {', '.join(unknown)}. "
            f"Available: {', '.join(available_symbols)}",
            operation="validate",
        )

    # Build weight and return vectors aligned to the full symbol list
    n = len(available_symbols)
    w = [0.0] * n
    for symbol, weight in weights.items():
        w[symbol_idx[symbol]] = weight

    # Portfolio metrics
    exp_return = calculate_portfolio_return(w, mean_returns)
    variance = calculate_portfolio_variance(w, cov_matrix)
    volatility = math.sqrt(max(variance, 0.0))
    sharpe = (
        (exp_return - risk_free_rate) / volatility if volatility > 0 else 0.0
    )

    # Per-asset risk contribution
    sigma_w = matrix_vector_multiply(cov_matrix, w)
    port_vol = volatility if volatility > 0 else 1.0
    contributions: list[dict[str, Any]] = []

    for symbol, weight in weights.items():
        idx = symbol_idx[symbol]
        mctr = sigma_w[idx] / port_vol
        rc = weight * mctr
        contributions.append({
            "symbol": symbol,
            "weight": round(weight, 6),
            "expected_return": round(mean_returns[idx], 6),
            "mctr": round(mctr, 6),
            "risk_contribution": round(rc, 6),
        })

    contributions.sort(key=lambda x: abs(x["risk_contribution"]), reverse=True)

    return {
        "weights": weights,
        "expected_return": round(exp_return, 6),
        "volatility": round(volatility, 6),
        "sharpe_ratio": round(sharpe, 4),
        "risk_free_rate": risk_free_rate,
        "contributions": contributions,
        "n_assets": len(weights),
    }
