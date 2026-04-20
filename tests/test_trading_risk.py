"""Tests for src/trading/risk.py — sizing, cost gate, kill switch, position cap."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.trading.risk import (
    can_open_new_position,
    compute_position_qty,
    cost_within_budget,
    kill_switch_tripped,
)


@dataclass
class FakeLedger:
    realized_pnl: float = 0.0
    open_count: int = 0

    def get_realized_pnl_today(self, now_utc: datetime) -> float:
        return self.realized_pnl

    def get_open_position_count(self) -> int:
        return self.open_count


def test_compute_position_qty_happy_path() -> None:
    # 10_000 equity × 1% risk / 3% stop = ~3333 USDT notional; at entry 100 -> 33.33 qty
    qty = compute_position_qty(
        equity_usdt=10_000.0,
        risk_per_trade=0.01,
        stop_loss_pct=0.03,
        entry_price=100.0,
    )
    assert abs(qty - (10_000.0 * 0.01 / 0.03) / 100.0) < 1e-9


def test_compute_position_qty_returns_zero_on_nonpositive_inputs() -> None:
    assert compute_position_qty(0.0, 0.01, 0.03, 100.0) == 0.0
    assert compute_position_qty(10_000.0, 0.01, 0.03, 0.0) == 0.0


def test_cost_within_budget_rejects_trade_eating_risk_budget() -> None:
    # risk budget = 100 USDT. default fee=0.001 + slippage 5bps on 100_000 notional
    # fee = 100, slippage = 50 → total = 150 > 100 * 0.20 = 20
    assert cost_within_budget(
        notional_usdt=100_000.0,
        equity_usdt=10_000.0,
        risk_per_trade=0.01,
        max_cost_fraction_of_risk=0.20,
    ) is False


def test_cost_within_budget_accepts_small_trade() -> None:
    assert cost_within_budget(
        notional_usdt=100.0,
        equity_usdt=10_000.0,
        risk_per_trade=0.01,
        max_cost_fraction_of_risk=0.20,
    ) is True


def test_cost_within_budget_rejects_nonpositive_notional() -> None:
    assert cost_within_budget(
        notional_usdt=0.0, equity_usdt=10_000.0,
        risk_per_trade=0.01, max_cost_fraction_of_risk=0.20,
    ) is False


def test_kill_switch_tripped_when_loss_exceeds_threshold() -> None:
    ledger = FakeLedger(realized_pnl=-600.0)
    # 5% of 10_000 = 500. -600 <= -500 → tripped.
    assert kill_switch_tripped(
        ledger, starting_equity_usdt=10_000.0, max_daily_loss_pct=0.05,
        now_utc=datetime.now(UTC),
    ) is True


def test_kill_switch_not_tripped_within_threshold() -> None:
    ledger = FakeLedger(realized_pnl=-100.0)
    assert kill_switch_tripped(
        ledger, starting_equity_usdt=10_000.0, max_daily_loss_pct=0.05,
        now_utc=datetime.now(UTC),
    ) is False


def test_kill_switch_ignored_on_invalid_inputs() -> None:
    ledger = FakeLedger(realized_pnl=-5000.0)
    assert kill_switch_tripped(ledger, 0.0, 0.05) is False
    assert kill_switch_tripped(ledger, 10_000.0, 0.0) is False


def test_can_open_new_position_respects_cap() -> None:
    assert can_open_new_position(FakeLedger(open_count=5), max_open_positions=10) is True
    assert can_open_new_position(FakeLedger(open_count=10), max_open_positions=10) is False
