"""
Risk / sizing helpers. Pure functions — no IO.

Position sizing reuses ``src/pipeline/position_sizing.py:fixed_fractional``;
transaction costs reuse ``src/pipeline/costs.py:estimate_trade_cost``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from src.pipeline.costs import estimate_trade_cost
from src.pipeline.position_sizing import fixed_fractional


class LedgerProtocol(Protocol):
    """Minimal surface ``risk`` needs from the ledger (keeps risk.py IO-free)."""

    def get_realized_pnl_today(self, now_utc: datetime) -> float: ...
    def get_open_position_count(self) -> int: ...


def compute_position_qty(
    equity_usdt: float,
    risk_per_trade: float,
    stop_loss_pct: float,
    entry_price: float,
) -> float:
    """
    Convert the fixed-fractional USD sizing into a base-asset quantity.

    Returns 0.0 if equity or entry price is non-positive.
    """
    if equity_usdt <= 0 or entry_price <= 0:
        return 0.0
    notional_usdt = fixed_fractional(equity_usdt, risk_per_trade, stop_loss_pct)
    return notional_usdt / entry_price


def cost_within_budget(
    notional_usdt: float,
    equity_usdt: float,
    risk_per_trade: float,
    max_cost_fraction_of_risk: float,
    fee_rate: float = 0.001,
    slippage_bps: float = 5.0,
) -> bool:
    """
    True if expected round-trip cost leaves enough of the risk budget to matter.

    Burns the trade if fees + slippage consume more than
    ``max_cost_fraction_of_risk`` of the dollar risk budget.
    """
    if notional_usdt <= 0:
        return False
    budget_usdt = equity_usdt * risk_per_trade
    if budget_usdt <= 0:
        return False
    cost = estimate_trade_cost(notional_usdt, fee_rate=fee_rate, slippage_bps=slippage_bps)
    return cost["total_cost"] <= budget_usdt * max_cost_fraction_of_risk


def kill_switch_tripped(
    ledger: LedgerProtocol,
    starting_equity_usdt: float,
    max_daily_loss_pct: float,
    now_utc: datetime | None = None,
) -> bool:
    """True if today's realised P&L is worse than ``-max_daily_loss_pct × equity``."""
    if starting_equity_usdt <= 0 or max_daily_loss_pct <= 0:
        return False
    now = now_utc or datetime.now(UTC)
    pnl = ledger.get_realized_pnl_today(now)
    threshold = -abs(max_daily_loss_pct) * starting_equity_usdt
    return pnl <= threshold


def can_open_new_position(ledger: LedgerProtocol, max_open_positions: int) -> bool:
    """True if we're below the max concurrent position cap."""
    return ledger.get_open_position_count() < max_open_positions
