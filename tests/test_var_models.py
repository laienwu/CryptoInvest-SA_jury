"""Tests for the Value-at-Risk comparison module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.var_models import (
    VaRError,
    _excess_kurtosis,
    _norm_ppf,
    _skewness,
    analyze_var,
    compare_var_models,
    cornish_fisher_cvar,
    cornish_fisher_var,
    historical_cvar,
    historical_var,
    parametric_cvar,
    parametric_var,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RETURNS_MIXED = [0.02, -0.03, 0.01, -0.05, 0.04, -0.01, 0.03, -0.02, 0.005, -0.015] * 5
"""50 mixed returns for general testing."""

RETURNS_ALL_POSITIVE = [0.01, 0.02, 0.015, 0.005, 0.03] * 4
"""20 positive-only returns."""


@pytest.fixture()
def mock_storage():
    """Mock storage with portfolio weights and per-asset returns."""
    storage = MagicMock()
    storage.load_output.return_value = {
        "weights": {
            "BTCUSDT": 0.50,
            "ETHUSDT": 0.30,
            "SOLUSDT": 0.20,
        },
        "expected_return": 0.10,
        "volatility": 0.25,
    }
    storage.load_processed.return_value = {
        "BTCUSDT": [0.02, -0.03, 0.01, -0.05, 0.04, -0.01, 0.03, -0.02, 0.005, -0.015] * 5,
        "ETHUSDT": [0.03, -0.04, 0.02, -0.06, 0.05, -0.02, 0.04, -0.03, 0.01, -0.02] * 5,
        "SOLUSDT": [0.04, -0.05, 0.03, -0.07, 0.06, -0.03, 0.05, -0.04, 0.015, -0.025] * 5,
    }
    return storage


# ---------------------------------------------------------------------------
# Historical VaR
# ---------------------------------------------------------------------------


class TestHistoricalVaR:
    def test_basic(self):
        var = historical_var(RETURNS_MIXED)
        assert var > 0

    def test_all_positive_returns(self):
        var = historical_var(RETURNS_ALL_POSITIVE)
        # VaR should be negative of a positive return → negative loss
        # (i.e. no actual loss)
        assert isinstance(var, float)

    def test_higher_confidence_higher_var(self):
        var_90 = historical_var(RETURNS_MIXED, confidence=0.90)
        var_99 = historical_var(RETURNS_MIXED, confidence=0.99)
        assert var_99 >= var_90

    def test_empty_returns_raises(self):
        with pytest.raises(VaRError, match="empty"):
            historical_var([])

    def test_single_return(self):
        var = historical_var([0.01])
        assert isinstance(var, float)


# ---------------------------------------------------------------------------
# Historical CVaR
# ---------------------------------------------------------------------------


class TestHistoricalCVaR:
    def test_basic(self):
        cvar = historical_cvar(RETURNS_MIXED)
        assert cvar > 0

    def test_cvar_ge_var(self):
        var = historical_var(RETURNS_MIXED)
        cvar = historical_cvar(RETURNS_MIXED)
        assert cvar >= var

    def test_empty_raises(self):
        with pytest.raises(VaRError, match="empty"):
            historical_cvar([])


# ---------------------------------------------------------------------------
# Parametric VaR
# ---------------------------------------------------------------------------


class TestParametricVaR:
    def test_basic(self):
        var = parametric_var(mean=0.001, std=0.02)
        assert var > 0

    def test_zero_volatility(self):
        var = parametric_var(mean=0.001, std=0.0)
        # With no volatility, VaR = -mean (could be negative if mean > 0)
        assert var == pytest.approx(-0.001)

    def test_high_confidence(self):
        var_95 = parametric_var(mean=0.001, std=0.02, confidence=0.95)
        var_99 = parametric_var(mean=0.001, std=0.02, confidence=0.99)
        assert var_99 > var_95

    def test_negative_mean_increases_var(self):
        var_pos = parametric_var(mean=0.01, std=0.02)
        var_neg = parametric_var(mean=-0.01, std=0.02)
        assert var_neg > var_pos


# ---------------------------------------------------------------------------
# Parametric CVaR
# ---------------------------------------------------------------------------


class TestParametricCVaR:
    def test_basic(self):
        cvar = parametric_cvar(mean=0.001, std=0.02)
        assert cvar > 0

    def test_cvar_ge_var(self):
        var = parametric_var(mean=0.001, std=0.02)
        cvar = parametric_cvar(mean=0.001, std=0.02)
        assert cvar >= var

    def test_zero_volatility(self):
        cvar = parametric_cvar(mean=0.001, std=0.0)
        assert isinstance(cvar, float)


# ---------------------------------------------------------------------------
# Skewness & Kurtosis
# ---------------------------------------------------------------------------


class TestSkewnessKurtosis:
    def test_symmetric_returns_near_zero(self):
        symmetric = [-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03] * 3
        s = _skewness(symmetric)
        assert abs(s) < 0.3

    def test_normal_like_kurtosis(self):
        # Uniform-ish returns should have negative excess kurtosis
        uniform = [float(i) / 100 for i in range(-10, 11)] * 2
        k = _excess_kurtosis(uniform)
        assert k < 1.0  # Not fat-tailed

    def test_skewness_too_few_raises(self):
        with pytest.raises(VaRError, match="3 observations"):
            _skewness([0.01, 0.02])

    def test_kurtosis_too_few_raises(self):
        with pytest.raises(VaRError, match="4 observations"):
            _excess_kurtosis([0.01, 0.02, 0.03])

    def test_constant_returns_zero(self):
        assert _skewness([0.01, 0.01, 0.01, 0.01]) == 0.0
        assert _excess_kurtosis([0.01, 0.01, 0.01, 0.01]) == 0.0


# ---------------------------------------------------------------------------
# Cornish-Fisher VaR
# ---------------------------------------------------------------------------


class TestCornishFisherVaR:
    def test_basic(self):
        var = cornish_fisher_var(RETURNS_MIXED)
        assert var > 0

    def test_near_normal_close_to_parametric(self):
        """For near-normal returns, CF should be close to parametric."""
        # Large sample of near-symmetric returns
        returns = [0.01, -0.01, 0.005, -0.005, 0.002, -0.002] * 20
        cf_var = cornish_fisher_var(returns)
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        import math
        std = math.sqrt(variance)
        p_var = parametric_var(mean, std)
        # Should be reasonably close
        assert abs(cf_var - p_var) < 0.01

    def test_skewed_returns(self):
        # Left-skewed: more large negatives
        skewed = [-0.10, -0.08, -0.05, 0.01, 0.02, 0.015, 0.01, 0.005] * 5
        var = cornish_fisher_var(skewed)
        assert var > 0

    def test_too_few_raises(self):
        with pytest.raises(VaRError, match="4 observations"):
            cornish_fisher_var([0.01, 0.02, 0.03])


# ---------------------------------------------------------------------------
# Cornish-Fisher CVaR
# ---------------------------------------------------------------------------


class TestCornishFisherCVaR:
    def test_basic(self):
        cvar = cornish_fisher_cvar(RETURNS_MIXED)
        assert cvar > 0

    def test_cvar_ge_var(self):
        var = cornish_fisher_var(RETURNS_MIXED)
        cvar = cornish_fisher_cvar(RETURNS_MIXED)
        assert cvar >= var


# ---------------------------------------------------------------------------
# compare_var_models
# ---------------------------------------------------------------------------


class TestCompareVarModels:
    def test_return_keys(self):
        result = compare_var_models(RETURNS_MIXED)
        assert "historical" in result
        assert "parametric" in result
        assert "cornish_fisher" in result
        assert "confidence" in result
        assert "n_observations" in result

    def test_all_positive_values(self):
        result = compare_var_models(RETURNS_MIXED)
        assert result["historical"]["var"] > 0
        assert result["parametric"]["var"] > 0
        assert result["cornish_fisher"]["var"] > 0

    def test_confidence_passed_through(self):
        result = compare_var_models(RETURNS_MIXED, confidence=0.99)
        assert result["confidence"] == 0.99

    def test_n_observations(self):
        result = compare_var_models(RETURNS_MIXED)
        assert result["n_observations"] == len(RETURNS_MIXED)

    def test_too_few_raises(self):
        with pytest.raises(VaRError, match="4 observations"):
            compare_var_models([0.01, 0.02, 0.03])


# ---------------------------------------------------------------------------
# analyze_var
# ---------------------------------------------------------------------------


class TestAnalyzeVar:
    def test_basic(self, mock_storage):
        result = analyze_var(storage=mock_storage, save=False)
        assert "portfolio" in result
        assert "asset_var" in result
        assert result["confidence"] == 0.95

    def test_saves_to_storage(self, mock_storage):
        analyze_var(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        args = mock_storage.save_output.call_args
        assert args[0][1] == "var_analysis"

    def test_no_save(self, mock_storage):
        analyze_var(storage=mock_storage, save=False)
        mock_storage.save_output.assert_not_called()

    def test_missing_portfolio_raises(self):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(VaRError, match="weights not found"):
            analyze_var(storage=storage, save=False)

    def test_missing_returns_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {
            "weights": {"BTCUSDT": 0.5, "ETHUSDT": 0.5},
        }
        storage.load_processed.side_effect = FileNotFoundError("not found")
        with pytest.raises(VaRError, match="Returns data not found"):
            analyze_var(storage=storage, save=False)

    def test_no_matching_returns_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {
            "weights": {"BTCUSDT": 0.5, "ETHUSDT": 0.5},
        }
        storage.load_processed.return_value = {"AAPL": [0.01, 0.02, 0.03]}
        with pytest.raises(VaRError, match="No return data"):
            analyze_var(storage=storage, save=False)

    def test_per_asset_var_breakdown(self, mock_storage):
        result = analyze_var(storage=mock_storage, save=False)
        assert len(result["asset_var"]) == 3
        for entry in result["asset_var"]:
            assert "symbol" in entry
            assert "historical_var" in entry
            assert "parametric_var" in entry
            assert "cornish_fisher_var" in entry

    def test_dict_values_format(self):
        """Test that returns stored as dict with 'values' key are handled."""
        storage = MagicMock()
        storage.load_output.return_value = {
            "weights": {"BTCUSDT": 1.0},
        }
        storage.load_processed.return_value = {
            "BTCUSDT": {"values": [0.02, -0.03, 0.01, -0.05, 0.04] * 4},
        }
        result = analyze_var(storage=storage, save=False)
        assert result["n_observations"] == 20


# ---------------------------------------------------------------------------
# VaRError
# ---------------------------------------------------------------------------


class TestVaRError:
    def test_message(self):
        err = VaRError("test error", operation="test_op")
        assert err.message == "test error"
        assert str(err) == "test error"

    def test_operation(self):
        err = VaRError("msg", operation="load")
        assert err.operation == "load"

    def test_default_operation(self):
        err = VaRError("msg")
        assert err.operation == "var"


# ---------------------------------------------------------------------------
# _norm_ppf edge cases
# ---------------------------------------------------------------------------


class TestNormPpf:
    def test_median(self):
        """ppf(0.5) should be ~0."""
        assert abs(_norm_ppf(0.5)) < 0.01

    def test_95th_percentile(self):
        """ppf(0.95) should be ~1.645."""
        assert abs(_norm_ppf(0.95) - 1.645) < 0.01

    def test_invalid_p_raises(self):
        with pytest.raises(VaRError):
            _norm_ppf(0.0)
        with pytest.raises(VaRError):
            _norm_ppf(1.0)
