"""Tests for the Sortino ratio and downside risk module."""

import pytest

from src.pipeline.sortino import (
    SortinoError,
    analyze_sortino,
    compute_sortino_metrics,
    downside_capture,
    downside_deviation,
    gain_to_pain_ratio,
    sortino_ratio,
    upside_capture,
)


# ---------------------------------------------------------------------------
# downside_deviation
# ---------------------------------------------------------------------------

class TestDownsideDeviation:
    def test_no_negative_returns(self):
        returns = [0.01, 0.02, 0.03, 0.01]
        dd = downside_deviation(returns)
        assert dd == 0.0  # No returns below MAR=0

    def test_all_negative(self):
        returns = [-0.01, -0.02, -0.03]
        dd = downside_deviation(returns)
        assert dd > 0

    def test_mixed_returns(self):
        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        dd = downside_deviation(returns)
        assert dd > 0

    def test_too_few_returns(self):
        assert downside_deviation([0.01]) == 0.0
        assert downside_deviation([]) == 0.0

    def test_custom_mar(self):
        returns = [0.01, 0.02, 0.03]
        # MAR = 0.02, so 0.01 is below → positive dd
        dd = downside_deviation(returns, mar=0.02)
        assert dd > 0


# ---------------------------------------------------------------------------
# sortino_ratio
# ---------------------------------------------------------------------------

class TestSortinoRatio:
    def test_positive_returns(self):
        returns = [0.01, 0.02, -0.005, 0.015, -0.002] * 10
        sr = sortino_ratio(returns)
        assert sr > 0

    def test_all_positive_returns_zero_dd(self):
        returns = [0.01, 0.02, 0.03]
        sr = sortino_ratio(returns)
        assert sr == 0.0  # dd=0 → ratio=0

    def test_too_few(self):
        assert sortino_ratio([0.01]) == 0.0

    def test_higher_return_higher_sortino(self):
        low = [0.005, -0.01, 0.003, -0.005, 0.002] * 5
        high = [0.02, -0.01, 0.015, -0.005, 0.01] * 5
        assert sortino_ratio(high) > sortino_ratio(low)


# ---------------------------------------------------------------------------
# Capture ratios
# ---------------------------------------------------------------------------

class TestUpsideCapture:
    def test_perfect_capture(self):
        bench = [0.01, -0.02, 0.03]
        assert upside_capture(bench, bench) == pytest.approx(1.0)

    def test_double_capture(self):
        bench = [0.01, -0.02, 0.03]
        port = [0.02, -0.04, 0.06]
        assert upside_capture(port, bench) == pytest.approx(2.0)

    def test_no_up_periods(self):
        bench = [-0.01, -0.02, -0.03]
        port = [-0.005, -0.01, -0.015]
        assert upside_capture(port, bench) == 0.0

    def test_unequal_length(self):
        assert upside_capture([0.01], [0.01, 0.02]) == 0.0


class TestDownsideCapture:
    def test_perfect_capture(self):
        bench = [0.01, -0.02, 0.03]
        assert downside_capture(bench, bench) == pytest.approx(1.0)

    def test_half_capture(self):
        bench = [0.01, -0.02, 0.03]
        port = [0.005, -0.01, 0.015]
        assert downside_capture(port, bench) == pytest.approx(0.5)

    def test_no_down_periods(self):
        bench = [0.01, 0.02, 0.03]
        assert downside_capture([0.01, 0.02, 0.03], bench) == 0.0


# ---------------------------------------------------------------------------
# gain_to_pain_ratio
# ---------------------------------------------------------------------------

class TestGainToPain:
    def test_all_gains(self):
        result = gain_to_pain_ratio([0.01, 0.02, 0.03])
        assert result == float("inf")

    def test_all_losses(self):
        result = gain_to_pain_ratio([-0.01, -0.02, -0.03])
        assert result < 0

    def test_mixed(self):
        result = gain_to_pain_ratio([0.05, -0.01, 0.03, -0.02])
        # total = 0.05, pain = 0.03
        assert result == pytest.approx(0.05 / 0.03, abs=0.01)

    def test_empty(self):
        assert gain_to_pain_ratio([]) == 0.0

    def test_zero_sum(self):
        assert gain_to_pain_ratio([0.01, -0.01]) == 0.0


