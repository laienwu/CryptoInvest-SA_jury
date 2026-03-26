"""Tests for the factor exposure analysis module."""

import math

import pytest

from src.pipeline.factor_analysis import (
    FactorAnalysisError,
    _align_returns,
    _extract_returns,
    _gauss_jordan_inverse,
    _mean,
    _ols_regression,
    _std,
    analyze_factors,
    compute_market_factor,
    compute_momentum_factor,
    compute_volatility_factor,
    factor_regression,
)


# ---------------------------------------------------------------------------
# TestOlsRegression
# ---------------------------------------------------------------------------


class TestOlsRegression:
    """Tests for _ols_regression."""

    def test_perfect_fit_single_predictor(self):
        # y = 2x, no intercept col → just slope
        y = [2.0, 4.0, 6.0, 8.0]
        x = [[v] for v in [1.0, 2.0, 3.0, 4.0]]
        result = _ols_regression(y, x)
        assert result["coefficients"][0] == pytest.approx(2.0, abs=1e-6)
        assert result["r_squared"] == pytest.approx(1.0, abs=1e-4)
        assert result["residual_std"] == pytest.approx(0.0, abs=1e-6)

    def test_perfect_fit_with_intercept(self):
        # y = 3 + 2x
        y = [3 + 2 * i for i in range(5)]
        x = [[1.0, float(i)] for i in range(5)]
        result = _ols_regression(y, x)
        assert result["coefficients"][0] == pytest.approx(3.0, abs=1e-4)
        assert result["coefficients"][1] == pytest.approx(2.0, abs=1e-4)
        assert result["r_squared"] == pytest.approx(1.0, abs=1e-4)

    def test_noisy_data_r_squared_below_one(self):
        # y ≈ x + noise
        y = [1.1, 2.3, 2.8, 4.1, 5.2]
        x = [[1.0, float(i)] for i in range(1, 6)]
        result = _ols_regression(y, x)
        assert 0.0 < result["r_squared"] < 1.0
        assert result["residual_std"] > 0

    def test_r_squared_range(self):
        y = [1.0, 2.0, 1.5, 3.0, 2.5]
        x = [[1.0, float(i)] for i in range(5)]
        result = _ols_regression(y, x)
        assert 0.0 <= result["r_squared"] <= 1.0

    def test_empty_data_raises(self):
        with pytest.raises(FactorAnalysisError, match="Empty data"):
            _ols_regression([], [])

    def test_singular_matrix_raises(self):
        # All X identical → singular X'X
        y = [1.0, 2.0, 3.0]
        x = [[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]
        with pytest.raises(FactorAnalysisError, match="Singular"):
            _ols_regression(y, x)

    def test_two_predictors(self):
        # y = 1 + 2*x1 + 3*x2 (x1 and x2 not perfectly collinear)
        x1 = [1, 2, 3, 4, 5]
        x2 = [2, 1, 4, 3, 6]
        y = [1 + 2 * a + 3 * b for a, b in zip(x1, x2)]
        x = [[1.0, float(a), float(b)] for a, b in zip(x1, x2)]
        result = _ols_regression(y, x)
        assert result["coefficients"][0] == pytest.approx(1.0, abs=1e-3)
        assert result["coefficients"][1] == pytest.approx(2.0, abs=1e-3)
        assert result["coefficients"][2] == pytest.approx(3.0, abs=1e-3)


# ---------------------------------------------------------------------------
# TestComputeMarketFactor
# ---------------------------------------------------------------------------


class TestComputeMarketFactor:
    """Tests for compute_market_factor."""

    def test_equal_weight_average(self):
        returns = {
            "A": [0.01, 0.02, -0.01],
            "B": [0.03, -0.02, 0.01],
        }
        market = compute_market_factor(returns)
        assert len(market) == 3
        assert market[0] == pytest.approx((0.01 + 0.03) / 2)
        assert market[1] == pytest.approx((0.02 + (-0.02)) / 2)
        assert market[2] == pytest.approx((-0.01 + 0.01) / 2)

    def test_single_asset(self):
        returns = {"A": [0.05, -0.03]}
        market = compute_market_factor(returns)
        assert market[0] == pytest.approx(0.05)
        assert market[1] == pytest.approx(-0.03)

    def test_empty_returns(self):
        assert compute_market_factor({}) == []

    def test_three_assets(self):
        returns = {
            "A": [0.01],
            "B": [0.02],
            "C": [0.03],
        }
        market = compute_market_factor(returns)
        assert market[0] == pytest.approx(0.02)


# ---------------------------------------------------------------------------
# TestComputeMomentumFactor
# ---------------------------------------------------------------------------


class TestComputeMomentumFactor:
    """Tests for compute_momentum_factor."""

    def test_winners_minus_losers(self):
        # A always goes up, B always goes down → momentum should be positive
        n = 25
        returns = {
            "A": [0.02] * n,
            "B": [-0.01] * n,
        }
        momentum = compute_momentum_factor(returns, window=5)
        assert len(momentum) == n - 5
        # Winners (A) minus losers (B) at each period
        for m in momentum:
            assert m > 0

    def test_short_window(self):
        returns = {
            "A": [0.01, 0.02, 0.03, 0.04, 0.05],
            "B": [0.05, 0.04, 0.03, 0.02, 0.01],
        }
        momentum = compute_momentum_factor(returns, window=2)
        assert len(momentum) == 3  # 5 - 2

    def test_insufficient_data_returns_empty(self):
        returns = {
            "A": [0.01, 0.02],
            "B": [0.01, 0.02],
        }
        momentum = compute_momentum_factor(returns, window=5)
        assert momentum == []

    def test_empty_returns(self):
        assert compute_momentum_factor({}) == []


# ---------------------------------------------------------------------------
# TestComputeVolatilityFactor
# ---------------------------------------------------------------------------


class TestComputeVolatilityFactor:
    """Tests for compute_volatility_factor."""

    def test_low_vol_minus_high_vol(self):
        n = 25
        # A is low vol (constant), B is high vol (alternating)
        returns = {
            "A": [0.01] * n,
            "B": [0.05 if i % 2 == 0 else -0.03 for i in range(n)],
        }
        vol_factor = compute_volatility_factor(returns, window=5)
        assert len(vol_factor) == n - 5
        # Low vol (A) - high vol (B): sign depends on return difference
        # A always 0.01, B alternates, so factor values exist
        assert len(vol_factor) > 0

    def test_short_window(self):
        returns = {
            "A": [0.01] * 10,
            "B": [0.02] * 10,
        }
        vol_factor = compute_volatility_factor(returns, window=3)
        assert len(vol_factor) == 7  # 10 - 3

    def test_empty_returns(self):
        assert compute_volatility_factor({}) == []

    def test_insufficient_data(self):
        returns = {"A": [0.01], "B": [0.02]}
        vol_factor = compute_volatility_factor(returns, window=5)
        assert vol_factor == []


# ---------------------------------------------------------------------------
# TestFactorRegression
# ---------------------------------------------------------------------------


class TestFactorRegression:
    """Tests for factor_regression."""

    def test_basic_regression(self):
        # Asset return = 0.001 + 1.0 * market
        market = [0.01, -0.02, 0.03, 0.01, -0.01, 0.02]
        asset = [0.001 + r for r in market]
        result = factor_regression(asset, {"market": market})
        assert "alpha" in result
        assert "betas" in result
        assert "r_squared" in result
        assert result["betas"]["market"] == pytest.approx(1.0, abs=0.01)
        assert result["r_squared"] == pytest.approx(1.0, abs=0.01)

    def test_alpha_and_betas_present(self):
        market = [0.01, -0.02, 0.03, 0.01, -0.01, 0.02]
        momentum = [0.005, -0.003, 0.002, 0.001, -0.002, 0.004]
        asset = [0.01] * 6
        result = factor_regression(
            asset, {"market": market, "momentum": momentum}
        )
        assert "alpha" in result
        assert "market" in result["betas"]
        assert "momentum" in result["betas"]

    def test_no_factors_raises(self):
        with pytest.raises(FactorAnalysisError, match="No factor"):
            factor_regression([0.01, 0.02], {})

    def test_insufficient_observations_raises(self):
        with pytest.raises(FactorAnalysisError, match="Need at least"):
            factor_regression([0.01], {"market": [0.01]})

    def test_multi_factor(self):
        n = 20
        market = [0.01 * (i % 5 - 2) for i in range(n)]
        momentum = [0.005 * (i % 3 - 1) for i in range(n)]
        volatility = [0.002 * (i % 4 - 1.5) for i in range(n)]
        # Asset = 0.001 + 0.8*mkt + 0.3*mom + 0.1*vol
        asset = [
            0.001 + 0.8 * market[i] + 0.3 * momentum[i] + 0.1 * volatility[i]
            for i in range(n)
        ]
        result = factor_regression(
            asset,
            {"market": market, "momentum": momentum, "volatility": volatility},
        )
        assert result["betas"]["market"] == pytest.approx(0.8, abs=0.05)
        assert result["betas"]["momentum"] == pytest.approx(0.3, abs=0.05)
        assert result["r_squared"] > 0.9


# ---------------------------------------------------------------------------
# TestAnalyzeFactors
# ---------------------------------------------------------------------------


class TestAnalyzeFactors:
    """Tests for analyze_factors (integration with storage)."""

    @staticmethod
    def _make_klines(prices: list[float]) -> list[dict]:
        """Build kline records from a price series."""
        return [
            {
                "timestamp": f"2024-01-{i + 1:02d}",
                "open": p,
                "high": p * 1.01,
                "low": p * 0.99,
                "close": p,
                "volume": 1000,
            }
            for i, p in enumerate(prices)
        ]

    def _make_storage(self, raw_data=None, *, saved=None):
        klines = raw_data
        _saved = saved if saved is not None else {}

        class MockStorage:
            def load_raw(self, symbols=None):
                if klines is None:
                    raise FileNotFoundError("no raw data")
                return klines

            def save_output(self, data, name):
                _saved[name] = data

        storage = MockStorage()
        storage._saved = _saved
        return storage

    def test_basic(self):
        # 4 assets, 30 prices each with varied patterns → 29 returns, window=5
        import math as _math

        raw = {}
        seeds = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0}
        for sym, seed in seeds.items():
            prices = [
                100 + 10 * _math.sin(seed * i * 0.3) + i * 0.2 * seed
                for i in range(30)
            ]
            raw[sym] = self._make_klines(prices)

        storage = self._make_storage(raw)
        result = analyze_factors(window=5, storage=storage, save=False)

        assert result["method"] == "factor_analysis"
        assert result["n_assets"] >= 2
        assert result["n_periods"] > 0
        assert len(result["factors"]) == 3
        assert "market" in result["factors"]
        assert "momentum" in result["factors"]
        assert "volatility" in result["factors"]
        assert len(result["per_asset"]) == result["n_assets"]

    def test_saves_output(self):
        raw = {}
        for sym in ["A", "B", "C", "D"]:
            prices = [100 + i * 0.5 for i in range(30)]
            raw[sym] = self._make_klines(prices)

        saved: dict = {}
        storage = self._make_storage(raw, saved=saved)
        analyze_factors(window=5, storage=storage, save=True)
        assert "factor_analysis" in saved

    def test_no_save(self):
        raw = {}
        for sym in ["A", "B", "C"]:
            prices = [100 + i for i in range(30)]
            raw[sym] = self._make_klines(prices)

        saved: dict = {}
        storage = self._make_storage(raw, saved=saved)
        analyze_factors(window=5, storage=storage, save=False)
        assert "factor_analysis" not in saved

    def test_missing_data_raises(self):
        storage = self._make_storage(None)
        with pytest.raises(FactorAnalysisError, match="Raw price data not found"):
            analyze_factors(storage=storage)

    def test_empty_raw_raises(self):
        storage = self._make_storage({})
        with pytest.raises(FactorAnalysisError, match="No symbols found"):
            analyze_factors(storage=storage)

    def test_single_asset_raises(self):
        raw = {"A": self._make_klines([100 + i for i in range(30)])}
        storage = self._make_storage(raw)
        with pytest.raises(FactorAnalysisError, match="at least 2 assets"):
            analyze_factors(storage=storage)

    def test_per_asset_has_expected_keys(self):
        raw = {}
        for sym in ["A", "B", "C"]:
            prices = [100 + i * (1 if sym == "A" else -0.5) for i in range(30)]
            raw[sym] = self._make_klines(prices)

        storage = self._make_storage(raw)
        result = analyze_factors(window=5, storage=storage, save=False)
        for entry in result["per_asset"]:
            assert "symbol" in entry
            assert "alpha" in entry
            assert "betas" in entry
            assert "r_squared" in entry
            assert 0.0 <= entry["r_squared"] <= 1.0


