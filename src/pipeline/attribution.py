"""
Portfolio performance attribution module.

Decomposes portfolio return into per-asset contributions using the
Brinson-style weight × return framework. Shows which assets drove
gains or losses over a given period.

Output: data/output/attribution.json
"""

import logging
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class AttributionError(Exception):
    """Error during performance attribution."""

    def __init__(self, message: str, *, operation: str = "attribution") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def compute_attribution(
    weights: dict[str, float],
    returns: dict[str, float],
) -> dict[str, Any]:
    """
    Compute per-asset return contribution.

    Args:
        weights: Portfolio weights {symbol: weight}.
        returns: Period returns per asset {symbol: return}.

    Returns:
        Attribution breakdown with per-asset contribution and ranking.
    """
    if not weights:
        return {
            "contributions": [],
            "portfolio_return": 0.0,
            "n_assets": 0,
        }

    contributions: list[dict[str, Any]] = []
    portfolio_return = 0.0

    for symbol, weight in weights.items():
        asset_return = returns.get(symbol, 0.0)
        contribution = weight * asset_return
        portfolio_return += contribution

        contributions.append({
            "symbol": symbol,
            "weight": round(weight, 6),
            "asset_return": round(asset_return, 6),
            "contribution": round(contribution, 6),
        })

    # Add percentage contribution
    for c in contributions:
        c["pct_contribution"] = (
            round(c["contribution"] / portfolio_return, 4)
            if portfolio_return != 0
            else 0.0
        )

    # Sort by contribution descending (best contributors first)
    contributions.sort(key=lambda x: x["contribution"], reverse=True)

    return {
        "contributions": contributions,
        "portfolio_return": round(portfolio_return, 6),
        "n_assets": len(contributions),
    }


def analyze_performance_attribution(
    portfolio_key: str = "weights",
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run performance attribution using portfolio weights and processed returns.

    Uses the most recent period return for each asset from the returns data.

    Args:
        portfolio_key: Storage key for portfolio weights.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Attribution analysis with per-asset contributions, top/bottom
        contributors, and sector breakdown.

    Raises:
        AttributionError: If portfolio or returns data is missing.
    """
    if storage is None:
        storage = get_storage()

    # Load portfolio weights
    try:
        portfolio = storage.load_output(portfolio_key)
    except (StorageError, FileNotFoundError) as e:
        raise AttributionError(
            f"Portfolio not found (key={portfolio_key})", operation="load"
        ) from e

    weights = portfolio.get("weights", {})
    if not weights:
        raise AttributionError("Portfolio has no weights", operation="validate")

    # Load returns data
    try:
        returns_data = storage.load_processed("returns")
    except (StorageError, FileNotFoundError) as e:
        raise AttributionError(
            "Returns data not found", operation="load"
        ) from e

    symbols = returns_data.get("symbols", [])
    values = returns_data.get("values", [])

    if not values or not symbols:
        raise AttributionError("Returns data is empty", operation="validate")

    # Use cumulative return over the full period for each asset
    period_returns: dict[str, float] = {}
    for idx, symbol in enumerate(symbols):
        asset_returns = [row[idx] for row in values if idx < len(row)]
        if asset_returns:
            # Compound returns: product of (1 + r) - 1
            cumulative = 1.0
            for r in asset_returns:
                cumulative *= (1 + r)
            period_returns[symbol] = cumulative - 1.0

    attribution = compute_attribution(weights, period_returns)

    # Top/bottom contributors
    contribs = attribution["contributions"]
    top_contributors = contribs[:3] if len(contribs) >= 3 else contribs
    bottom_contributors = contribs[-3:] if len(contribs) >= 3 else contribs

    result: dict[str, Any] = {
        **attribution,
        "top_contributors": [c["symbol"] for c in top_contributors],
        "bottom_contributors": [c["symbol"] for c in bottom_contributors],
        "portfolio_key": portfolio_key,
    }

    if save:
        storage.save_output("attribution", result)
        logger.info(
            "Attribution analysis: portfolio return %.2f%%, %d assets",
            attribution["portfolio_return"] * 100,
            attribution["n_assets"],
        )

    return result
