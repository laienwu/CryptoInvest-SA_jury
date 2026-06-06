"""
Binance symbol filter helpers (LOT_SIZE, MIN_NOTIONAL, PRICE_FILTER).

Every order must be quantized to the symbol's step/tick sizes and meet
the minimum notional before being sent, otherwise Binance rejects it.
Pure functions — no IO.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.trading.errors import FilterViolationError


@dataclass(frozen=True)
class SymbolFilters:
    """Precision / minimum constraints for a single trading pair."""

    symbol: str
    step_size: float         # LOT_SIZE.stepSize — qty increment
    min_qty: float           # LOT_SIZE.minQty
    max_qty: float           # LOT_SIZE.maxQty
    tick_size: float         # PRICE_FILTER.tickSize — price increment
    min_notional: float      # MIN_NOTIONAL.minNotional


def parse_symbol_filters(symbol: str, filters: list[dict[str, Any]]) -> SymbolFilters:
    """
    Extract the three relevant filters from an exchangeInfo ``filters`` array.

    Raises FilterViolationError if any of LOT_SIZE / PRICE_FILTER is missing,
    since we cannot safely size an order without them. MIN_NOTIONAL is optional
    on some pairs and defaults to 0.0.
    """
    by_type = {f.get("filterType"): f for f in filters if isinstance(f, dict)}

    lot = by_type.get("LOT_SIZE")
    price = by_type.get("PRICE_FILTER")
    if lot is None or price is None:
        missing = [n for n, f in (("LOT_SIZE", lot), ("PRICE_FILTER", price)) if f is None]
        raise FilterViolationError(
            f"{symbol}: missing required filters {missing}",
            symbol=symbol,
            filter_name=missing[0] if missing else None,
        )

    # NOTIONAL replaces MIN_NOTIONAL on newer Binance endpoints — accept either.
    notional = by_type.get("MIN_NOTIONAL") or by_type.get("NOTIONAL")
    min_notional = float(notional.get("minNotional", 0.0)) if notional else 0.0

    return SymbolFilters(
        symbol=symbol,
        step_size=float(lot["stepSize"]),
        min_qty=float(lot["minQty"]),
        max_qty=float(lot["maxQty"]),
        tick_size=float(price["tickSize"]),
        min_notional=min_notional,
    )


def _precision_from_step(step: float) -> int:
    """Decimal places required to represent ``step`` exactly."""
    if step >= 1.0:
        return 0
    # Avoid float fuzz: rely on string rep of a well-formed exchange step.
    step_str = f"{step:.12f}".rstrip("0").rstrip(".")
    if "." not in step_str:
        return 0
    return len(step_str.split(".")[1])


def quantize_qty(qty: float, step_size: float) -> float:
    """Floor ``qty`` to the nearest multiple of ``step_size``."""
    if step_size <= 0:
        return qty
    steps = math.floor(qty / step_size)
    precision = _precision_from_step(step_size)
    return round(steps * step_size, precision)


def quantize_price(price: float, tick_size: float) -> float:
    """Floor ``price`` to the nearest multiple of ``tick_size``."""
    if tick_size <= 0:
        return price
    ticks = math.floor(price / tick_size)
    precision = _precision_from_step(tick_size)
    return round(ticks * tick_size, precision)


def passes_min_notional(qty: float, price: float, min_notional: float) -> bool:
    """True if qty × price meets Binance's MIN_NOTIONAL (or no minimum is set)."""
    if min_notional <= 0:
        return True
    return qty * price >= min_notional


def ensure_order_valid(qty: float, price: float, f: SymbolFilters) -> None:
    """Raise FilterViolationError if the order cannot be placed under Binance rules."""
    if qty < f.min_qty:
        raise FilterViolationError(
            f"{f.symbol}: qty {qty} below minQty {f.min_qty}",
            symbol=f.symbol,
            filter_name="LOT_SIZE",
        )
    if qty > f.max_qty:
        raise FilterViolationError(
            f"{f.symbol}: qty {qty} above maxQty {f.max_qty}",
            symbol=f.symbol,
            filter_name="LOT_SIZE",
        )
    if not passes_min_notional(qty, price, f.min_notional):
        raise FilterViolationError(
            f"{f.symbol}: notional {qty * price:.8f} below minNotional {f.min_notional}",
            symbol=f.symbol,
            filter_name="MIN_NOTIONAL",
        )