# ---------------------------------------------------------------------------
# TestFactorAnalysisError
# ---------------------------------------------------------------------------


class TestFactorAnalysisError:
    """Tests for FactorAnalysisError."""

    def test_message(self):
        err = FactorAnalysisError("test error")
        assert str(err) == "test error"
        assert err.message == "test error"
        assert err.operation == "factor_analysis"

    def test_custom_operation(self):
        err = FactorAnalysisError("fail", operation="load")
        assert err.operation == "load"


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    """Tests for internal helper functions."""

    def test_mean_basic(self):
        assert _mean([1, 2, 3]) == pytest.approx(2.0)

    def test_mean_empty(self):
        assert _mean([]) == 0.0

    def test_std_basic(self):
        assert _std([1, 2, 3]) == pytest.approx(1.0)

    def test_std_single(self):
        assert _std([5.0]) == 0.0

    def test_extract_returns(self):
        raw = {
            "A": [
                {"timestamp": "2024-01-01", "close": 100.0},
                {"timestamp": "2024-01-02", "close": 110.0},
                {"timestamp": "2024-01-03", "close": 105.0},
            ]
        }
        result = _extract_returns(raw)
        assert "A" in result
        assert len(result["A"]) == 2
        assert result["A"][0] == pytest.approx(0.1)
        assert result["A"][1] == pytest.approx(-0.04545454, abs=1e-5)

    def test_align_returns(self):
        returns = {"A": [1, 2, 3, 4], "B": [5, 6]}
        aligned = _align_returns(returns)
        assert len(aligned["A"]) == 2
        assert len(aligned["B"]) == 2

    def test_gauss_jordan_identity(self):
        m = [[1.0, 0.0], [0.0, 1.0]]
        inv = _gauss_jordan_inverse(m)
        assert inv[0][0] == pytest.approx(1.0)
        assert inv[1][1] == pytest.approx(1.0)

    def test_gauss_jordan_2x2(self):
        m = [[2.0, 1.0], [1.0, 3.0]]
        inv = _gauss_jordan_inverse(m)
        # Verify M * M^-1 = I
        product = [
            [sum(m[i][k] * inv[k][j] for k in range(2)) for j in range(2)]
            for i in range(2)
        ]
        assert product[0][0] == pytest.approx(1.0, abs=1e-8)
        assert product[0][1] == pytest.approx(0.0, abs=1e-8)
        assert product[1][0] == pytest.approx(0.0, abs=1e-8)
        assert product[1][1] == pytest.approx(1.0, abs=1e-8)
