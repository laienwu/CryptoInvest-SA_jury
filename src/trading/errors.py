"""
Typed exceptions for the automated trading module.

Follows the repo convention of one exception class per concern with
typed context fields (see ``BinanceAPIError``, ``SymbolSelectorError``).
"""

from __future__ import annotations


class TradingError(Exception):
    """Base class for all trading-module errors."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


class MainnetBlockedError(TradingError):
    """Raised when any code path would touch Binance mainnet.

    This exception is the invariant that keeps the module safe. It is raised
    at ``BinanceClient`` init time before any network call so misconfiguration
    fails loudly, not silently at order time.
    """

    def __init__(self, message: str = "Mainnet trading is hard-blocked in this build"):
        super().__init__(message, operation="client_init")


class FilterViolationError(TradingError):
    """Order violates Binance symbol filters (LOT_SIZE, MIN_NOTIONAL, PRICE_FILTER)."""

    def __init__(self, message: str, symbol: str | None = None, filter_name: str | None = None):
        self.symbol = symbol
        self.filter_name = filter_name
        super().__init__(message, operation="filter_check")


class LedgerError(TradingError):
    """Persistence layer error (DuckDB ledger)."""

    def __init__(self, message: str, operation: str | None = None):
        super().__init__(message, operation=operation or "ledger")


class ReconciliationError(TradingError):
    """Exchange-to-ledger reconciliation disagreement that the tick cannot resolve."""

    def __init__(self, message: str):
        super().__init__(message, operation="reconcile")
