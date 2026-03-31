"""Tests for Kafka streaming producer and consumer."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock optional dependencies at sys.modules level so the modules can import
# ---------------------------------------------------------------------------

def _ensure_streaming_mocks():
    """Inject mock modules for websocket and kafka if not installed."""
    for mod_name in ("websocket", "kafka"):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()


_ensure_streaming_mocks()


class TestProducer:
    """Tests for stream_producer module."""

    def test_build_stream_url_single_symbol(self):
        from src.pipeline.stream_producer import _build_stream_url

        url = _build_stream_url(["BTCUSDT"])
        assert "btcusdt@kline_1d" in url
        assert url.startswith("wss://stream.binance.com")

    def test_build_stream_url_multiple_symbols(self):
        from src.pipeline.stream_producer import _build_stream_url

        url = _build_stream_url(["BTCUSDT", "ETHUSDT"], interval="1h")
        assert "btcusdt@kline_1h" in url
        assert "ethusdt@kline_1h" in url

    def test_parse_kline_event_closed_candle(self):
        from src.pipeline.stream_producer import _parse_kline_event

        event = {
            "e": "kline",
            "k": {
                "s": "BTCUSDT",
                "t": 1704067200000,  # 2024-01-01 UTC
                "o": "42000.0",
                "h": "43000.0",
                "l": "41000.0",
                "c": "42500.0",
                "v": "100.5",
                "x": True,  # Closed candle
            },
        }
        result = _parse_kline_event(event)
        assert result is not None
        assert result["symbol"] == "BTCUSDT"
        assert result["timestamp"] == "2024-01-01"
        assert result["open"] == 42000.0
        assert result["close"] == 42500.0
        assert result["volume"] == 100.5

    def test_parse_kline_event_open_candle_skipped(self):
        from src.pipeline.stream_producer import _parse_kline_event

        event = {
            "e": "kline",
            "k": {"s": "BTCUSDT", "t": 1704067200000, "o": "42000", "h": "43000", "l": "41000", "c": "42500", "v": "100", "x": False},
        }
        result = _parse_kline_event(event)
        assert result is None

    def test_parse_kline_event_non_kline_skipped(self):
        from src.pipeline.stream_producer import _parse_kline_event

        result = _parse_kline_event({"e": "trade", "data": {}})
        assert result is None


class TestConsumer:
    """Tests for stream_consumer module."""

    def test_flush_buffer_new_file(self, tmp_path):
        from src.pipeline.stream_consumer import _flush_buffer

        buffer = {
            "BTCUSDT": [
                {"timestamp": "2024-01-01", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 100.0},
                {"timestamp": "2024-01-02", "open": 42500.0, "high": 44000.0, "low": 42000.0, "close": 43500.0, "volume": 150.0},
            ]
        }
        flushed = _flush_buffer(buffer, tmp_path)
        assert flushed == 2
        assert (tmp_path / "raw" / "klines" / "BTCUSDT.parquet").exists()

    def test_flush_buffer_deduplicates(self, tmp_path):
        from src.pipeline.stream_consumer import _flush_buffer

        records = [
            {"timestamp": "2024-01-01", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 100.0},
        ]
        # First flush
        _flush_buffer({"BTCUSDT": records}, tmp_path)
        # Second flush with same data
        flushed = _flush_buffer({"BTCUSDT": records}, tmp_path)
        assert flushed == 0  # Nothing new

    def test_flush_buffer_merges_with_existing(self, tmp_path):
        from src.pipeline.stream_consumer import _flush_buffer

        # First batch
        batch1 = {"BTCUSDT": [
            {"timestamp": "2024-01-01", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 100.0},
        ]}
        _flush_buffer(batch1, tmp_path)

        # Second batch with new + duplicate
        batch2 = {"BTCUSDT": [
            {"timestamp": "2024-01-01", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 100.0},
            {"timestamp": "2024-01-02", "open": 43000.0, "high": 44000.0, "low": 42000.0, "close": 43500.0, "volume": 120.0},
        ]}
        flushed = _flush_buffer(batch2, tmp_path)
        assert flushed == 1  # Only the new one

    def test_flush_empty_buffer(self, tmp_path):
        from src.pipeline.stream_consumer import _flush_buffer

        flushed = _flush_buffer({}, tmp_path)
        assert flushed == 0

    def test_load_existing_timestamps_no_file(self, tmp_path):
        from src.pipeline.stream_consumer import _load_existing_timestamps

        result = _load_existing_timestamps(tmp_path / "nonexistent.parquet")
        assert result == set()


class TestOrderBookProducer:
    """Tests for order book depth producer."""

    def test_build_orderbook_stream_url_single(self):
        from src.pipeline.stream_producer import _build_orderbook_stream_url

        url = _build_orderbook_stream_url(["BTCUSDT"])
        assert "btcusdt@depth20@100ms" in url
        assert url.startswith("wss://stream.binance.com")

    def test_build_orderbook_stream_url_multiple(self):
        from src.pipeline.stream_producer import _build_orderbook_stream_url

        url = _build_orderbook_stream_url(["BTCUSDT", "ETHUSDT"])
        assert "btcusdt@depth20@100ms" in url
        assert "ethusdt@depth20@100ms" in url

    def test_parse_orderbook_event_valid(self):
        from src.pipeline.stream_producer import _parse_orderbook_event

        event = {
            "bids": [["42000.0", "1.5"], ["41999.0", "2.0"]],
            "asks": [["42001.0", "1.0"], ["42002.0", "3.0"]],
        }
        result = _parse_orderbook_event(event, "BTCUSDT")
        assert result is not None
        assert result["symbol"] == "BTCUSDT"
        assert result["spread"] == pytest.approx(1.0, abs=0.01)
        assert result["mid_price"] == pytest.approx(42000.5, abs=0.01)
        assert len(result["bids"]) == 2
        assert len(result["asks"]) == 2
        assert result["bid_depth"] == pytest.approx(3.5, abs=0.01)
        assert result["ask_depth"] == pytest.approx(4.0, abs=0.01)

    def test_parse_orderbook_event_empty_bids(self):
        from src.pipeline.stream_producer import _parse_orderbook_event

        event = {"bids": [], "asks": [["42001.0", "1.0"]]}
        result = _parse_orderbook_event(event, "BTCUSDT")
        assert result is None

    def test_parse_orderbook_event_empty_asks(self):
        from src.pipeline.stream_producer import _parse_orderbook_event

        event = {"bids": [["42000.0", "1.5"]], "asks": []}
        result = _parse_orderbook_event(event, "BTCUSDT")
        assert result is None

    def test_parse_orderbook_event_no_data(self):
        from src.pipeline.stream_producer import _parse_orderbook_event

        result = _parse_orderbook_event({}, "BTCUSDT")
        assert result is None


class TestOrderBookConsumer:
    """Tests for order book depth consumer."""

    def test_flush_orderbook_buffer_empty(self, tmp_path):
        from src.pipeline.stream_consumer import _flush_orderbook_buffer

        flushed = _flush_orderbook_buffer([], tmp_path)
        assert flushed == 0

    def test_flush_orderbook_buffer_writes_parquet(self, tmp_path):
        from src.pipeline.stream_consumer import _flush_orderbook_buffer

        buffer = [
            {
                "symbol": "BTCUSDT",
                "timestamp": "2024-01-01T12:00:00",
                "bids": [["42000.0", "1.5"]],
                "asks": [["42001.0", "1.0"]],
                "spread": 1.0,
                "mid_price": 42000.5,
                "bid_depth": 1.5,
                "ask_depth": 1.0,
            },
            {
                "symbol": "ETHUSDT",
                "timestamp": "2024-01-01T12:00:00",
                "bids": [["2200.0", "10.0"]],
                "asks": [["2201.0", "5.0"]],
                "spread": 1.0,
                "mid_price": 2200.5,
                "bid_depth": 10.0,
                "ask_depth": 5.0,
            },
        ]
        flushed = _flush_orderbook_buffer(buffer, tmp_path)
        assert flushed == 2
        parquet_files = list(tmp_path.glob("orderbook_*.parquet"))
        assert len(parquet_files) == 1

    def test_flush_orderbook_buffer_creates_directory(self, tmp_path):
        from src.pipeline.stream_consumer import _flush_orderbook_buffer

        output_dir = tmp_path / "streaming" / "orderbook"
        buffer = [
            {
                "symbol": "BTCUSDT",
                "timestamp": "2024-01-01T12:00:00",
                "bids": [["42000.0", "1.5"]],
                "asks": [["42001.0", "1.0"]],
                "spread": 1.0,
                "mid_price": 42000.5,
                "bid_depth": 1.5,
                "ask_depth": 1.0,
            },
        ]
        _flush_orderbook_buffer(buffer, output_dir)
        assert output_dir.exists()
