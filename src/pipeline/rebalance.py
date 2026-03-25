"""
Portfolio rebalancing alerts.

Compares current (or last known) portfolio weights against the optimal
allocation and flags symbols that have drifted beyond a configurable
threshold. Suggests trades (buy/sell amounts) to restore target weights.

Output: data/output/rebalance_alerts.json
"""

import logging
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)

DEFAULT_DRIFT_THRESHOLD = 0.05  # 5 percentage points


class RebalanceError(Exception):
    """Error during rebalancing analysis."""

    def __init__(self, message: str, *, operation: str = "rebalance") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def compute_rebalance_alerts(
    current_weights: dict[str, float] | None = None,
    drift_threshold: float = DEFAULT_DRIFT_THRESHOLD,
    portfolio_value: float = 10000.0,
    portfolio_key: str = "weights",
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Compare current weights against optimal and generate rebalancing alerts.

    Args:
        current_weights: Current portfolio weights. If None, uses optimal as
            both current and target (no drift — useful for initial setup).
        drift_threshold: Minimum absolute weight difference to trigger an alert.
        portfolio_value: Total portfolio value in USD for trade sizing.
        portfolio_key: Storage key for optimal weights ("weights" or "weights_trad").
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Dictionary with alerts, suggested trades, and drift statistics.

    Raises:
        RebalanceError: If optimal portfolio cannot be loaded.
    """
    if drift_threshold < 0 or drift_threshold > 1:
        raise RebalanceError(
            f"drift_threshold must be between 0 and 1, got {drift_threshold}",
            operation="validate",
        )

    if storage is None:
        storage = get_storage()

    # Load optimal weights
    try:
        optimal_data = storage.load_output(portfolio_key)
    except (StorageError, FileNotFoundError) as e:
        raise RebalanceError(
            f"Optimal portfolio not found (key={portfolio_key})",
            operation="load_optimal",
        ) from e

    target_weights = optimal_data.get("weights", {})
    if not target_weights:
        raise RebalanceError("Optimal portfolio has no weights", operation="validate")

    # Default current = target (no drift)
    if current_weights is None:
        current_weights = dict(target_weights)

    # All symbols from both sets
    all_symbols = sorted(set(target_weights) | set(current_weights))

    alerts: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    total_drift = 0.0

    for symbol in all_symbols:
        current = current_weights.get(symbol, 0.0)
        target = target_weights.get(symbol, 0.0)
        drift = current - target

        total_drift += abs(drift)

        if abs(drift) >= drift_threshold:
            direction = "SELL" if drift > 0 else "BUY"
            trade_amount = abs(drift) * portfolio_value

            alerts.append({
                "symbol": symbol,
                "current_weight": round(current, 6),
                "target_weight": round(target, 6),
                "drift": round(drift, 6),
                "drift_pct": round(drift * 100, 2),
                "action": direction,
            })

            trades.append({
                "symbol": symbol,
                "action": direction,
                "amount_usd": round(trade_amount, 2),
                "weight_change": round(-drift, 6),
            })

    result: dict[str, Any] = {
        "alerts": alerts,
        "trades": trades,
        "summary": {
            "total_drift": round(total_drift, 6),
            "max_drift": round(max(abs(a["drift"]) for a in alerts), 6) if alerts else 0.0,
            "n_alerts": len(alerts),
            "n_symbols": len(all_symbols),
            "drift_threshold": drift_threshold,
            "portfolio_value": portfolio_value,
            "needs_rebalance": len(alerts) > 0,
        },
        "portfolio_key": portfolio_key,
    }

    if save:
        storage.save_output(result, "rebalance_alerts")
        logger.info(
            "Rebalance analysis: %d alerts out of %d symbols (threshold=%.1f%%)",
            len(alerts),
            len(all_symbols),
            drift_threshold * 100,
        )

    return result
