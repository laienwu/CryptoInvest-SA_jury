"""Tests for Kafka streaming producer and consumer."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


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
