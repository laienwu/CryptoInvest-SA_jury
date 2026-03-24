"""
Portfolio drawdown analysis module.

Computes full drawdown time series, identifies drawdown periods (peak-to-trough
and recovery), and reports key statistics: max drawdown, average drawdown,
longest drawdown duration, and current drawdown state.

Uses backtest cumulative values as input.

Output: data/output/drawdown.json
"""

import logging
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class DrawdownError(Exception):
    """Error during drawdown analysis."""

    def __init__(self, message: str, *, operation: str = "drawdown") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def _compute_drawdown_series(values: list[float]) -> list[float]:
    """
    Compute drawdown at each time step.

    Returns list of drawdowns as negative fractions (e.g., -0.15 = 15% drawdown).
    Zero when at or above the running peak.
    """
    if not values:
        return []

    series: list[float] = []
    peak = values[0]

    for v in values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak if peak > 0 else 0.0
        series.append(round(dd, 8))

    return series


def _identify_drawdown_periods(
    drawdown_series: list[float],
    dates: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Identify distinct drawdown periods from a drawdown series.

    A period starts when drawdown goes below zero and ends when it returns to zero.

    Returns list of dicts with start/end indices, depth, and duration.
    """
    periods: list[dict[str, Any]] = []
    n = len(drawdown_series)
    i = 0

    while i < n:
        if drawdown_series[i] < 0:
            start = i
            trough_idx = i
            trough_val = drawdown_series[i]

            # Walk through the drawdown period
            while i < n and drawdown_series[i] < 0:
                if drawdown_series[i] < trough_val:
                    trough_val = drawdown_series[i]
                    trough_idx = i
                i += 1

            end = i - 1  # Last index still in drawdown
            recovered = i < n  # Did we recover to peak?

            period: dict[str, Any] = {
                "start_idx": start,
                "end_idx": end,
                "trough_idx": trough_idx,
                "max_drawdown": round(trough_val, 6),
                "duration": end - start + 1,
                "recovered": recovered,
            }

            if recovered:
                period["recovery_idx"] = i
                period["recovery_duration"] = i - trough_idx

            if dates:
                period["start_date"] = dates[start] if start < len(dates) else None
                period["end_date"] = dates[end] if end < len(dates) else None
                period["trough_date"] = (
                    dates[trough_idx] if trough_idx < len(dates) else None
                )
                if recovered and i < len(dates):
                    period["recovery_date"] = dates[i]

            periods.append(period)
        else:
            i += 1

    return periods


def compute_drawdown_analysis(
    values: list[float],
    dates: list[str] | None = None,
    strategy_name: str = "strategy",
) -> dict[str, Any]:
    """
    Compute full drawdown analysis for a value series.

    Args:
        values: Portfolio value series (e.g., cumulative values starting at 1.0).
        dates: Optional date labels for each value.
        strategy_name: Name of the strategy being analyzed.

    Returns:
        Dictionary with drawdown series, periods, and summary statistics.
    """
    if not values:
        return {
            "strategy": strategy_name,
            "drawdown_series": [],
            "periods": [],
            "summary": {
                "max_drawdown": 0.0,
                "avg_drawdown": 0.0,
                "n_periods": 0,
                "longest_duration": 0,
                "current_drawdown": 0.0,
                "time_in_drawdown_pct": 0.0,
            },
        }

    dd_series = _compute_drawdown_series(values)
    periods = _identify_drawdown_periods(dd_series, dates)

    # Summary stats
    max_dd = min(dd_series) if dd_series else 0.0
    in_drawdown = [d for d in dd_series if d < 0]
    avg_dd = sum(in_drawdown) / len(in_drawdown) if in_drawdown else 0.0
    longest = max((p["duration"] for p in periods), default=0)
    current_dd = dd_series[-1] if dd_series else 0.0
    time_in_dd_pct = len(in_drawdown) / len(dd_series) if dd_series else 0.0

    return {
        "strategy": strategy_name,
        "drawdown_series": dd_series,
        "dates": dates,
        "periods": periods,
        "summary": {
            "max_drawdown": round(max_dd, 6),
            "avg_drawdown": round(avg_dd, 6),
            "n_periods": len(periods),
            "longest_duration": longest,
            "current_drawdown": round(current_dd, 6),
            "time_in_drawdown_pct": round(time_in_dd_pct, 4),
        },
    }


def analyze_portfolio_drawdowns(
    portfolio_key: str = "backtest",
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run drawdown analysis on backtest results for all strategies.

    Args:
        portfolio_key: Storage key for backtest data.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Dictionary with per-strategy drawdown analyses and comparison.

    Raises:
        DrawdownError: If backtest data is missing or invalid.
    """
    if storage is None:
        storage = get_storage()

    try:
        backtest = storage.load_output(portfolio_key)
    except (StorageError, FileNotFoundError) as e:
        raise DrawdownError(
            f"Backtest data not found (key={portfolio_key})", operation="load"
        ) from e

    cumulative = backtest.get("cumulative_values", {})
    if not cumulative:
        raise DrawdownError(
            "Backtest has no cumulative_values", operation="validate"
        )

    dates = cumulative.get("dates")
    strategies: list[str] = [
        k for k in cumulative if k != "dates" and isinstance(cumulative[k], list)
    ]

    if not strategies:
        raise DrawdownError("No strategy series found", operation="validate")

    analyses: dict[str, Any] = {}
    for name in strategies:
        values = cumulative[name]
        analyses[name] = compute_drawdown_analysis(values, dates, name)

    # Comparison: rank by max drawdown (least negative = best)
    comparison = sorted(
        [
            {"strategy": name, "max_drawdown": a["summary"]["max_drawdown"]}
            for name, a in analyses.items()
        ],
        key=lambda x: x["max_drawdown"],
    )

    result: dict[str, Any] = {
        "analyses": analyses,
        "comparison": comparison,
        "n_strategies": len(strategies),
        "portfolio_key": portfolio_key,
    }

    if save:
        storage.save_output("drawdown", result)
        logger.info(
            "Drawdown analysis complete for %d strategies", len(strategies)
        )

    return result
