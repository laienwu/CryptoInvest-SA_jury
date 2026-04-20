"""
Automated trading package — Binance **testnet only**.

Mainnet is hard-blocked at the client layer (see ``binance_client.py``). This
module is intentionally narrow: load the daily universe, compute signals on
closed 5m candles, size positions at 1% of equity, place entry + stop-loss
orders, and persist the ledger. Invoked by Airflow every 5 minutes.

Default posture: ``TRADING_DRY_RUN=true`` — no real orders until opted out.

Public entry points:
    >>> from src.trading import run_tick
    >>> summary = run_tick()
    >>> summary["orders_placed"]
    3
"""

from src.trading.errors import (
    FilterViolationError,
    LedgerError,
    MainnetBlockedError,
    ReconciliationError,
    TradingError,
)
from src.trading.tick import run_tick

__all__ = [
    "FilterViolationError",
    "LedgerError",
    "MainnetBlockedError",
    "ReconciliationError",
    "TradingError",
    "run_tick",
]