# ---------------------------------------------------------------------------
# compute_sortino_metrics
# ---------------------------------------------------------------------------

class TestComputeSortinoMetrics:
    def test_return_keys(self):
        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        result = compute_sortino_metrics(returns)
        expected = {
            "sortino_ratio", "downside_deviation", "upside_deviation",
            "gain_to_pain", "upside_capture", "downside_capture",
            "n_periods", "n_negative", "n_positive",
            "worst_return", "best_return",
            "periods_per_year", "risk_free_rate",
        }
        assert set(result.keys()) == expected

    def test_counts(self):
        returns = [0.01, -0.02, 0.03, -0.01, 0.0]
        result = compute_sortino_metrics(returns)
        assert result["n_negative"] == 2
        assert result["n_positive"] == 2
        assert result["n_periods"] == 5

    def test_with_benchmark(self):
        returns = [0.01, -0.02, 0.03]
        bench = [0.005, -0.01, 0.015]
        result = compute_sortino_metrics(returns, benchmark_returns=bench)
        assert result["upside_capture"] is not None
        assert result["downside_capture"] is not None

    def test_without_benchmark(self):
        returns = [0.01, -0.02, 0.03]
        result = compute_sortino_metrics(returns)
        assert result["upside_capture"] is None
        assert result["downside_capture"] is None

    def test_too_few(self):
        result = compute_sortino_metrics([0.01])
        assert result["sortino_ratio"] == 0.0
        assert result["downside_deviation"] == 0.0


# ---------------------------------------------------------------------------
# analyze_sortino (integration)
# ---------------------------------------------------------------------------

class TestAnalyzeSortino:
    def _make_storage(self, portfolio=None, returns=None):
        class MockStorage:
            def __init__(self, outputs, processed):
                self._outputs = outputs
                self._processed = processed
                self._saved = {}

            def load_output(self, key):
                if key not in self._outputs:
                    raise FileNotFoundError(f"Key {key} not found")
                return self._outputs[key]

            def load_processed(self, key):
                if key not in self._processed:
                    raise FileNotFoundError(f"Key {key} not found")
                return self._processed[key]

            def save_output(self, key, data):
                self._saved[key] = data

        if portfolio is None:
            portfolio = {
                "weights": {"ETHUSDT": 0.6, "BNBUSDT": 0.4},
                "expected_return": 0.15,
                "volatility": 0.25,
            }
        if returns is None:
            returns = {
                "BTCUSDT": [0.01, -0.02, 0.03, 0.01, -0.01],
                "ETHUSDT": [0.015, -0.025, 0.035, 0.012, -0.008],
                "BNBUSDT": [0.02, -0.01, 0.02, 0.005, -0.015],
            }
        return MockStorage({"weights": portfolio}, {"returns": returns})

    def test_basic_analysis(self):
        storage = self._make_storage()
        result = analyze_sortino(storage=storage, save=False)
        assert "sortino_ratio" in result
        assert "downside_deviation" in result
        assert result["portfolio_key"] == "weights"
        assert result["benchmark"] == "BTCUSDT"

    def test_missing_portfolio_raises(self):
        storage = self._make_storage()
        with pytest.raises(SortinoError, match="Portfolio not found"):
            analyze_sortino(portfolio_key="nonexistent", storage=storage)

    def test_empty_weights_raises(self):
        storage = self._make_storage(
            portfolio={"weights": {}}
        )
        with pytest.raises(SortinoError, match="no weights"):
            analyze_sortino(storage=storage)

    def test_saves_when_requested(self):
        storage = self._make_storage()
        analyze_sortino(storage=storage, save=True)
        assert "sortino" in storage._saved

    def test_no_save_when_disabled(self):
        storage = self._make_storage()
        analyze_sortino(storage=storage, save=False)
        assert "sortino" not in storage._saved

    def test_capture_ratios_present(self):
        storage = self._make_storage()
        result = analyze_sortino(storage=storage, save=False)
        assert result["upside_capture"] is not None
        assert result["downside_capture"] is not None


class TestSortinoError:
    def test_message(self):
        err = SortinoError("test")
        assert str(err) == "test"
        assert err.operation == "sortino"

    def test_custom_operation(self):
        err = SortinoError("fail", operation="load")
        assert err.operation == "load"
