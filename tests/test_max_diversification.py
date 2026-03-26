"""Tests for maximum diversification portfolio module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.max_diversification import (
    MaxDiversificationError,
    analyze_max_diversification,
    diversification_ratio,
    optimize_max_diversification,
)


# =============================================================================
# TestDiversificationRatio
# =============================================================================


class TestDiversificationRatio:
    """Tests for diversification_ratio."""

    def test_single_asset_is_one(self):
        """Single asset has diversification ratio of 1.0."""
        assert diversification_ratio([1.0], [[0.04]]) == pytest.approx(1.0, abs=1e-6)

    def test_equal_weights_two_correlated(self):
        """Two correlated assets with equal weights should have DR >= 1."""
        cov = [[0.04, 0.01], [0.01, 0.04]]
        dr = diversification_ratio([0.5, 0.5], cov)
        assert dr >= 1.0

    def test_equal_weights_uncorrelated(self):
        """Uncorrelated assets should have higher DR than correlated ones."""
        cov_uncorr = [[0.04, 0.0], [0.0, 0.04]]
        cov_corr = [[0.04, 0.03], [0.03, 0.04]]
        dr_uncorr = diversification_ratio([0.5, 0.5], cov_uncorr)
        dr_corr = diversification_ratio([0.5, 0.5], cov_corr)
        assert dr_uncorr > dr_corr

    def test_perfectly_correlated_is_one(self):
        """Perfectly correlated assets give DR = 1.0."""
        # cov = sigma_i * sigma_j * rho, rho=1 → cov = sqrt(0.04)*sqrt(0.09) = 0.06
        cov = [[0.04, 0.06], [0.06, 0.09]]
        dr = diversification_ratio([0.5, 0.5], cov)
        assert dr == pytest.approx(1.0, abs=1e-4)

    def test_empty_weights(self):
        """Empty weights returns 1.0."""
        assert diversification_ratio([], []) == 1.0

    def test_concentrated_single_asset(self):
        """All weight in one asset → DR = 1.0."""
        cov = [[0.04, 0.01], [0.01, 0.09]]
        dr = diversification_ratio([1.0, 0.0], cov)
        assert dr == pytest.approx(1.0, abs=1e-4)

    def test_three_assets(self):
        """Three assets with diversification benefit."""
        cov = [
            [0.04, 0.005, 0.002],
            [0.005, 0.09, 0.003],
            [0.002, 0.003, 0.16],
        ]
        dr = diversification_ratio([1.0 / 3] * 3, cov)
        assert dr > 1.0


# =============================================================================
# TestOptimizeMaxDiversification
# =============================================================================


class TestOptimizeMaxDiversification:
    """Tests for optimize_max_diversification."""

    def test_weights_sum_to_one(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = optimize_max_diversification(cov)
        assert sum(result["weights"]) == pytest.approx(1.0, abs=1e-4)

    def test_long_only(self):
        """All weights are non-negative."""
        cov = [
            [0.04, 0.01, 0.005],
            [0.01, 0.06, 0.01],
            [0.005, 0.01, 0.09],
        ]
        result = optimize_max_diversification(cov)
        for w in result["weights"]:
            assert w >= -1e-6

    def test_two_assets(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = optimize_max_diversification(cov)
        assert len(result["weights"]) == 2
        assert result["diversification_ratio"] >= 1.0

    def test_uncorrelated_assets_high_ratio(self):
        """Uncorrelated assets should yield a high diversification ratio."""
        cov = [[0.04, 0.0], [0.0, 0.04]]
        result = optimize_max_diversification(cov)
        assert result["diversification_ratio"] > 1.3

    def test_output_keys(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = optimize_max_diversification(cov)
        assert "weights" in result
        assert "diversification_ratio" in result
        assert "portfolio_volatility" in result

    def test_single_asset(self):
        result = optimize_max_diversification([[0.04]])
        assert result["weights"] == [1.0]
        assert result["diversification_ratio"] == pytest.approx(1.0, abs=1e-4)

    def test_empty_matrix(self):
        result = optimize_max_diversification([])
        assert result["weights"] == []
        assert result["diversification_ratio"] == 1.0
        assert result["portfolio_volatility"] == 0.0

    def test_portfolio_volatility_positive(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = optimize_max_diversification(cov)
        assert result["portfolio_volatility"] > 0

    def test_three_assets_favors_low_correlation(self):
        """Optimizer should put less weight on highly correlated pair."""
        cov = [
            [0.04, 0.035, 0.0],
            [0.035, 0.04, 0.0],
            [0.0, 0.0, 0.04],
        ]
        result = optimize_max_diversification(cov)
        # Asset 3 (uncorrelated) should get meaningful weight
        assert result["weights"][2] > 0.2


# =============================================================================
# TestAnalyzeMaxDiversification
# =============================================================================


class TestAnalyzeMaxDiversification:
    """Tests for analyze_max_diversification."""

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
        result = analyze_max_diversification(storage=mock_storage, save=False)
        assert "weights" in result
        assert "expected_return" in result
        assert "volatility" in result
        assert "sharpe_ratio" in result
        assert "diversification_ratio" in result
        assert "n_assets" in result
        assert "method" in result

    def test_method_is_max_diversification(self, mock_storage):
        result = analyze_max_diversification(storage=mock_storage, save=False)
        assert result["method"] == "max_diversification"

    def test_weights_are_named_dict(self, mock_storage):
        result = analyze_max_diversification(storage=mock_storage, save=False)
        assert isinstance(result["weights"], dict)
        assert set(result["weights"].keys()) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def test_weights_sum_to_one(self, mock_storage):
        result = analyze_max_diversification(storage=mock_storage, save=False)
        assert sum(result["weights"].values()) == pytest.approx(1.0, abs=1e-4)

    def test_saves_to_storage(self, mock_storage):
        analyze_max_diversification(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        call_args = mock_storage.save_output.call_args
        assert call_args[0][1] == "max_diversification"

    def test_no_save(self, mock_storage):
        analyze_max_diversification(storage=mock_storage, save=False)
        mock_storage.save_output.assert_not_called()

    def test_missing_data_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = FileNotFoundError("not found")
        with pytest.raises(MaxDiversificationError, match="not found"):
            analyze_max_diversification(storage=storage)

    def test_empty_data_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = lambda name: {
            "returns": {"symbols": [], "annualized_mean": []},
            "covariance": {"matrix": []},
        }[name]
        with pytest.raises(MaxDiversificationError, match="incomplete"):
            analyze_max_diversification(storage=storage)


# =============================================================================
# TestMaxDiversificationError
# =============================================================================


class TestMaxDiversificationError:
    """Tests for MaxDiversificationError."""

    def test_message(self):
        err = MaxDiversificationError("test error")
        assert err.message == "test error"
        assert str(err) == "test error"

    def test_operation(self):
        err = MaxDiversificationError("fail", operation="optimize")
        assert err.operation == "optimize"

    def test_default_operation(self):
        err = MaxDiversificationError("fail")
        assert err.operation == "max_diversification"
