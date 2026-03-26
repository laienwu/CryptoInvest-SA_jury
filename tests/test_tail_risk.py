"""Tests for tail risk analysis module."""

import math
from unittest.mock import MagicMock

import pytest

from src.pipeline.tail_risk import (
    TailRiskError,
    analyze_tail_risk,
    calmar_ratio,
    compute_tail_metrics,
    excess_kurtosis,
    jarque_bera_statistic,
    max_drawdown,
    omega_ratio,
    skewness,
)


class TestSkewness:
    """Tests for skewness function."""

    def test_symmetric_distribution_near_zero(self):
        # Symmetric around 0
        data = [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0]
        assert skewness(data) == pytest.approx(0.0, abs=0.01)

    def test_right_skewed_positive(self):
        # Mostly small values with a few large outliers
        data = [0.01, 0.02, 0.01, 0.03, 0.02, 0.01, 0.50]
        assert skewness(data) > 0

    def test_left_skewed_negative(self):
        # Mostly high values with a few large negative outliers
        data = [-0.50, 0.02, 0.03, 0.02, 0.03, 0.02, 0.03]
        assert skewness(data) < 0

    def test_too_few_observations_raises(self):
        with pytest.raises(TailRiskError, match="at least 3"):
            skewness([1.0, 2.0])

    def test_constant_returns_zero(self):
        data = [0.01, 0.01, 0.01, 0.01]
        assert skewness(data) == 0.0

    def test_three_observations_minimum(self):
        # Should not raise with exactly 3
        result = skewness([1.0, 2.0, 3.0])
        assert isinstance(result, float)


class TestExcessKurtosis:
    """Tests for excess_kurtosis function."""

    def test_normal_like_near_zero(self):
        # Large-ish sample from uniform-like spread; excess kurtosis ~ negative
        # For uniform distribution, excess kurtosis = -1.2
        import random
        random.seed(42)
        data = [random.gauss(0, 1) for _ in range(10000)]
        k = excess_kurtosis(data)
        assert abs(k) < 0.5  # Should be close to 0 for normal

    def test_heavy_tails_positive(self):
        # Distribution with extreme outliers
        data = [0.01] * 50 + [-0.50, 0.50]
        k = excess_kurtosis(data)
        assert k > 0

    def test_light_tails_negative(self):
        # Uniform-like distribution has negative excess kurtosis
        data = list(range(100))
        data = [x / 100.0 for x in data]
        k = excess_kurtosis(data)
        assert k < 0

    def test_too_few_observations_raises(self):
        with pytest.raises(TailRiskError, match="at least 4"):
            excess_kurtosis([1.0, 2.0, 3.0])

    def test_constant_returns_zero(self):
        data = [0.05] * 10
        assert excess_kurtosis(data) == 0.0


class TestJarqueBera:
    """Tests for jarque_bera_statistic function."""

    def test_normal_data_is_normal(self):
        import random
        random.seed(123)
        data = [random.gauss(0, 1) for _ in range(1000)]
        result = jarque_bera_statistic(data)
        assert "statistic" in result
        assert "is_normal" in result
        assert result["is_normal"] is True

    def test_non_normal_data(self):
        # Highly skewed data should fail normality
        data = [0.01] * 100 + [5.0]
        result = jarque_bera_statistic(data)
        assert result["is_normal"] is False
        assert result["statistic"] > 5.991

    def test_threshold_boundary(self):
        result = jarque_bera_statistic([0.01, -0.01, 0.02, -0.02, 0.0])
        assert isinstance(result["statistic"], float)
        assert isinstance(result["is_normal"], bool)

    def test_too_few_raises(self):
        with pytest.raises(TailRiskError, match="at least 4"):
            jarque_bera_statistic([1.0, 2.0, 3.0])


