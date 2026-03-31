"""
Strategy comparison module — side-by-side results from all portfolio optimizers.

Calls all 6 portfolio optimization strategies (Max Sharpe, HRP, Risk Parity,
Min Variance, Max Diversification, Black-Litterman), collects their results,
ranks them by Sharpe ratio, and returns a unified comparison dict.

Output: data/output/strategy_comparison.json
"""

import logging
from typing import Any

from src.pipeline.black_litterman import analyze_black_litterman
from src.pipeline.hrp import analyze_hrp
from src.pipeline.max_diversification import analyze_max_diversification
from src.pipeline.min_variance import analyze_min_variance
from src.pipeline.optimize import optimize_portfolio
from src.pipeline.risk_parity import optimize_risk_parity
from src.storage import Storage, get_storage

logger = logging.getLogger(__name__)


class StrategyCompareError(Exception):
    """Error during strategy comparison."""

    def __init__(self, message: str, *, operation: str = "strategy_compare") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def _call_strategy(
    name: str,
    func: Any,
    storage: Storage,
    **kwargs: Any,
) -> dict[str, Any]:
    """Call a single optimizer and normalize the result."""
    try:
        result = func(storage=storage, save=False, **kwargs)
        return {
            "name": name,
            "weights": result.get("weights"),
            "expected_return": result.get("expected_return"),
            "volatility": result.get("volatility"),
            "sharpe_ratio": result.get("sharpe_ratio"),
            "rank": None,
            "error": None,
        }
    except Exception as exc:
        logger.warning("Strategy %s failed: %s", name, exc)
        return {
            "name": name,
            "weights": None,
            "expected_return": None,
            "volatility": None,
            "sharpe_ratio": None,
            "rank": None,
            "error": str(exc),
        }


def compare_strategies(
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run all 6 portfolio optimizers and return side-by-side comparison.

    Each strategy is called independently; failures are captured gracefully
    so that partial results are still returned.

    Args:
        storage: Storage backend. If None, uses get_storage().
        save: Whether to persist results via storage.save_output.

    Returns:
        Dict with strategies list (ranked by Sharpe), best/worst names,
        counts, symbols, and method identifier.

    Raises:
        StrategyCompareError: If ALL strategies fail.
    """
    if storage is None:
        storage = get_storage()

    strategy_specs: list[tuple[str, Any, dict[str, Any]]] = [
        ("Max Sharpe", optimize_portfolio, {}),
        ("HRP", analyze_hrp, {}),
        ("Risk Parity", optimize_risk_parity, {}),
        ("Min Variance", analyze_min_variance, {}),
        ("Max Diversification", analyze_max_diversification, {}),
        ("Black-Litterman", analyze_black_litterman, {}),
    ]

    strategies: list[dict[str, Any]] = []
    for name, func, kwargs in strategy_specs:
        logger.info("Running strategy: %s", name)
        result = _call_strategy(name, func, storage, **kwargs)
        strategies.append(result)

    successful = [s for s in strategies if s["error"] is None]
    failed = [s for s in strategies if s["error"] is not None]

    if not successful:
        raise StrategyCompareError(
            "All strategies failed",
            operation="compare_strategies",
        )

    # Sort successful by sharpe_ratio descending
    successful.sort(key=lambda s: s["sharpe_ratio"] or 0.0, reverse=True)

    for rank, strategy in enumerate(successful, start=1):
        strategy["rank"] = rank

    ranked = successful + failed

    best_strategy = successful[0]["name"]
    worst_strategy = successful[-1]["name"]

    # Extract symbols from first successful strategy
    first_weights = successful[0]["weights"]
    symbols = list(first_weights.keys()) if first_weights else []

    output: dict[str, Any] = {
        "strategies": ranked,
        "best_strategy": best_strategy,
        "worst_strategy": worst_strategy,
        "n_strategies": len(strategies),
        "n_assets": len(symbols),
        "symbols": symbols,
        "method": "strategy_comparison",
    }

    if save:
        storage.save_output(output, "strategy_comparison")
        logger.info("Strategy comparison saved to storage")

    logger.info(
        "Compared %d strategies: best=%s (Sharpe=%.4f)",
        len(strategies),
        best_strategy,
        successful[0]["sharpe_ratio"] or 0.0,
    )

    return output
