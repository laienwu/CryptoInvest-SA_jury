"""
Tests for src/pipeline/symbol_selector.py

All HTTP calls to Binance are mocked — no real network traffic.
Covers filter gates, ranking determinism, malformed payloads,
min_universe_size guard, and persistence via the Storage ABC.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.config import SymbolSelectorConfig
from src.pipeline.symbol_selector import (
    SymbolSelectorError,
    _filter_pairs,
    _rank_and_select,
    fetch_24h_tickers,
    fetch_trading_symbols,
    select_universe,
)


# =============================================================================
# Helpers
# =============================================================================


def _ticker(
    symbol: str,
    quote_volume: float = 1e8,
    high: float = 110.0,
    low: float = 100.0,
    pct: float = 2.0,
) -> dict[str, Any]:
    """Build a Binance /ticker/24hr record with sensible defaults."""
    return {
        "symbol": symbol,
        "quoteVolume": str(quote_volume),
        "highPrice": str(high),
        "lowPrice": str(low),
        "priceChangePercent": str(pct),
    }


def _default_cfg(**overrides: Any) -> SymbolSelectorConfig:
    """SymbolSelectorConfig with low thresholds so hand-built tickers pass easily."""
    base = {
        "min_quote_volume": 1_000_000.0,
        "min_daily_range": 0.02,
        "min_abs_price_change_pct": 1.0,
        "momentum_filter_enabled": True,
        "top_n": 30,
        "min_universe_size": 1,
    }
    base.update(overrides)
    return SymbolSelectorConfig(**base)


def _trading_set(tickers: list[dict[str, Any]]) -> set[str]:
    return {t["symbol"] for t in tickers}


# =============================================================================
# SymbolSelectorError
# =============================================================================


def test_symbol_selector_error_fields() -> None:
    err = SymbolSelectorError("boom", operation="fetch")
    assert err.message == "boom"
    assert err.operation == "fetch"
    assert str(err) == "boom"


# =============================================================================
# Fetchers
# =============================================================================


def test_fetch_24h_tickers_returns_list() -> None:
    payload = [_ticker("BTCUSDT"), _ticker("ETHUSDT")]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload

    with patch("requests.get", return_value=mock_response):
        result = fetch_24h_tickers("https://api.binance.com")

    assert result == payload


def test_fetch_24h_tickers_rejects_non_list_payload() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "nope"}

    with patch("requests.get", return_value=mock_response):
        with pytest.raises(SymbolSelectorError):
            fetch_24h_tickers("https://api.binance.com")


def test_fetch_trading_symbols_filters_by_status() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "symbols": [
            {"symbol": "BTCUSDT", "status": "TRADING"},
            {"symbol": "DEADUSDT", "status": "BREAK"},
            {"symbol": "HALTUSDT", "status": "HALT"},
            {"symbol": "ETHUSDT", "status": "TRADING"},
        ]
    }

    with patch("requests.get", return_value=mock_response):
        result = fetch_trading_symbols("https://api.binance.com")

    assert result == {"BTCUSDT", "ETHUSDT"}


def test_fetch_trading_symbols_rejects_malformed_payload() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"unexpected": "shape"}

    with patch("requests.get", return_value=mock_response):
        with pytest.raises(SymbolSelectorError):
            fetch_trading_symbols("https://api.binance.com")


# =============================================================================
# _filter_pairs — one gate at a time
# =============================================================================


def test_filter_rejects_non_usdt_quote() -> None:
    tickers = [_ticker("BTCUSDT"), _ticker("ETHBTC"), _ticker("BNBBUSD")]
    result = _filter_pairs(tickers, _trading_set(tickers), _default_cfg())
    assert [t["symbol"] for t in result] == ["BTCUSDT"]


def test_filter_rejects_leveraged_tokens() -> None:
    tickers = [
        _ticker("BTCUSDT"),
        _ticker("BTCUPUSDT"),     # UP suffix on base → leveraged
        _ticker("ETHDOWNUSDT"),   # DOWN suffix
        _ticker("XRPBULLUSDT"),   # BULL suffix
        _ticker("XRPBEARUSDT"),   # BEAR suffix
    ]
    result = _filter_pairs(tickers, _trading_set(tickers), _default_cfg())
    assert [t["symbol"] for t in result] == ["BTCUSDT"]


def test_filter_rejects_stablecoin_blocklist() -> None:
    tickers = [
        _ticker("BTCUSDT"),
        _ticker("USDCUSDT"),
        _ticker("DAIUSDT"),
        _ticker("FDUSDUSDT"),
    ]
    result = _filter_pairs(tickers, _trading_set(tickers), _default_cfg())
    assert [t["symbol"] for t in result] == ["BTCUSDT"]


def test_filter_rejects_non_trading_status() -> None:
    tickers = [_ticker("BTCUSDT"), _ticker("HALTEDUSDT")]
    trading = {"BTCUSDT"}  # HALTEDUSDT absent → filtered
    result = _filter_pairs(tickers, trading, _default_cfg())
    assert [t["symbol"] for t in result] == ["BTCUSDT"]


def test_filter_rejects_illiquid_symbols() -> None:
    cfg = _default_cfg(min_quote_volume=100_000_000.0)
    tickers = [
        _ticker("BTCUSDT", quote_volume=2e8),
        _ticker("POORUSDT", quote_volume=1e6),   # below floor
    ]
    result = _filter_pairs(tickers, _trading_set(tickers), cfg)
    assert [t["symbol"] for t in result] == ["BTCUSDT"]


def test_filter_rejects_low_daily_range() -> None:
    cfg = _default_cfg(min_daily_range=0.05)
    tickers = [
        _ticker("BTCUSDT", high=110.0, low=100.0),  # range=10%
        _ticker("FLATUSDT", high=101.0, low=100.0),  # range=1%
    ]
    result = _filter_pairs(tickers, _trading_set(tickers), cfg)
    assert [t["symbol"] for t in result] == ["BTCUSDT"]


def test_filter_rejects_weak_momentum() -> None:
    cfg = _default_cfg(min_abs_price_change_pct=5.0)
    tickers = [
        _ticker("BTCUSDT", pct=6.0),
        _ticker("BORINGUSDT", pct=0.5),
        _ticker("NEGUSDT", pct=-6.0),  # absolute value matters
    ]
    result = _filter_pairs(tickers, _trading_set(tickers), cfg)
    assert sorted(t["symbol"] for t in result) == ["BTCUSDT", "NEGUSDT"]


def test_filter_can_disable_momentum_gate() -> None:
    cfg = _default_cfg(momentum_filter_enabled=False, min_abs_price_change_pct=99.0)
    tickers = [_ticker("BTCUSDT", pct=0.1)]
    result = _filter_pairs(tickers, _trading_set(tickers), cfg)
    assert [t["symbol"] for t in result] == ["BTCUSDT"]
    assert result[0]["daily_range"] == pytest.approx(0.1)


# =============================================================================
# Malformed payload handling
# =============================================================================


def test_filter_skips_missing_numeric_fields() -> None:
    tickers = [
        _ticker("BTCUSDT"),
        {"symbol": "BADUSDT", "quoteVolume": "not-a-number"},
        {"symbol": "LOWZEROUSDT", "quoteVolume": "1e9", "highPrice": "100", "lowPrice": "0",
         "priceChangePercent": "3"},
        {"symbol": "MISSINGUSDT"},  # no prices at all
    ]
    result = _filter_pairs(tickers, _trading_set(tickers), _default_cfg())
    assert [t["symbol"] for t in result] == ["BTCUSDT"]


def test_filter_skips_non_string_symbol() -> None:
    tickers = [_ticker("BTCUSDT"), {"symbol": None, "quoteVolume": "1e9"}]
    result = _filter_pairs(tickers, _trading_set(tickers), _default_cfg())
    assert [t["symbol"] for t in result] == ["BTCUSDT"]


# =============================================================================
# Ranking
# =============================================================================


def test_rank_orders_by_score_descending() -> None:
    filtered = [
        {"symbol": "A", "quoteVolume": 1e8, "daily_range": 0.05, "priceChangePercent": 3.0},
        {"symbol": "B", "quoteVolume": 2e8, "daily_range": 0.05, "priceChangePercent": 3.0},
        {"symbol": "C", "quoteVolume": 1e8, "daily_range": 0.10, "priceChangePercent": 3.0},
    ]
    result = _rank_and_select(filtered, top_n=3)
    # scores: A=5e6, B=1e7, C=1e7 → B and C tie, C after B by alpha
    assert [t["symbol"] for t in result] == ["B", "C", "A"]


def test_rank_tie_break_is_alphabetical() -> None:
    filtered = [
        {"symbol": "ZZZUSDT", "quoteVolume": 1e8, "daily_range": 0.05, "priceChangePercent": 3.0},
        {"symbol": "AAAUSDT", "quoteVolume": 1e8, "daily_range": 0.05, "priceChangePercent": 3.0},
        {"symbol": "MMMUSDT", "quoteVolume": 1e8, "daily_range": 0.05, "priceChangePercent": 3.0},
    ]
    result = _rank_and_select(filtered, top_n=3)
    assert [t["symbol"] for t in result] == ["AAAUSDT", "MMMUSDT", "ZZZUSDT"]


def test_rank_respects_top_n() -> None:
    filtered = [
        {"symbol": f"SYM{i}USDT", "quoteVolume": 1e8, "daily_range": 0.01 * (i + 1),
         "priceChangePercent": 3.0}
        for i in range(10)
    ]
    result = _rank_and_select(filtered, top_n=3)
    assert len(result) == 3


# =============================================================================
# select_universe orchestration
# =============================================================================


def _make_storage_mock() -> MagicMock:
    storage = MagicMock()
    storage.save_output.return_value = "ok"
    return storage


def test_select_universe_happy_path_persists_two_keys() -> None:
    tickers = [
        _ticker("BTCUSDT", quote_volume=2e9, high=120, low=100, pct=5.0),
        _ticker("ETHUSDT", quote_volume=1e9, high=110, low=100, pct=4.0),
        _ticker("SOLUSDT", quote_volume=5e8, high=105, low=100, pct=3.0),
    ]
    cfg = _default_cfg(top_n=3, min_universe_size=1)
    storage = _make_storage_mock()
    fixed = datetime(2026, 4, 19, 0, 5, tzinfo=UTC)

    with patch("src.pipeline.symbol_selector.fetch_24h_tickers", return_value=tickers), \
         patch("src.pipeline.symbol_selector.fetch_trading_symbols",
               return_value={"BTCUSDT", "ETHUSDT", "SOLUSDT"}):
        payload = select_universe(storage=storage, cfg=cfg, selected_at=fixed)

    assert payload["symbols"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert payload["universe_size"] == 3
    assert payload["selected_at"] == fixed.isoformat()
    assert payload["thresholds"]["top_n"] == 3

    keys = [call.args[1] for call in storage.save_output.call_args_list]
    assert keys == ["universe_20260419", "universe_latest"]


def test_select_universe_raises_when_below_min_size() -> None:
    cfg = _default_cfg(min_universe_size=10, top_n=30)
    tickers = [_ticker("BTCUSDT", quote_volume=2e9, high=120, low=100, pct=5.0)]
    storage = _make_storage_mock()

    with patch("src.pipeline.symbol_selector.fetch_24h_tickers", return_value=tickers), \
         patch("src.pipeline.symbol_selector.fetch_trading_symbols", return_value={"BTCUSDT"}):
        with pytest.raises(SymbolSelectorError) as exc_info:
            select_universe(storage=storage, cfg=cfg)

    assert exc_info.value.operation == "rank_and_select"
    storage.save_output.assert_not_called()


def test_select_universe_payload_records_thresholds() -> None:
    tickers = [_ticker(f"SYM{i}USDT", quote_volume=1e9 * (i + 1),
                       high=110 + i, low=100, pct=3.0) for i in range(5)]
    trading = {t["symbol"] for t in tickers}
    cfg = _default_cfg(top_n=5, min_universe_size=1)
    storage = _make_storage_mock()

    with patch("src.pipeline.symbol_selector.fetch_24h_tickers", return_value=tickers), \
         patch("src.pipeline.symbol_selector.fetch_trading_symbols", return_value=trading):
        payload = select_universe(storage=storage, cfg=cfg,
                                  selected_at=datetime(2026, 4, 19, tzinfo=UTC))

    thresholds = payload["thresholds"]
    assert thresholds["min_quote_volume"] == cfg.min_quote_volume
    assert thresholds["min_daily_range"] == cfg.min_daily_range
    assert thresholds["stablecoin_blocklist"] == list(cfg.stablecoin_blocklist)
    assert payload["source_snapshot_url"].endswith("/api/v3/ticker/24hr")

    for row in payload["universe"]:
        assert row["score"] == pytest.approx(row["quoteVolume"] * row["daily_range"])