class TestOmegaRatio:
    """Tests for omega_ratio function."""

    def test_all_positive_returns(self):
        data = [0.01, 0.02, 0.03, 0.04]
        result = omega_ratio(data)
        assert result == float("inf")

    def test_all_negative_returns(self):
        data = [-0.01, -0.02, -0.03, -0.04]
        result = omega_ratio(data)
        assert result == 0.0

    def test_mixed_returns(self):
        data = [0.10, -0.05, 0.08, -0.03]
        result = omega_ratio(data)
        assert result > 0
        # gains = 0.10 + 0.08 = 0.18, losses = 0.05 + 0.03 = 0.08
        assert result == pytest.approx(0.18 / 0.08, abs=0.01)

    def test_custom_threshold(self):
        data = [0.05, 0.06, 0.07, -0.01]
        # With threshold=0.05, gains above 0.05: 0.01+0.02=0.03
        # losses below 0.05: 0.05+0.01+0.06=0.06... let me compute
        # r=0.05: not > 0.05, not < 0.05 -> neither
        # r=0.06: gain = 0.01
        # r=0.07: gain = 0.02
        # r=-0.01: loss = 0.06
        # omega = 0.03 / 0.06 = 0.5
        result = omega_ratio(data, threshold=0.05)
        assert result == pytest.approx(0.5, abs=0.01)

    def test_empty_returns(self):
        assert omega_ratio([]) == 0.0

    def test_zero_returns(self):
        data = [0.0, 0.0, 0.0]
        assert omega_ratio(data) == 0.0


class TestCalmarRatio:
    """Tests for calmar_ratio function."""

    def test_basic_positive(self):
        # Steady positive returns with some drawdown
        data = [0.02, -0.05, 0.03, 0.01, 0.02]
        result = calmar_ratio(data)
        assert result > 0

    def test_zero_drawdown_returns_zero(self):
        # Monotonically increasing wealth -> no drawdown
        data = [0.01, 0.02, 0.03, 0.04]
        result = calmar_ratio(data)
        assert result == 0.0

    def test_negative_returns_negative_ratio(self):
        data = [-0.10, -0.05, -0.03]
        result = calmar_ratio(data)
        assert result < 0

    def test_custom_annualized_return(self):
        data = [0.01, -0.05, 0.02]
        result = calmar_ratio(data, annualized_return=0.15)
        mdd = max_drawdown(data)
        assert result == pytest.approx(0.15 / mdd, abs=0.01)

    def test_empty_returns(self):
        assert calmar_ratio([]) == 0.0


class TestMaxDrawdown:
    """Tests for max_drawdown function."""

    def test_no_drawdown(self):
        data = [0.01, 0.02, 0.03, 0.04]
        assert max_drawdown(data) == 0.0

    def test_simple_drawdown(self):
        # Start at 1.0, go to 1.10, drop to 1.10*0.90 = 0.99
        data = [0.10, -0.10]
        mdd = max_drawdown(data)
        # Peak = 1.10, trough = 0.99, dd = (1.10-0.99)/1.10 ≈ 0.10
        assert mdd == pytest.approx(0.10, abs=0.01)

    def test_full_loss(self):
        data = [-1.0]
        mdd = max_drawdown(data)
        assert mdd == pytest.approx(1.0, abs=0.001)

    def test_empty_returns(self):
        assert max_drawdown([]) == 0.0

    def test_recovery_after_drawdown(self):
        data = [0.10, -0.20, 0.30]
        mdd = max_drawdown(data)
        # Peak 1.10, trough 0.88, dd = 0.22/1.10 = 0.2
        assert mdd == pytest.approx(0.2, abs=0.01)


