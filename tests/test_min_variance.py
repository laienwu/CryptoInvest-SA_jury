"""Tests for the minimum variance portfolio module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.min_variance import (
    MinVarianceError,
    analyze_min_variance,
    optimize_min_variance,
)


# =============================================================================
# TestOptimizeMinVariance
# =============================================================================


class TestOptimizeMinVariance:
    """Tests for optimize_min_variance."""

    def test_weights_sum_to_one(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = optimize_min_variance(cov)
        assert sum(result["weights"]) == pytest.approx(1.0, abs=1e-4)

    def test_long_only(self):
        """All weights are non-negative."""
        cov = [
            [0.04, 0.01, 0.005],
            [0.01, 0.06, 0.01],
            [0.005, 0.01, 0.09],
        ]
        result = optimize_min_variance(cov)
        for w in result["weights"]:
            assert w >= -1e-6

    def test_single_asset(self):
        """Single asset gets weight 1.0."""
        result = optimize_min_variance([[0.04]])
        assert result["weights"] == [1.0]
        assert result["portfolio_volatility"] == pytest.approx(0.2, abs=1e-4)
        assert result["portfolio_variance"] == pytest.approx(0.04, abs=1e-4)

    def test_empty_matrix(self):
        result = optimize_min_variance([])
        assert result["weights"] == []
        assert result["portfolio_volatility"] == 0.0
        assert result["portfolio_variance"] == 0.0

    def test_prefers_low_vol_asset(self):
        """Optimizer should favor the lower-variance asset."""
        cov = [
            [0.01, 0.0],
            [0.0, 0.16],  # 16x the variance
        ]
        result = optimize_min_variance(cov)
        assert result["weights"][0] > result["weights"][1]

    def test_two_uncorrelated_equal_vol(self):
        """Two uncorrelated equal-vol assets → roughly equal weights."""
        cov = [[0.04, 0.0], [0.0, 0.04]]
        result = optimize_min_variance(cov)
        assert result["weights"][0] == pytest.approx(0.5, abs=0.01)
        assert result["weights"][1] == pytest.approx(0.5, abs=0.01)

    def test_portfolio_volatility_positive(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = optimize_min_variance(cov)
        assert result["portfolio_volatility"] > 0

    def test_variance_equals_vol_squared(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = optimize_min_variance(cov)
        vol = result["portfolio_volatility"]
        var = result["portfolio_variance"]
        assert var == pytest.approx(vol**2, abs=1e-4)

    def test_output_keys(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = optimize_min_variance(cov)
        assert "weights" in result
        assert "portfolio_volatility" in result
        assert "portfolio_variance" in result

    def test_three_assets(self):
        cov = [
            [0.04, 0.01, 0.005],
            [0.01, 0.06, 0.01],
            [0.005, 0.01, 0.09],
        ]
        result = optimize_min_variance(cov)
        assert len(result["weights"]) == 3
        assert sum(result["weights"]) == pytest.approx(1.0, abs=1e-4)
        assert result["portfolio_volatility"] > 0

    def test_lower_vol_than_any_individual(self):
        """Min-variance portfolio vol should be <= smallest individual vol."""
        cov = [
            [0.04, 0.005, 0.002],
            [0.005, 0.09, 0.003],
            [0.002, 0.003, 0.16],
        ]
        result = optimize_min_variance(cov)
        import math

        min_individual_vol = math.sqrt(0.04)  # 0.2
        assert result["portfolio_volatility"] <= min_individual_vol + 1e-4

    def test_lower_vol_than_equal_weight(self):
        """Min-variance should achieve lower vol than equal-weight."""
        cov = [
            [0.04, 0.01, 0.005],
            [0.01, 0.09, 0.01],
            [0.005, 0.01, 0.16],
        ]
        result = optimize_min_variance(cov)
        # Equal-weight variance
        n = 3
        ew = [1.0 / n] * n
        ew_var = 0.0
        for i in range(n):
            for j in range(n):
                ew_var += ew[i] * ew[j] * cov[i][j]
        import math

        ew_vol = math.sqrt(ew_var)
        assert result["portfolio_volatility"] <= ew_vol + 1e-6


# =============================================================================
# TestAnalyzeMinVariance
# =============================================================================


class TestAnalyzeMinVariance:
    """Tests for analyze_min_variance."""

    @pytest.fixture()
    def mock_storage(self):
        storage = MagicMock()
        storage.load_processed.side_effect = lambda name: {
            "returns": {
                "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                "annualized_mean": [0.15, 0.20, 0.25],
            },
            "covariance": {
                "matrix": [
                    [0.04, 0.01, 0.005],
                    [0.01, 0.06, 0.01],
                    [0.005, 0.01, 0.09],
                ]
            },
        }[name]
        return storage

    def test_basic_output_keys(self, mock_storage):
        result = analyze_min_variance(storage=mock_storage, save=False)
        assert "weights" in result
        assert "expected_return" in result
        assert "volatility" in result
        assert "sharpe_ratio" in result
        assert "equal_weight_volatility" in result
        assert "equal_weight_return" in result
        assert "volatility_reduction_pct" in result
        assert "n_assets" in result
        assert "method" in result

    def test_method_is_min_variance(self, mock_storage):
        result = analyze_min_variance(storage=mock_storage, save=False)
        assert result["method"] == "min_variance"

    def test_weights_are_named_dict(self, mock_storage):
        result = analyze_min_variance(storage=mock_storage, save=False)
        assert isinstance(result["weights"], dict)
        assert set(result["weights"].keys()) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def test_weights_sum_to_one(self, mock_storage):
        result = analyze_min_variance(storage=mock_storage, save=False)
        assert sum(result["weights"].values()) == pytest.approx(1.0, abs=1e-4)

    def test_saves_to_storage(self, mock_storage):
        analyze_min_variance(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        call_args = mock_storage.save_output.call_args
        assert call_args[0][1] == "min_variance"

    def test_no_save(self, mock_storage):
        analyze_min_variance(storage=mock_storage, save=False)
        mock_storage.save_output.assert_not_called()

    def test_missing_data_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = FileNotFoundError("not found")
        with pytest.raises(MinVarianceError, match="not found"):
            analyze_min_variance(storage=storage)

    def test_empty_data_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = lambda name: {
            "returns": {"symbols": [], "annualized_mean": []},
            "covariance": {"matrix": []},
        }[name]
        with pytest.raises(MinVarianceError, match="incomplete"):
            analyze_min_variance(storage=storage)

    def test_volatility_reduction_computed(self, mock_storage):
        """Volatility reduction should be positive (min-var beats equal-weight)."""
        result = analyze_min_variance(storage=mock_storage, save=False)
        assert result["volatility_reduction_pct"] > 0

    def test_vol_lower_than_equal_weight(self, mock_storage):
        """Min-variance volatility should be <= equal-weight volatility."""
        result = analyze_min_variance(storage=mock_storage, save=False)
        assert result["volatility"] <= result["equal_weight_volatility"] + 1e-6

    def test_n_assets(self, mock_storage):
        result = analyze_min_variance(storage=mock_storage, save=False)
        assert result["n_assets"] == 3


# =============================================================================
# TestMinVarianceError
# =============================================================================


class TestMinVarianceError:
    """Tests for MinVarianceError."""

    def test_message(self):
        err = MinVarianceError("test error")
        assert err.message == "test error"
        assert str(err) == "test error"

    def test_operation(self):
        err = MinVarianceError("fail", operation="optimize")
        assert err.operation == "optimize"

    def test_default_operation(self):
        err = MinVarianceError("fail")
        assert err.operation == "min_variance"
