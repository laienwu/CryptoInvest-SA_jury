"""
Portfolio decay analysis module.

Simulates how portfolio weights drift from target allocations over time
without rebalancing. Computes tracking error, maximum deviation, and
optimal rebalance frequency based on a drift threshold.

Output: data/output/decay_analysis.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class DecayError(Exception):
    """Error during portfolio decay analysis."""

    def __init__(self, message: str, *, operation: str = "decay") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def simulate_weight_drift(
    target_weights: list[float],
    returns_matrix: list[list[float]],
) -> list[list[float]]:
    """
    Simulate how portfolio weights evolve over time without rebalancing.

    At each time step, asset values grow by their period return, and the
    new weights are the normalized values.

    Args:
        target_weights: Initial target allocation (must sum to ~1.0).
        returns_matrix: T periods × N assets matrix of returns.

    Returns:
        List of weight vectors over time (T+1 rows × N columns).
        First row is the initial target weights.
    """
    n_assets = len(target_weights)
    if n_assets == 0:
        return []

    # Start with unit values proportional to target weights
    values = list(target_weights)
    result: list[list[float]] = [list(target_weights)]

    for period_returns in returns_matrix:
        # Update values: new_value = old_value * (1 + return)
        for i in range(n_assets):
            r = period_returns[i] if i < len(period_returns) else 0.0
            values[i] = values[i] * (1.0 + r)

        # Normalize to weights
        total = sum(values)
        if total > 0:
            weights = [v / total for v in values]
        else:
            weights = [0.0] * n_assets

        result.append(weights)

    return result


def compute_tracking_error(
    drifted_weights: list[list[float]],
    target_weights: list[float],
) -> list[float]:
    """
    Compute L2 distance from target weights at each time step.

    Args:
        drifted_weights: Weight vectors over time (T+1 × N).
        target_weights: Target allocation vector.

    Returns:
        List of L2 distances, one per time step.
    """
    errors: list[float] = []
    for weights in drifted_weights:
        sq_sum = 0.0
        for i, w in enumerate(weights):
            t = target_weights[i] if i < len(target_weights) else 0.0
            sq_sum += (w - t) ** 2
        errors.append(round(math.sqrt(sq_sum), 8))
    return errors


def compute_max_deviation(
    drifted_weights: list[list[float]],
    target_weights: list[float],
) -> list[float]:
    """
    Compute maximum absolute deviation from target across assets at each step.

    Args:
        drifted_weights: Weight vectors over time (T+1 × N).
        target_weights: Target allocation vector.

    Returns:
        List of max absolute deviations, one per time step.
    """
    deviations: list[float] = []
    for weights in drifted_weights:
        max_dev = 0.0
        for i, w in enumerate(weights):
            t = target_weights[i] if i < len(target_weights) else 0.0
            dev = abs(w - t)
            if dev > max_dev:
                max_dev = dev
        deviations.append(round(max_dev, 8))
    return deviations


def optimal_rebalance_frequency(
    target_weights: list[float],
    returns_matrix: list[list[float]],
    max_deviation_threshold: float = 0.05,
) -> dict[str, Any]:
    """
    Find the first period where max deviation exceeds the threshold.

    Simulates weight drift and scans for the first breach. If the
    threshold is never exceeded, returns the total number of periods.

    Args:
        target_weights: Target allocation vector.
        returns_matrix: T periods × N assets matrix of returns.
        max_deviation_threshold: Maximum tolerable deviation (default 5%).

    Returns:
        Dict with periods_to_threshold, threshold, and max_drift_at_threshold.
    """
    drifted = simulate_weight_drift(target_weights, returns_matrix)
    max_devs = compute_max_deviation(drifted, target_weights)

    for period, dev in enumerate(max_devs):
        if dev > max_deviation_threshold:
            return {
                "periods_to_threshold": period,
                "threshold": max_deviation_threshold,
                "max_drift_at_threshold": round(dev, 8),
            }

    # Threshold never exceeded
    n_periods = len(returns_matrix)
    final_dev = max_devs[-1] if max_devs else 0.0
    return {
        "periods_to_threshold": n_periods,
        "threshold": max_deviation_threshold,
        "max_drift_at_threshold": round(final_dev, 8),
    }


def analyze_decay(
    max_deviation_threshold: float = 0.05,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run portfolio decay analysis using stored weights and returns.

    Loads portfolio weights and per-asset returns, simulates weight drift,
    and computes tracking error and max deviation over time.

    Args:
        max_deviation_threshold: Threshold for optimal rebalance calculation.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Decay analysis with drift summary and optimal rebalance frequency.

    Raises:
        DecayError: If portfolio or returns data is missing.
    """
    if storage is None:
        storage = get_storage()

    # Load portfolio weights
    try:
        portfolio = storage.load_output("weights")
    except (StorageError, FileNotFoundError) as e:
        raise DecayError(
            "Portfolio weights not found", operation="load"
        ) from e

    weights_dict = portfolio.get("weights", {})
    if not weights_dict:
        raise DecayError("Portfolio has no weights", operation="validate")

    # Load returns data
    try:
        returns_data = storage.load_processed("returns")
    except (StorageError, FileNotFoundError) as e:
        raise DecayError(
            "Returns data not found", operation="load"
        ) from e

    per_asset = returns_data.get("per_asset", {})

    if not per_asset:
        raise DecayError("Returns data is empty", operation="validate")

    # Align symbols: only use symbols present in both weights and returns
    common_symbols = [s for s in weights_dict if s in per_asset]
    if not common_symbols:
        raise DecayError(
            "No common symbols between weights and returns", operation="validate"
        )

    # Normalize weights to common symbols
    raw_weights = [weights_dict[s] for s in common_symbols]
    total_w = sum(raw_weights)
    target_weights = [w / total_w for w in raw_weights] if total_w > 0 else raw_weights

    # Build returns matrix (T × N)
    series_lengths = [len(per_asset[s]) for s in common_symbols]
    n_periods = min(series_lengths) if series_lengths else 0

    returns_matrix: list[list[float]] = []
    for t in range(n_periods):
        row = [per_asset[s][t] for s in common_symbols]
        returns_matrix.append(row)

    # Simulate drift
    drifted = simulate_weight_drift(target_weights, returns_matrix)
    tracking_errors = compute_tracking_error(drifted, target_weights)
    max_deviations = compute_max_deviation(drifted, target_weights)

    # Build drift summary
    drift_summary: list[dict[str, Any]] = []
    for period in range(len(drifted)):
        drift_summary.append({
            "period": period,
            "tracking_error": tracking_errors[period],
            "max_deviation": max_deviations[period],
        })

    # Optimal rebalance frequency
    optimal = optimal_rebalance_frequency(
        target_weights, returns_matrix, max_deviation_threshold
    )

    target_weights_dict = {
        s: round(w, 6) for s, w in zip(common_symbols, target_weights)
    }

    result: dict[str, Any] = {
        "target_weights": target_weights_dict,
        "drift_summary": drift_summary,
        "optimal_rebalance": optimal,
        "n_assets": len(common_symbols),
        "n_periods": n_periods,
        "method": "decay_analysis",
    }

    if save:
        storage.save_output(result, "decay_analysis")
        logger.info(
            "Decay analysis: %d assets, %d periods, rebalance at %d",
            len(common_symbols),
            n_periods,
            optimal["periods_to_threshold"],
        )

    return result