class TestComputeTailMetrics:
    """Tests for compute_tail_metrics function."""

    def test_all_keys_present(self):
        data = [0.01, -0.02, 0.03, -0.01, 0.02]
        result = compute_tail_metrics(data)
        expected_keys = {
            "symbol", "skewness", "excess_kurtosis", "jarque_bera",
            "is_normal", "omega_ratio", "calmar_ratio", "max_drawdown",
            "n_observations",
        }
        assert set(result.keys()) == expected_keys

    def test_symbol_in_result(self):
        data = [0.01, -0.02, 0.03, -0.01, 0.02]
        result = compute_tail_metrics(data, symbol="BTCUSDT")
        assert result["symbol"] == "BTCUSDT"

    def test_default_symbol(self):
        data = [0.01, -0.02, 0.03, -0.01, 0.02]
        result = compute_tail_metrics(data)
        assert result["symbol"] == "portfolio"

    def test_n_observations(self):
        data = [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03]
        result = compute_tail_metrics(data)
        assert result["n_observations"] == 7

    def test_too_few_returns_defaults(self):
        result = compute_tail_metrics([0.01, 0.02])
        assert result["skewness"] == 0.0
        assert result["n_observations"] == 2


class TestAnalyzeTailRisk:
    """Tests for analyze_tail_risk function."""

    @pytest.fixture()
    def mock_storage(self):
        storage = MagicMock()
        storage.load_output.return_value = {
            "weights": {
                "BTCUSDT": 0.50,
                "ETHUSDT": 0.30,
                "SOLUSDT": 0.20,
            },
        }
        storage.load_processed.return_value = {
            "BTCUSDT": [0.02, -0.01, 0.03, -0.02, 0.01],
            "ETHUSDT": [0.01, -0.03, 0.02, 0.01, -0.01],
            "SOLUSDT": [-0.01, 0.02, -0.01, 0.03, 0.02],
        }
        return storage

    def test_basic_output_keys(self, mock_storage):
        result = analyze_tail_risk(storage=mock_storage, save=False)
        assert "portfolio_metrics" in result
        assert "per_asset" in result
        assert "n_assets" in result
        assert "method" in result
        assert result["method"] == "tail_risk"

    def test_saves_to_storage(self, mock_storage):
        analyze_tail_risk(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        assert mock_storage.save_output.call_args[0][1] == "tail_risk"

    def test_no_save(self, mock_storage):
        analyze_tail_risk(storage=mock_storage, save=False)
        mock_storage.save_output.assert_not_called()

    def test_n_assets_matches(self, mock_storage):
        result = analyze_tail_risk(storage=mock_storage, save=False)
        assert result["n_assets"] == 3
        assert len(result["per_asset"]) == 3

    def test_portfolio_metrics_has_keys(self, mock_storage):
        result = analyze_tail_risk(storage=mock_storage, save=False)
        pm = result["portfolio_metrics"]
        assert "skewness" in pm
        assert "excess_kurtosis" in pm
        assert "max_drawdown" in pm
        assert pm["symbol"] == "portfolio"

    def test_per_asset_symbols(self, mock_storage):
        result = analyze_tail_risk(storage=mock_storage, save=False)
        symbols = {a["symbol"] for a in result["per_asset"]}
        assert symbols == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def test_missing_weights_raises(self):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(TailRiskError, match="weights not found"):
            analyze_tail_risk(storage=storage)

    def test_empty_weights_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {}}
        with pytest.raises(TailRiskError, match="no weights"):
            analyze_tail_risk(storage=storage)

    def test_missing_returns_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {"BTCUSDT": 1.0}}
        storage.load_processed.side_effect = FileNotFoundError("not found")
        with pytest.raises(TailRiskError, match="Returns data not found"):
            analyze_tail_risk(storage=storage)

    def test_no_matching_symbols_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {"BTCUSDT": 1.0}}
        storage.load_processed.return_value = {"ETHUSDT": [0.01, 0.02]}
        with pytest.raises(TailRiskError, match="No return data"):
            analyze_tail_risk(storage=storage)


class TestTailRiskError:
    """Tests for TailRiskError exception."""

    def test_message(self):
        err = TailRiskError("something failed")
        assert str(err) == "something failed"
        assert err.message == "something failed"

    def test_operation(self):
        err = TailRiskError("failed", operation="load")
        assert err.operation == "load"

    def test_default_operation(self):
        err = TailRiskError("failed")
        assert err.operation == "tail_risk"
