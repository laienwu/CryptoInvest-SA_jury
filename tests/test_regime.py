"""Tests for the market regime detection module."""

import math

import pytest

from src.pipeline.regime import (
    REGIME_BEAR,
    REGIME_BULL,
    REGIME_SIDEWAYS,
    RegimeError,
    _median,
    _realized_volatility,
    _sma,
    analyze_regimes,
    detect_regime_for_symbol,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestSma:
    def test_basic(self):
        assert _sma([1, 2, 3, 4, 5], 3) == pytest.approx(4.0)

    def test_full_window(self):
        assert _sma([2, 4, 6], 3) == pytest.approx(4.0)

    def test_insufficient_data(self):
        assert _sma([1, 2], 5) is None


class TestRealizedVolatility:
    def test_constant_returns(self):
        # Constant returns → near-zero vol
        returns = [0.01] * 30
        assert _realized_volatility(returns) == pytest.approx(0.0, abs=1e-10)

    def test_positive_vol(self):
        returns = [0.01, -0.02, 0.03, -0.01, 0.02] * 6
        vol = _realized_volatility(returns)
        assert vol > 0

    def test_too_few_returns(self):
        assert _realized_volatility([0.01]) == 0.0
        assert _realized_volatility([]) == 0.0


class TestMedian:
    def test_odd(self):
        assert _median([3, 1, 2]) == 2

    def test_even(self):
        assert _median([1, 2, 3, 4]) == pytest.approx(2.5)

    def test_empty(self):
        assert _median([]) == 0.0

    def test_single(self):
        assert _median([5]) == 5


# ---------------------------------------------------------------------------
# detect_regime_for_symbol
# ---------------------------------------------------------------------------

class TestDetectRegime:
    def _trending_up_prices(self, n=60):
        """Generate uptrending prices."""
        return [100 + i * 0.5 for i in range(n)]

    def _trending_down_prices(self, n=60):
        """Generate downtrending prices."""
        return [100 - i * 0.5 for i in range(n)]

    def _flat_prices(self, n=60):
        """Generate sideways prices."""
        return [100 + (i % 2) * 0.1 for i in range(n)]

    def _returns_from_prices(self, prices):
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0 and prices[i] > 0:
                returns.append(math.log(prices[i] / prices[i - 1]))
        return returns

    def test_bull_market(self):
        prices = self._trending_up_prices()
        returns = self._returns_from_prices(prices)
        result = detect_regime_for_symbol(prices, returns)
        assert result["regime"] == REGIME_BULL
        assert result["trend_signal"] == "BULLISH"
        assert result["confidence"] > 0

    def test_bear_market(self):
        prices = self._trending_down_prices()
        returns = self._returns_from_prices(prices)
        result = detect_regime_for_symbol(prices, returns)
        assert result["regime"] == REGIME_BEAR
        assert result["trend_signal"] == "BEARISH"

    def test_insufficient_data(self):
        prices = [100, 101, 102]
        returns = self._returns_from_prices(prices)
        result = detect_regime_for_symbol(prices, returns)
        assert result["regime"] == REGIME_SIDEWAYS
        assert result["confidence"] == 0.0

    def test_return_keys(self):
        prices = self._trending_up_prices()
        returns = self._returns_from_prices(prices)
        result = detect_regime_for_symbol(prices, returns)
        expected = {
            "regime", "confidence", "trend_signal", "vol_regime",
            "short_sma", "long_sma", "current_vol", "median_vol", "n_periods",
        }
        assert set(result.keys()) == expected

    def test_n_periods(self):
        prices = self._trending_up_prices(80)
        returns = self._returns_from_prices(prices)
        result = detect_regime_for_symbol(prices, returns)
        assert result["n_periods"] == 80

    def test_confidence_range(self):
        for gen in [self._trending_up_prices, self._trending_down_prices, self._flat_prices]:
            prices = gen()
            returns = self._returns_from_prices(prices)
            result = detect_regime_for_symbol(prices, returns)
            assert 0.0 <= result["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# analyze_regimes (integration)
# ---------------------------------------------------------------------------

class TestAnalyzeRegimes:
    def _make_storage(self, raw_data=None):
        class MockStorage:
            def __init__(self, raw):
                self._raw = raw
                self._saved = {}

            def load_raw(self):
                if self._raw is None:
                    raise FileNotFoundError("no data")
                return self._raw

            def save_output(self, key, data):
                self._saved[key] = data

        if raw_data is None:
            # Generate uptrending klines for two symbols
            raw_data = {}
            for symbol in ["BTCUSDT", "ETHUSDT"]:
                klines = []
                for i in range(60):
                    price = 100 + i * 0.5
                    klines.append({
                        "timestamp": f"2025-01-{i+1:02d}",
                        "open": price,
                        "high": price + 1,
                        "low": price - 1,
                        "close": price,
                        "volume": 1000,
                    })
                raw_data[symbol] = klines

        return MockStorage(raw_data)

    def test_basic_analysis(self):
        storage = self._make_storage()
        result = analyze_regimes(storage=storage, save=False)
        assert "regimes" in result
        assert "summary" in result
        assert result["summary"]["n_assets"] == 2

    def test_summary_counts(self):
        storage = self._make_storage()
        result = analyze_regimes(storage=storage, save=False)
        s = result["summary"]
        assert s["bull_count"] + s["bear_count"] + s["sideways_count"] == s["n_assets"]

    def test_missing_data_raises(self):
        storage = self._make_storage()
        storage._raw = None
        with pytest.raises(RegimeError, match="Raw price data not found"):
            analyze_regimes(storage=storage)

    def test_empty_data_raises(self):
        storage = self._make_storage(raw_data={})
        with pytest.raises(RegimeError, match="No price data"):
            analyze_regimes(storage=storage)

    def test_saves_when_requested(self):
        storage = self._make_storage()
        analyze_regimes(storage=storage, save=True)
        assert "regime" in storage._saved

    def test_no_save_when_disabled(self):
        storage = self._make_storage()
        analyze_regimes(storage=storage, save=False)
        assert "regime" not in storage._saved

    def test_symbol_in_regime_output(self):
        storage = self._make_storage()
        result = analyze_regimes(storage=storage, save=False)
        symbols = [r["symbol"] for r in result["regimes"]]
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

    def test_skips_insufficient_klines(self):
        raw = {"BTCUSDT": [{"close": 100}]}  # Only 1 kline
        storage = self._make_storage(raw_data=raw)
        result = analyze_regimes(storage=storage, save=False)
        # Symbol with only 1 kline is skipped
        assert result["summary"]["n_assets"] == 0
        assert result["regimes"] == []


class TestRegimeError:
    def test_message(self):
        err = RegimeError("test")
        assert str(err) == "test"
        assert err.operation == "regime"

    def test_custom_operation(self):
        err = RegimeError("fail", operation="load")
        assert err.operation == "load"
