"""Tests for src/trading/filters.py — symbol filter parsing and quantization."""

from __future__ import annotations

import pytest

from src.trading.errors import FilterViolationError
from src.trading.filters import (
    SymbolFilters,
    ensure_order_valid,
    parse_symbol_filters,
    passes_min_notional,
    quantize_price,
    quantize_qty,
)


def test_quantize_qty_floors_to_step() -> None:
    assert quantize_qty(1.2345, 0.001) == 1.234
    assert quantize_qty(1.2349, 0.001) == 1.234
    assert quantize_qty(1.0, 0.1) == 1.0
    assert quantize_qty(0.5, 1.0) == 0.0


def test_quantize_price_floors_to_tick() -> None:
    assert quantize_price(100.567, 0.01) == 100.56
    assert quantize_price(100.0, 0.5) == 100.0
    assert quantize_price(0.00001234, 0.00000001) == 0.00001234


def test_quantize_handles_nonpositive_step() -> None:
    assert quantize_qty(1.23, 0.0) == 1.23
    assert quantize_price(1.23, -1.0) == 1.23


def test_passes_min_notional() -> None:
    assert passes_min_notional(qty=1.0, price=10.0, min_notional=5.0) is True
    assert passes_min_notional(qty=1.0, price=4.0, min_notional=5.0) is False
    assert passes_min_notional(qty=1.0, price=10.0, min_notional=0.0) is True


def _filters(**overrides: object) -> SymbolFilters:
    base = dict(
        symbol="BTCUSDT",
        step_size=0.001,
        min_qty=0.001,
        max_qty=1000.0,
        tick_size=0.01,
        min_notional=10.0,
    )
    base.update(overrides)
    return SymbolFilters(**base)  # type: ignore[arg-type]


def test_ensure_order_valid_rejects_below_min_qty() -> None:
    with pytest.raises(FilterViolationError):
        ensure_order_valid(0.0, price=100.0, f=_filters())


def test_ensure_order_valid_rejects_above_max_qty() -> None:
    with pytest.raises(FilterViolationError):
        ensure_order_valid(2000.0, price=100.0, f=_filters())


def test_ensure_order_valid_rejects_below_min_notional() -> None:
    with pytest.raises(FilterViolationError):
        ensure_order_valid(0.05, price=100.0, f=_filters(min_notional=10.0))


def test_ensure_order_valid_passes_valid_order() -> None:
    ensure_order_valid(1.0, price=100.0, f=_filters())  # must not raise


def test_parse_symbol_filters_reads_lot_price_notional() -> None:
    filters_payload = [
        {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "100"},
        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
        {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
    ]
    f = parse_symbol_filters("BTCUSDT", filters_payload)
    assert f.step_size == 0.001
    assert f.tick_size == 0.01
    assert f.min_notional == 10.0


def test_parse_symbol_filters_accepts_notional_alias() -> None:
    filters_payload = [
        {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "100"},
        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
        {"filterType": "NOTIONAL", "minNotional": "5"},
    ]
    f = parse_symbol_filters("BTCUSDT", filters_payload)
    assert f.min_notional == 5.0


def test_parse_symbol_filters_raises_without_lot_size() -> None:
    with pytest.raises(FilterViolationError):
        parse_symbol_filters("BTCUSDT", [
            {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
        ])


def test_parse_symbol_filters_defaults_notional_zero() -> None:
    f = parse_symbol_filters("BTCUSDT", [
        {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "100"},
        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
    ])
    assert f.min_notional == 0.0
