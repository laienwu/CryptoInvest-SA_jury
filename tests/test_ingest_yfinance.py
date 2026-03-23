"""
Tests for yfinance data ingestion module.

Tests:
- fetch_yfinance_klines output format
- ingest_yfinance_data multi-symbol fetch
- ingest_yfinance_incremental dedup/merge logic
- YFinanceError exception fields
"""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.ingest_yfinance import (
    YFinanceError,
    fetch_yfinance_klines,
    ingest_yfinance_data,
    ingest_yfinance_incremental,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_mock_df(rows: list[dict]) -> MagicMock:
    """Build a mock DataFrame that behaves like yfinance output."""
    df = MagicMock()
    df.empty = len(rows) == 0
    df.__bool__ = lambda self: True  # `if df is None` check

    def iterrows():
        for row in rows:
            idx = MagicMock()
            idx.strftime = MagicMock(return_value=row["timestamp"])
            yield idx, {
                "Open": row["open"],
                "High": row["high"],
                "Low": row["low"],
                "Close": row["close"],
                "Volume": row["volume"],
            }

    df.iterrows = iterrows
    return df


def _mock_yf_module(ticker_mock: MagicMock) -> MagicMock:
    """Create a mock yfinance module with the given Ticker behaviour."""
    yf = MagicMock()
    yf.Ticker = ticker_mock
    return yf


SAMPLE_ROWS = [
    {
        "timestamp": "2025-01-01",
        "open": 470.0,
        "high": 475.0,
        "low": 468.0,
        "close": 472.0,
        "volume": 1_000_000.0,
    },
    {
        "timestamp": "2025-01-02",
        "open": 472.0,
        "high": 478.0,
        "low": 471.0,
        "close": 477.0,
        "volume": 1_200_000.0,
    },
]


# =============================================================================
# YFinanceError
# =============================================================================


class TestYFinanceError:
    def test_has_message_and_symbol(self):
        err = YFinanceError("test error", symbol="SPY")
        assert err.message == "test error"
        assert err.symbol == "SPY"
        assert str(err) == "test error"

    def test_symbol_defaults_to_none(self):
        err = YFinanceError("generic")
        assert err.symbol is None


# =============================================================================
# fetch_yfinance_klines
# =============================================================================


class TestFetchYfinanceKlines:
    def test_returns_ohlcv_dicts(self):
        """Verify output shape matches Binance kline format."""
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = _make_mock_df(SAMPLE_ROWS)
        mock_ticker_cls = MagicMock(return_value=mock_ticker_instance)
        yf_mod = _mock_yf_module(mock_ticker_cls)

        with patch.dict("sys.modules", {"yfinance": yf_mod}):
            klines = fetch_yfinance_klines("SPY", period_days=30)

        assert len(klines) == 2
        for k in klines:
            assert set(k.keys()) == {"timestamp", "open", "high", "low", "close", "volume"}

    def test_values_are_floats(self):
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = _make_mock_df(SAMPLE_ROWS)
        mock_ticker_cls = MagicMock(return_value=mock_ticker_instance)
        yf_mod = _mock_yf_module(mock_ticker_cls)

        with patch.dict("sys.modules", {"yfinance": yf_mod}):
            klines = fetch_yfinance_klines("GLD", period_days=10)

        assert isinstance(klines[0]["open"], float)
        assert isinstance(klines[0]["volume"], float)

    def test_timestamps_are_strings(self):
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = _make_mock_df(SAMPLE_ROWS)
        mock_ticker_cls = MagicMock(return_value=mock_ticker_instance)
        yf_mod = _mock_yf_module(mock_ticker_cls)

        with patch.dict("sys.modules", {"yfinance": yf_mod}):
            klines = fetch_yfinance_klines("SPY", period_days=10)

        assert klines[0]["timestamp"] == "2025-01-01"
        assert klines[1]["timestamp"] == "2025-01-02"

    def test_empty_data_raises_error(self):
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = _make_mock_df([])
        mock_ticker_cls = MagicMock(return_value=mock_ticker_instance)
        yf_mod = _mock_yf_module(mock_ticker_cls)

        with patch.dict("sys.modules", {"yfinance": yf_mod}):
            with pytest.raises(YFinanceError, match="No data returned"):
                fetch_yfinance_klines("INVALID")

    def test_download_failure_raises_error(self):
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.side_effect = Exception("Network timeout")
        mock_ticker_cls = MagicMock(return_value=mock_ticker_instance)
        yf_mod = _mock_yf_module(mock_ticker_cls)

        with patch.dict("sys.modules", {"yfinance": yf_mod}):
            with pytest.raises(YFinanceError, match="Failed to download"):
                fetch_yfinance_klines("SPY")


# =============================================================================
# ingest_yfinance_data
# =============================================================================


class TestIngestYfinanceData:
    def test_fetches_multiple_symbols(self):
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = _make_mock_df(SAMPLE_ROWS)
        mock_ticker_cls = MagicMock(return_value=mock_ticker_instance)
        yf_mod = _mock_yf_module(mock_ticker_cls)

        with patch.dict("sys.modules", {"yfinance": yf_mod}):
            result = ingest_yfinance_data(symbols=["SPY", "GLD"], period_days=30)

        assert set(result.keys()) == {"SPY", "GLD"}
        assert len(result["SPY"]) == 2

    def test_failed_symbol_is_skipped(self):
        def ticker_side_effect(symbol):
            t = MagicMock()
            if symbol == "BAD":
                t.history.return_value = _make_mock_df([])
            else:
                t.history.return_value = _make_mock_df(SAMPLE_ROWS)
            return t

        yf_mod = MagicMock()
        yf_mod.Ticker = ticker_side_effect

        with patch.dict("sys.modules", {"yfinance": yf_mod}):
            result = ingest_yfinance_data(symbols=["SPY", "BAD"], period_days=10)

        assert "SPY" in result
        assert "BAD" not in result


# =============================================================================
# ingest_yfinance_incremental
# =============================================================================


class TestIngestYfinanceIncremental:
    def test_merges_and_deduplicates(self):
        existing = [
            {"timestamp": "2025-01-01", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
            {"timestamp": "2025-01-02", "open": 1.5, "high": 2.5, "low": 1, "close": 2, "volume": 200},
        ]
        new_rows = [
            {"timestamp": "2025-01-02", "open": 1.5, "high": 2.5, "low": 1, "close": 2, "volume": 200},
            {"timestamp": "2025-01-03", "open": 2, "high": 3, "low": 1.5, "close": 2.5, "volume": 300},
        ]

        mock_storage = MagicMock()
        mock_storage.load_raw.return_value = {"SPY": existing}

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = _make_mock_df(new_rows)
        yf_mod = MagicMock()
        yf_mod.Ticker.return_value = mock_ticker_instance

        with patch.dict("sys.modules", {"yfinance": yf_mod}):
            with patch("src.storage.get_storage", return_value=mock_storage):
                with patch("src.config.load_config") as mock_cfg:
                    mock_cfg.return_value = MagicMock(storage_backend="parquet")
                    result = ingest_yfinance_incremental(symbols=["SPY"])

        # 3 unique dates, not 4
        assert len(result["SPY"]) == 3
        timestamps = [r["timestamp"] for r in result["SPY"]]
        assert timestamps == ["2025-01-01", "2025-01-02", "2025-01-03"]
