"""Tests for the alpha/beta analysis module."""

import math

import pytest

from src.pipeline.alpha_beta import (
    AlphaBetaError,
    _covariance,
    _mean,
    _portfolio_return_series,
    _variance,
    analyze_alpha_beta,
    compute_alpha_beta,
)


# ---------------------------------------------------------------------------
# Helper math functions
# ---------------------------------------------------------------------------

class TestMean:
    def test_basic(self):
        assert _mean([1, 2, 3]) == pytest.approx(2.0)

    def test_empty(self):
        assert _mean([]) == 0.0

    def test_single(self):
        assert _mean([5.0]) == 5.0


class TestVariance:
    def test_basic(self):
        # [1, 2, 3] → var = 1.0
        assert _variance([1, 2, 3]) == pytest.approx(1.0)

    def test_constant(self):
        assert _variance([5, 5, 5]) == pytest.approx(0.0)

    def test_too_few(self):
        assert _variance([1]) == 0.0
        assert _variance([]) == 0.0


class TestCovariance:
    def test_perfect_positive(self):
        xs = [1.0, 2.0, 3.0]
        ys = [2.0, 4.0, 6.0]
        assert _covariance(xs, ys) == pytest.approx(2.0)

    def test_perfect_negative(self):
        xs = [1.0, 2.0, 3.0]
        ys = [6.0, 4.0, 2.0]
        assert _covariance(xs, ys) == pytest.approx(-2.0)

    def test_too_few(self):
        assert _covariance([1], [2]) == 0.0


# ---------------------------------------------------------------------------
# compute_alpha_beta
# ---------------------------------------------------------------------------

class TestComputeAlphaBeta:
    def test_perfect_correlation_beta_one(self):
        # portfolio = benchmark → beta=1, alpha=0
        returns = [0.01, -0.02, 0.03, 0.01, -0.01]
        result = compute_alpha_beta(returns, returns)
        assert result["beta"] == pytest.approx(1.0, abs=0.01)
        assert result["alpha_annual"] == pytest.approx(0.0, abs=0.01)
        assert result["r_squared"] == pytest.approx(1.0, abs=0.01)

    def test_double_beta(self):
        # portfolio = 2x benchmark → beta=2
        bench = [0.01, -0.02, 0.03, 0.01, -0.01, 0.02]
        port = [r * 2 for r in bench]
        result = compute_alpha_beta(port, bench)
        assert result["beta"] == pytest.approx(2.0, abs=0.01)
        assert result["r_squared"] == pytest.approx(1.0, abs=0.01)

    def test_positive_alpha(self):
        # portfolio consistently beats benchmark
        bench = [0.01, -0.02, 0.03, 0.01, -0.01]
        port = [r + 0.001 for r in bench]  # +10bps per period
        result = compute_alpha_beta(port, bench)
        assert result["alpha_annual"] > 0
        assert result["beta"] == pytest.approx(1.0, abs=0.01)

    def test_negative_alpha(self):
        bench = [0.01, -0.02, 0.03, 0.01, -0.01]
        port = [r - 0.001 for r in bench]
        result = compute_alpha_beta(port, bench)
        assert result["alpha_annual"] < 0

    def test_unequal_length_raises(self):
        with pytest.raises(AlphaBetaError, match="equal length"):
            compute_alpha_beta([0.01, 0.02], [0.01])

    def test_too_few_observations_raises(self):
        with pytest.raises(AlphaBetaError, match="at least 2"):
            compute_alpha_beta([0.01], [0.01])

    def test_zero_variance_benchmark(self):
        # Flat benchmark → beta=0
        result = compute_alpha_beta([0.01, 0.02, 0.03], [0.0, 0.0, 0.0])
        assert result["beta"] == 0.0

    def test_tracking_error_positive(self):
        bench = [0.01, -0.02, 0.03]
        port = [0.02, -0.01, 0.01]  # different from benchmark
        result = compute_alpha_beta(port, bench)
        assert result["tracking_error"] > 0

    def test_tracking_error_zero_when_identical(self):
        returns = [0.01, -0.02, 0.03, 0.01]
        result = compute_alpha_beta(returns, returns)
        assert result["tracking_error"] == pytest.approx(0.0, abs=1e-6)

    def test_information_ratio(self):
        bench = [0.01, -0.02, 0.03, 0.01, -0.01]
        port = [r + 0.001 for r in bench]
        result = compute_alpha_beta(port, bench)
        # IR = alpha / TE; alpha > 0, TE > 0 → IR > 0
        assert result["information_ratio"] > 0

    def test_return_keys(self):
        returns = [0.01, -0.02, 0.03]
        result = compute_alpha_beta(returns, returns)
        expected = {
            "beta", "alpha_annual", "r_squared", "tracking_error",
            "information_ratio", "n_periods", "periods_per_year",
            "risk_free_rate",
        }
        assert set(result.keys()) == expected

    def test_risk_free_rate(self):
        bench = [0.01, -0.02, 0.03, 0.01, -0.01]
        result_no_rf = compute_alpha_beta(bench, bench, risk_free_rate=0.0)
        result_rf = compute_alpha_beta(bench, bench, risk_free_rate=0.05)
        # Both should have beta≈1 regardless of rf
        assert result_no_rf["beta"] == pytest.approx(1.0, abs=0.01)
        assert result_rf["beta"] == pytest.approx(1.0, abs=0.01)

    def test_custom_periods_per_year(self):
        bench = [0.01, -0.02, 0.03, 0.01, -0.01]
        port = [r + 0.001 for r in bench]
        result_365 = compute_alpha_beta(port, bench, periods_per_year=365)
        result_252 = compute_alpha_beta(port, bench, periods_per_year=252)
        # alpha_annual should scale with periods_per_year
        ratio = result_365["alpha_annual"] / result_252["alpha_annual"]
        assert ratio == pytest.approx(365 / 252, abs=0.01)


