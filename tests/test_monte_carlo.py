"""
Tests for Monte Carlo simulation module.

Tests:
- Output shape (percentiles, final_values)
- VaR/CVaR are negative or reasonable
- Config is preserved
- Error handling for missing data
"""

from unittest.mock import MagicMock

import pytest

from src.pipeline.monte_carlo import MonteCarloError, run_monte_carlo


def _mock_storage() -> MagicMock:
    """Create a mock storage with valid weights, mean_returns, covariance."""
    storage = MagicMock()

    storage.load_output.return_value = {
        "weights": {"A": 0.6, "B": 0.4},
    }
    storage.load_processed.side_effect = lambda name: {
        "mean_returns": {
            "mean_returns": {"A": 0.0005, "B": 0.0003},
        },
        "covariance": {
            "symbols": ["A", "B"],
            "matrix": [
                [0.0004, 0.0001],
                [0.0001, 0.0003],
            ],
        },
    }[name]

    return storage


class TestRunMonteCarlo:
    def test_output_has_required_keys(self):
        storage = _mock_storage()
        result = run_monte_carlo(n_simulations=100, n_days=30, storage=storage, save=False)

        assert "percentiles" in result
        assert "final_values" in result
        assert "var_95" in result
        assert "cvar_95" in result
        assert "config" in result
        assert "symbols" in result

    def test_percentiles_have_correct_keys(self):
        storage = _mock_storage()
        result = run_monte_carlo(n_simulations=100, n_days=30, storage=storage, save=False)

        for key in ["p5", "p25", "p50", "p75", "p95"]:
            assert key in result["percentiles"]
            assert len(result["percentiles"][key]) == 30

    def test_final_values_count_matches_simulations(self):
        storage = _mock_storage()
        result = run_monte_carlo(n_simulations=50, n_days=20, storage=storage, save=False)

        assert len(result["final_values"]) == 50

    def test_config_preserved(self):
        storage = _mock_storage()
        result = run_monte_carlo(n_simulations=200, n_days=60, storage=storage, save=False)

        assert result["config"]["n_simulations"] == 200
        assert result["config"]["n_days"] == 60

    def test_var_and_cvar_are_floats(self):
        storage = _mock_storage()
        result = run_monte_carlo(n_simulations=100, n_days=30, storage=storage, save=False)

        assert isinstance(result["var_95"], float)
        assert isinstance(result["cvar_95"], float)

    def test_cvar_worse_than_var(self):
        storage = _mock_storage()
        result = run_monte_carlo(n_simulations=500, n_days=60, storage=storage, save=False)

        # CVaR (expected shortfall) should be <= VaR
        assert result["cvar_95"] <= result["var_95"]

    def test_percentile_ordering(self):
        storage = _mock_storage()
        result = run_monte_carlo(n_simulations=200, n_days=30, storage=storage, save=False)

        p = result["percentiles"]
        # At each time step, p5 <= p25 <= p50 <= p75 <= p95
        for i in range(30):
            assert p["p5"][i] <= p["p25"][i] <= p["p50"][i] <= p["p75"][i] <= p["p95"][i]

    def test_saves_to_storage(self):
        storage = _mock_storage()
        run_monte_carlo(n_simulations=50, n_days=10, storage=storage, save=True)

        storage.save_output.assert_called_once()
        call_args = storage.save_output.call_args
        assert call_args[0][1] == "monte_carlo"

    def test_missing_weights_raises_error(self):
        storage = _mock_storage()
        storage.load_output.side_effect = FileNotFoundError("no weights")

        with pytest.raises(MonteCarloError, match="Cannot load weights"):
            run_monte_carlo(storage=storage, save=False)

    def test_missing_covariance_raises_error(self):
        storage = _mock_storage()

        def side_effect(name: str):
            if name == "covariance":
                raise FileNotFoundError("no cov")
            return {"mean_returns": {"A": 0.0005, "B": 0.0003}}

        storage.load_processed.side_effect = side_effect

        with pytest.raises(MonteCarloError, match="Cannot load covariance"):
            run_monte_carlo(storage=storage, save=False)

    def test_symbols_match_weights(self):
        storage = _mock_storage()
        result = run_monte_carlo(n_simulations=50, n_days=10, storage=storage, save=False)

        assert result["symbols"] == ["A", "B"]
