"""Tests for src/trading/strategy.py — SMA crossover strategy wrapper."""

from __future__ import annotations

from src.trading.strategy import SmaCrossoverStrategy


def test_hold_when_insufficient_history() -> None:
    s = SmaCrossoverStrategy(short_window=5, long_window=20)
    assert s.generate_signal([1.0] * 10) == "HOLD"


def test_buy_when_fast_crosses_above_slow() -> None:
    s = SmaCrossoverStrategy(short_window=3, long_window=5)
    # Flat low, then a ramp that pulls the short avg above the long avg.
    closes = [10.0] * 10 + [20.0, 22.0, 24.0, 26.0, 28.0]
    assert s.generate_signal(closes) == "BUY"


def test_sell_when_fast_crosses_below_slow() -> None:
    s = SmaCrossoverStrategy(short_window=3, long_window=5)
    closes = [30.0] * 10 + [20.0, 18.0, 16.0, 14.0, 12.0]
    assert s.generate_signal(closes) == "SELL"


def test_hold_when_no_crossover() -> None:
    s = SmaCrossoverStrategy(short_window=3, long_window=5)
    closes = [10.0] * 20
    assert s.generate_signal(closes) == "HOLD"