# ---------------------------------------------------------------------------
# _portfolio_return_series
# ---------------------------------------------------------------------------

class TestPortfolioReturnSeries:
    def test_basic(self):
        weights = {"A": 0.6, "B": 0.4}
        returns = {
            "A": [0.01, 0.02, -0.01],
            "B": [0.02, -0.01, 0.03],
        }
        series = _portfolio_return_series(weights, returns)
        assert len(series) == 3
        assert series[0] == pytest.approx(0.6 * 0.01 + 0.4 * 0.02)

    def test_empty_weights(self):
        assert _portfolio_return_series({}, {"A": [0.01]}) == []

    def test_missing_symbol_in_returns(self):
        weights = {"A": 0.5, "B": 0.5}
        returns = {"A": [0.01, 0.02]}
        # B missing → treated as 0
        series = _portfolio_return_series(weights, returns)
        assert len(series) == 2
        assert series[0] == pytest.approx(0.5 * 0.01)


# ---------------------------------------------------------------------------
# analyze_alpha_beta (integration with storage)
# ---------------------------------------------------------------------------

class TestAnalyzeAlphaBeta:
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

            def save_output(self, data, key):
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
        result = analyze_alpha_beta(storage=storage, save=False)
        assert "beta" in result
        assert "alpha_annual" in result
        assert result["benchmark"] == "BTCUSDT"
        assert result["portfolio_key"] == "weights"

    def test_custom_benchmark(self):
        returns = {
            "BTCUSDT": [0.01, -0.02, 0.03],
            "ETHUSDT": [0.015, -0.025, 0.035],
            "BNBUSDT": [0.02, -0.01, 0.02],
        }
        storage = self._make_storage(returns=returns)
        result = analyze_alpha_beta(
            benchmark_symbol="ETHUSDT", storage=storage, save=False
        )
        assert result["benchmark"] == "ETHUSDT"

    def test_missing_portfolio_raises(self):
        storage = self._make_storage()
        with pytest.raises(AlphaBetaError, match="Portfolio not found"):
            analyze_alpha_beta(portfolio_key="nonexistent", storage=storage)

    def test_missing_returns_raises(self):
        class NoReturnsStorage:
            def load_output(self, key):
                return {"weights": {"A": 1.0}}

            def load_processed(self, key):
                raise FileNotFoundError("no returns")

        with pytest.raises(AlphaBetaError, match="Returns data not found"):
            analyze_alpha_beta(storage=NoReturnsStorage())

    def test_missing_benchmark_raises(self):
        portfolio = {"weights": {"ETHUSDT": 1.0}}
        returns = {"ETHUSDT": [0.01, 0.02, 0.03]}
        storage = self._make_storage(portfolio=portfolio, returns=returns)
        with pytest.raises(AlphaBetaError, match="Benchmark BTCUSDT not found"):
            analyze_alpha_beta(storage=storage, save=False)

    def test_saves_when_requested(self):
        storage = self._make_storage()
        analyze_alpha_beta(storage=storage, save=True)
        assert "alpha_beta" in storage._saved

    def test_no_save_when_disabled(self):
        storage = self._make_storage()
        analyze_alpha_beta(storage=storage, save=False)
        assert "alpha_beta" not in storage._saved

    def test_empty_weights_raises(self):
        storage = self._make_storage(
            portfolio={"weights": {}, "expected_return": 0.1, "volatility": 0.2}
        )
        with pytest.raises(AlphaBetaError, match="no weights"):
            analyze_alpha_beta(storage=storage)


class TestAlphaBetaError:
    def test_message(self):
        err = AlphaBetaError("test error")
        assert str(err) == "test error"
        assert err.operation == "alpha_beta"

    def test_custom_operation(self):
        err = AlphaBetaError("fail", operation="load")
        assert err.operation == "load"
