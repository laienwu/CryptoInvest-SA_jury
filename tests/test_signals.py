"""Tests for trading signals module."""

import math
from unittest.mock import MagicMock

import pytest

from src.pipeline.signals import (
    BUY,
    HOLD,
    SELL,
    SignalError,
    _bollinger_bands,
    _ema,
    _rsi,
    _sma,
    bollinger_signal,
    generate_portfolio_signals,
    generate_signals_for_asset,
    macd_signal,
    rsi_signal,
    sma_crossover_signal,
)


# =============================================================================
# Helper: generate synthetic price series
# =============================================================================

def _rising_prices(n: int = 60, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start + i * step for i in range(n)]


def _falling_prices(n: int = 60, start: float = 200.0, step: float = 1.0) -> list[float]:
    return [start - i * step for i in range(n)]


def _flat_prices(n: int = 60, value: float = 100.0) -> list[float]:
    return [value] * n


def _volatile_prices(n: int = 60) -> list[float]:
    """Alternating up/down for volatility."""
    return [100.0 + (5.0 if i % 2 == 0 else -5.0) for i in range(n)]


class TestSMA:
    def test_length_matches_input(self):
        assert len(_sma([1, 2, 3, 4, 5], 3)) == 5

    def test_none_before_window(self):
        result = _sma([1, 2, 3, 4, 5], 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] is not None

    def test_correct_value(self):
        result = _sma([10, 20, 30, 40, 50], 3)
        assert result[2] == pytest.approx(20.0)
        assert result[4] == pytest.approx(40.0)

    def test_window_1(self):
        prices = [5, 10, 15]
        result = _sma(prices, 1)
        assert result == [5, 10, 15]


class TestEMA:
    def test_length_matches_input(self):
        assert len(_ema([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 3)) == 10

    def test_none_before_window(self):
        result = _ema([1, 2, 3, 4, 5], 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] is not None

    def test_empty(self):
        assert _ema([], 3) == []


class TestRSI:
    def test_length_matches_input(self):
        prices = _rising_prices(30)
        assert len(_rsi(prices, 14)) == 30

    def test_rising_market_high_rsi(self):
        prices = _rising_prices(30)
        rsi_vals = _rsi(prices, 14)
        last = next(v for v in reversed(rsi_vals) if v is not None)
        assert last > 70  # Should be overbought

    def test_falling_market_low_rsi(self):
        prices = _falling_prices(30)
        rsi_vals = _rsi(prices, 14)
        last = next(v for v in reversed(rsi_vals) if v is not None)
        assert last < 30  # Should be oversold

    def test_too_short(self):
        result = _rsi([100, 101], 14)
        assert all(v is None for v in result)


class TestBollingerBands:
    def test_length_matches(self):
        prices = _rising_prices(30)
        upper, middle, lower = _bollinger_bands(prices, 20)
        assert len(upper) == len(middle) == len(lower) == 30

    def test_upper_above_lower(self):
        prices = _volatile_prices(40)
        upper, _mid, lower = _bollinger_bands(prices, 20)
        for u, l in zip(upper, lower):
            if u is not None and l is not None:
                assert u > l


class TestSMACrossoverSignal:
    def test_rising_gives_buy(self):
        signals = sma_crossover_signal(_rising_prices(60), 10, 30)
        valid = [s for s in signals if s is not None]
        assert valid[-1] == BUY

    def test_falling_gives_sell(self):
        signals = sma_crossover_signal(_falling_prices(60), 10, 30)
        valid = [s for s in signals if s is not None]
        assert valid[-1] == SELL

    def test_none_early(self):
        signals = sma_crossover_signal(_rising_prices(60), 10, 30)
        assert signals[0] is None


class TestRSISignal:
    def test_rising_gives_sell(self):
        """Strong uptrend → overbought RSI → SELL signal."""
        signals = rsi_signal(_rising_prices(30))
        valid = [s for s in signals if s is not None]
        assert valid[-1] == SELL

    def test_falling_gives_buy(self):
        """Strong downtrend → oversold RSI → BUY signal."""
        signals = rsi_signal(_falling_prices(30))
        valid = [s for s in signals if s is not None]
        assert valid[-1] == BUY


class TestMACDSignal:
    def test_accelerating_gives_buy(self):
        """Accelerating prices → fast EMA pulls ahead → positive histogram."""
        prices = [100 + i ** 1.5 for i in range(60)]  # Accelerating curve
        signals = macd_signal(prices)
        valid = [s for s in signals if s is not None]
        assert len(valid) > 0
        assert valid[-1] == BUY

    def test_length(self):
        assert len(macd_signal(_rising_prices(60))) == 60


class TestBollingerSignal:
    def test_length(self):
        assert len(bollinger_signal(_rising_prices(40))) == 40

    def test_flat_gives_hold(self):
        signals = bollinger_signal(_flat_prices(40))
        valid = [s for s in signals if s is not None]
        # Flat prices stay within bands
        assert all(s == HOLD for s in valid)


class TestGenerateSignalsForAsset:
    def test_output_keys(self):
        result = generate_signals_for_asset(_rising_prices(60))
        assert "sma_crossover" in result
        assert "rsi" in result
        assert "macd" in result
        assert "bollinger" in result
        assert "combined" in result
        assert "rsi_value" in result
        assert "n_periods" in result

    def test_combined_signal_valid(self):
        result = generate_signals_for_asset(_rising_prices(60))
        assert result["combined"] in (BUY, SELL, HOLD, None)

    def test_rsi_value_numeric(self):
        result = generate_signals_for_asset(_rising_prices(60))
        assert isinstance(result["rsi_value"], float)


class TestGeneratePortfolioSignals:
    @pytest.fixture()
    def mock_storage(self):
        storage = MagicMock()
        storage.load_raw.return_value = {
            "BTCUSDT": [{"close": 100 + i} for i in range(60)],
            "ETHUSDT": [{"close": 200 - i} for i in range(60)],
        }
        return storage

    def test_output_keys(self, mock_storage):
        result = generate_portfolio_signals(storage=mock_storage, save=False)
        assert "signals" in result
        assert "summary" in result
        assert "n_assets" in result

    def test_all_assets_included(self, mock_storage):
        result = generate_portfolio_signals(storage=mock_storage, save=False)
        symbols = {s["symbol"] for s in result["signals"]}
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

    def test_summary_counts(self, mock_storage):
        result = generate_portfolio_signals(storage=mock_storage, save=False)
        summary = result["summary"]
        assert summary["total"] == 2
        assert summary["buy_count"] + summary["sell_count"] + summary["hold_count"] == 2

    def test_save_to_storage(self, mock_storage):
        generate_portfolio_signals(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()

    def test_missing_data_raises(self):
        storage = MagicMock()
        storage.load_raw.side_effect = FileNotFoundError("not found")
        with pytest.raises(SignalError, match="not found"):
            generate_portfolio_signals(storage=storage)

    def test_empty_data_raises(self):
        storage = MagicMock()
        storage.load_raw.return_value = {}
        with pytest.raises(SignalError, match="No raw"):
            generate_portfolio_signals(storage=storage)

    def test_skips_short_series(self):
        storage = MagicMock()
        storage.load_raw.return_value = {
            "BTCUSDT": [{"close": 100 + i} for i in range(10)],  # Too short
            "ETHUSDT": [{"close": 200 + i} for i in range(60)],  # OK
        }
        result = generate_portfolio_signals(storage=storage, save=False)
        assert result["n_assets"] == 1
