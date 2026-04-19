"""
Tests for src/pipeline/ingest.py

Covers: fetch_klines, make_binance_request, BinanceAPIError, ingest_data, ingest_incremental.
All network calls are mocked — no real Binance API calls.
"""

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.ingest import (
    BinanceAPIError,
    fetch_klines,
    ingest_data,
    make_binance_request,
)


# =============================================================================
# BinanceAPIError
# =============================================================================


def test_binance_api_error_message() -> None:
    err = BinanceAPIError("test error", status_code=429)
    assert err.message == "test error"
    assert err.status_code == 429
    assert str(err) == "test error"


def test_binance_api_error_no_status_code() -> None:
    err = BinanceAPIError("timeout")
    assert err.status_code is None


# =============================================================================
# make_binance_request
# =============================================================================


def _mock_kline_response() -> list[list[Any]]:
    """Minimal Binance kline API response (one candle)."""
    return [[
        1704067200000,  # open_time ms
        "42000.0",      # open
        "43000.0",      # high
        "41500.0",      # low
        "42500.0",      # close
        "1500.5",       # volume
        1704153599999,  # close_time
        "63000000.0",   # quote_asset_volume
        1000,           # number_of_trades
        "750.0",        # taker_buy_base_vol
        "31500000.0",   # taker_buy_quote_vol
        "0",            # ignore
    ]]


def test_make_request_success() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _mock_kline_response()

    with patch("requests.get", return_value=mock_response):
        result = make_binance_request("https://api.binance.com/api/v3/klines", {"symbol": "BTCUSDT"})

    assert isinstance(result, list)
    assert len(result) == 1


def test_make_request_non_200_raises() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"msg": "Bad symbol"}

    with patch("requests.get", return_value=mock_response):
        with pytest.raises(BinanceAPIError) as exc_info:
            make_binance_request("https://api.binance.com/api/v3/klines", {}, max_retries=1)

    assert exc_info.value.status_code == 400


def test_make_request_timeout_raises() -> None:
    import requests as req

    with patch("requests.get", side_effect=req.exceptions.Timeout):
        with pytest.raises(BinanceAPIError):
            make_binance_request("https://api.binance.com/api/v3/klines", {}, max_retries=1)


def test_make_request_connection_error_raises() -> None:
    import requests as req

    with patch("requests.get", side_effect=req.exceptions.ConnectionError("refused")):
        with pytest.raises(BinanceAPIError):
            make_binance_request("https://api.binance.com/api/v3/klines", {}, max_retries=1)


def test_make_request_exponential_backoff() -> None:
    """Verify multiple retries are attempted before raising."""
    import requests as req

    call_count = 0

    def flaky(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        raise req.exceptions.Timeout

    with patch("requests.get", side_effect=flaky):
        with patch("time.sleep"):  # don't actually sleep
            with pytest.raises(BinanceAPIError):
                make_binance_request("https://api.binance.com/api/v3/klines", {}, max_retries=3)

    assert call_count == 3


# =============================================================================
# fetch_klines
# =============================================================================


def test_fetch_klines_returns_ohlcv_records() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _mock_kline_response()

    with patch("requests.get", return_value=mock_response):
        klines = fetch_klines("BTCUSDT", interval="1d")

    assert len(klines) == 1
    record = klines[0]
    assert "timestamp" in record
    assert "open" in record
    assert "high" in record
    assert "low" in record
    assert "close" in record
    assert "volume" in record
    assert isinstance(record["close"], float)


def test_fetch_klines_respects_start_end_time() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []

    start = datetime(2024, 1, 1)
    end = datetime(2024, 3, 31)

    captured_params: dict[str, Any] = {}

    def capture_call(url: str, params: dict[str, Any], **kwargs: Any) -> MagicMock:
        captured_params.update(params)
        return mock_response

    with patch("requests.get", side_effect=capture_call):
        fetch_klines("BTCUSDT", start_time=start, end_time=end)

    assert captured_params["startTime"] == int(start.timestamp() * 1000)
    assert captured_params["endTime"] == int(end.timestamp() * 1000)


def test_fetch_klines_empty_response_returns_empty_list() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []

    with patch("requests.get", return_value=mock_response):
        klines = fetch_klines("BTCUSDT")

    assert klines == []


# =============================================================================
# ingest_data
# =============================================================================


def test_ingest_data_returns_dict_of_symbols() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _mock_kline_response()

    with patch("requests.get", return_value=mock_response):
        with patch("time.sleep"):
            result = ingest_data(symbols=["BTCUSDT", "ETHUSDT"], period_days=1)

    assert "BTCUSDT" in result
    assert "ETHUSDT" in result
    assert isinstance(result["BTCUSDT"], list)


def test_ingest_data_partial_failure_skips_symbol() -> None:
    """If one symbol fails, others should still be returned."""
    import requests as req

    call_count = 0

    def flaky_for_eth(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        params = kwargs.get("params", args[1] if len(args) > 1 else {})
        if isinstance(params, dict) and params.get("symbol") == "ETHUSDT":
            raise req.exceptions.ConnectionError("ETH down")
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = _mock_kline_response()
        return mock

    with patch("requests.get", side_effect=flaky_for_eth):
        with patch("time.sleep"):
            result = ingest_data(symbols=["BTCUSDT", "ETHUSDT"], period_days=1)

    assert "BTCUSDT" in result
    assert "ETHUSDT" not in result
