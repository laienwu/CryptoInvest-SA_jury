"""Tests for live price fetcher."""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.live_prices import (
    LivePriceError,
    fetch_binance_ticker,
    fetch_live_prices,
)


@pytest.fixture()
def mock_binance_response():
    """Mock Binance 24hr ticker response."""
    return [
        {
            "symbol": "BTCUSDT",
            "lastPrice": "65432.10",
            "priceChangePercent": "2.35",
            "quoteVolume": "1234567890.50",
            "highPrice": "66000.00",
            "lowPrice": "64000.00",
        },
        {
            "symbol": "ETHUSDT",
            "lastPrice": "3456.78",
            "priceChangePercent": "-1.20",
            "quoteVolume": "567890123.40",
            "highPrice": "3500.00",
            "lowPrice": "3400.00",
        },
        {
            "symbol": "BNBUSDT",
            "lastPrice": "580.50",
            "priceChangePercent": "0.85",
            "quoteVolume": "123456789.10",
            "highPrice": "590.00",
            "lowPrice": "575.00",
        },
    ]


class TestFetchBinanceTicker:
    """Tests for fetch_binance_ticker."""

    def test_returns_matching_symbols(self, mock_binance_response):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_binance_response, status_code=200
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = fetch_binance_ticker(["BTCUSDT", "ETHUSDT"])
            assert len(result) == 2
            symbols = {t["symbol"] for t in result}
            assert symbols == {"BTCUSDT", "ETHUSDT"}

    def test_price_is_float(self, mock_binance_response):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_binance_response, status_code=200
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = fetch_binance_ticker(["BTCUSDT"])
            assert isinstance(result[0]["price"], float)
            assert result[0]["price"] == pytest.approx(65432.10)

    def test_change_24h_parsed(self, mock_binance_response):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_binance_response, status_code=200
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = fetch_binance_ticker(["ETHUSDT"])
            assert result[0]["change_24h"] == pytest.approx(-1.20)

    def test_empty_symbols_returns_empty(self):
        result = fetch_binance_ticker([])
        assert result == []

    def test_unknown_symbol_filtered_out(self, mock_binance_response):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_binance_response, status_code=200
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = fetch_binance_ticker(["UNKNOWNUSDT"])
            assert len(result) == 0

    def test_api_failure_raises_error(self):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            import requests
            mock_get.side_effect = requests.ConnectionError("timeout")

            with pytest.raises(LivePriceError, match="Binance API request failed"):
                fetch_binance_ticker(["BTCUSDT"])

    def test_ticker_fields_present(self, mock_binance_response):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_binance_response, status_code=200
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = fetch_binance_ticker(["BTCUSDT"])
            expected_keys = {"symbol", "price", "change_24h", "volume_24h", "high_24h", "low_24h"}
            assert set(result[0].keys()) == expected_keys


class TestFetchLivePrices:
    """Tests for fetch_live_prices."""

    def test_returns_timestamp(self, mock_binance_response):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_binance_response, status_code=200
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = fetch_live_prices(crypto_symbols=["BTCUSDT"])
            assert "timestamp" in result

    def test_crypto_count(self, mock_binance_response):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_binance_response, status_code=200
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = fetch_live_prices(crypto_symbols=["BTCUSDT", "ETHUSDT"])
            assert result["n_crypto"] == 2

    def test_no_trad_symbols(self, mock_binance_response):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: mock_binance_response, status_code=200
            )
            mock_get.return_value.raise_for_status = MagicMock()

            result = fetch_live_prices(crypto_symbols=["BTCUSDT"])
            assert result["n_trad"] == 0
            assert result["trad"] == []

    def test_graceful_binance_failure(self):
        with patch("src.pipeline.live_prices.requests.get") as mock_get:
            import requests
            mock_get.side_effect = requests.ConnectionError("fail")

            result = fetch_live_prices(crypto_symbols=["BTCUSDT"])
            assert result["n_crypto"] == 0
            assert result["crypto"] == []
