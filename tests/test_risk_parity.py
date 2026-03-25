"""Tests for risk parity optimization module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.risk_parity import (
    RiskParityError,
    compute_risk_parity_weights,
    optimize_risk_parity,
)


class TestComputeRiskParityWeights:
    """Tests for compute_risk_parity_weights."""

    def test_empty_matrix(self):
        result = compute_risk_parity_weights([])
        assert result["weights"] == []
        assert result["converged"] is True

    def test_single_asset(self):
        result = compute_risk_parity_weights([[0.04]])
        assert len(result["weights"]) == 1
        assert result["weights"][0] == pytest.approx(1.0, abs=1e-4)

    def test_two_equal_assets(self):
        """Two assets with identical volatility → equal weights."""
        cov = [[0.04, 0.01], [0.01, 0.04]]
        result = compute_risk_parity_weights(cov)
        assert result["weights"][0] == pytest.approx(0.5, abs=0.01)
        assert result["weights"][1] == pytest.approx(0.5, abs=0.01)

    def test_weights_sum_to_one(self):
        cov = [
            [0.04, 0.01, 0.005],
            [0.01, 0.09, 0.01],
            [0.005, 0.01, 0.16],
        ]
        result = compute_risk_parity_weights(cov)
        assert sum(result["weights"]) == pytest.approx(1.0, abs=1e-4)

    def test_higher_vol_gets_lower_weight(self):
        """Asset with higher variance should get lower weight."""
        cov = [
            [0.01, 0.0],
            [0.0, 0.16],  # 4x the variance
        ]
        result = compute_risk_parity_weights(cov)
        assert result["weights"][0] > result["weights"][1]

    def test_equal_risk_contribution(self):
        """Each asset should contribute ~1/N to total risk."""
        cov = [
            [0.04, 0.01, 0.005],
            [0.01, 0.09, 0.01],
            [0.005, 0.01, 0.16],
        ]
        result = compute_risk_parity_weights(cov)
        target = 1.0 / 3
        for pct in result["pct_contributions"]:
            assert pct == pytest.approx(target, abs=0.01)

    def test_converges(self):
        cov = [
            [0.04, 0.01],
            [0.01, 0.09],
        ]
        result = compute_risk_parity_weights(cov)
        assert result["converged"] is True

    def test_portfolio_volatility_positive(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = compute_risk_parity_weights(cov)
        assert result["portfolio_volatility"] > 0

    def test_output_keys(self):
        cov = [[0.04, 0.01], [0.01, 0.09]]
        result = compute_risk_parity_weights(cov)
        assert "weights" in result
        assert "risk_contributions" in result
        assert "pct_contributions" in result
        assert "converged" in result
        assert "iterations" in result


class TestOptimizeRiskParity:
    """Tests for optimize_risk_parity."""

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

    def test_output_keys(self, mock_storage):
        result = optimize_risk_parity(storage=mock_storage, save=False)
        assert "weights" in result
        assert "expected_return" in result
        assert "volatility" in result
        assert "sharpe_ratio" in result
        assert "contributions" in result
        assert "optimization_method" in result

    def test_method_is_risk_parity(self, mock_storage):
        result = optimize_risk_parity(storage=mock_storage, save=False)
        assert result["optimization_method"] == "risk_parity"

    def test_weights_are_dict(self, mock_storage):
        result = optimize_risk_parity(storage=mock_storage, save=False)
        assert isinstance(result["weights"], dict)
        assert set(result["weights"].keys()) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def test_weights_sum_to_one(self, mock_storage):
        result = optimize_risk_parity(storage=mock_storage, save=False)
        assert sum(result["weights"].values()) == pytest.approx(1.0, abs=1e-4)

    def test_save_to_storage(self, mock_storage):
        optimize_risk_parity(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()

    def test_missing_data_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = FileNotFoundError("not found")
        with pytest.raises(RiskParityError, match="not found"):
            optimize_risk_parity(storage=storage)

    def test_empty_data_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = lambda name: {
            "returns": {"symbols": [], "annualized_mean": []},
            "covariance": {"matrix": []},
        }[name]
        with pytest.raises(RiskParityError, match="incomplete"):
            optimize_risk_parity(storage=storage)
