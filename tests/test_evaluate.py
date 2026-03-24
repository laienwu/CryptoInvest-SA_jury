"""Tests for custom portfolio evaluation module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.evaluate import EvaluateError, evaluate_custom_portfolio


@pytest.fixture()
def mock_storage():
    """Mock storage with returns and covariance data."""
    storage = MagicMock()
    storage.load_processed.side_effect = lambda name: {
        "returns": {
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "annualized_mean": [0.15, 0.20, 0.25],
            "values": [[0.01, 0.02, 0.01]],
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


class TestEvaluateCustomPortfolio:
    """Tests for evaluate_custom_portfolio."""

    def test_output_keys(self, mock_storage):
        result = evaluate_custom_portfolio(
            {"BTCUSDT": 0.5, "ETHUSDT": 0.3, "SOLUSDT": 0.2},
            storage=mock_storage,
        )
        assert "weights" in result
        assert "expected_return" in result
        assert "volatility" in result
        assert "sharpe_ratio" in result
        assert "contributions" in result
        assert "n_assets" in result

    def test_expected_return_computed(self, mock_storage):
        result = evaluate_custom_portfolio(
            {"BTCUSDT": 1.0, "ETHUSDT": 0.0, "SOLUSDT": 0.0},
            storage=mock_storage,
        )
        assert result["expected_return"] == pytest.approx(0.15, abs=1e-4)

    def test_volatility_positive(self, mock_storage):
        result = evaluate_custom_portfolio(
            {"BTCUSDT": 0.5, "ETHUSDT": 0.3, "SOLUSDT": 0.2},
            storage=mock_storage,
        )
        assert result["volatility"] > 0

    def test_sharpe_with_risk_free(self, mock_storage):
        result = evaluate_custom_portfolio(
            {"BTCUSDT": 0.5, "ETHUSDT": 0.3, "SOLUSDT": 0.2},
            risk_free_rate=0.05,
            storage=mock_storage,
        )
        assert result["risk_free_rate"] == 0.05
        assert result["sharpe_ratio"] > 0

    def test_contributions_per_asset(self, mock_storage):
        result = evaluate_custom_portfolio(
            {"BTCUSDT": 0.5, "ETHUSDT": 0.3, "SOLUSDT": 0.2},
            storage=mock_storage,
        )
        symbols = {c["symbol"] for c in result["contributions"]}
        assert symbols == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def test_n_assets(self, mock_storage):
        result = evaluate_custom_portfolio(
            {"BTCUSDT": 0.6, "ETHUSDT": 0.4},
            storage=mock_storage,
        )
        assert result["n_assets"] == 2

    def test_empty_weights_raises(self, mock_storage):
        with pytest.raises(EvaluateError, match="No weights"):
            evaluate_custom_portfolio({}, storage=mock_storage)

    def test_weights_not_sum_to_one_raises(self, mock_storage):
        with pytest.raises(EvaluateError, match="sum to"):
            evaluate_custom_portfolio(
                {"BTCUSDT": 0.5, "ETHUSDT": 0.1}, storage=mock_storage
            )

    def test_unknown_symbol_raises(self, mock_storage):
        with pytest.raises(EvaluateError, match="Unknown symbols"):
            evaluate_custom_portfolio(
                {"BTCUSDT": 0.5, "FAKETOKEN": 0.5}, storage=mock_storage
            )

    def test_missing_data_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = FileNotFoundError("not found")
        with pytest.raises(EvaluateError, match="not found"):
            evaluate_custom_portfolio(
                {"BTCUSDT": 1.0}, storage=storage
            )

    def test_equal_weight_portfolio(self, mock_storage):
        w = 1.0 / 3
        result = evaluate_custom_portfolio(
            {"BTCUSDT": w, "ETHUSDT": w, "SOLUSDT": w},
            storage=mock_storage,
        )
        # Expected: (0.15 + 0.20 + 0.25) / 3 = 0.20
        assert result["expected_return"] == pytest.approx(0.20, abs=1e-2)
