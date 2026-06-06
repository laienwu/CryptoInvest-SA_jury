"""
Trading strategies (pluggable via the Strategy Protocol).

This PR ships a single implementation — SMA crossover over closed 5m bars —
wrapping the existing ``src/pipeline/signals.py:sma_crossover_signal`` so
there's a single source of truth for indicator math.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from src.pipeline.signals import sma_crossover_signal

Signal = Literal["BUY", "SELL", "HOLD"]


class Strategy(Protocol):
    """
    A strategy maps a history of closed-bar closes to a single latest signal.

    Implementations must be pure (no IO, no globals) so they are trivially
    testable and swappable.
    """

    @property
    def name(self) -> str:
        """Identifier recorded on every trade row in the ledger."""
        ...

    @property
    def startup_candle_count(self) -> int:
        """Minimum number of closed bars required before a signal is meaningful."""
        ...

    def generate_signal(self, closes: list[float]) -> Signal:
        """Return BUY / SELL / HOLD for the most recent *closed* bar."""
        ...


@dataclass(frozen=True)
class SmaCrossoverStrategy:
    """Classic fast/slow SMA crossover. BUY when fast > slow, SELL when fast < slow."""

    short_window: int = 20
    long_window: int = 50
    name: str = "sma_crossover"

    @property
    def startup_candle_count(self) -> int:
        """Enough bars to compute the slow SMA (the longer window gates signals)."""
        return self.long_window

    def generate_signal(self, closes: list[float]) -> Signal:
        if len(closes) < self.long_window:
            return "HOLD"
        signals = sma_crossover_signal(closes, self.short_window, self.long_window)
        latest = signals[-1]
        if latest in ("BUY", "SELL"):
            return latest  # type: ignore[return-value]
        return "HOLD"
