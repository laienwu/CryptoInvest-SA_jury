"""Tests for portfolio stress testing module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.stress_test import (
    StressTestError,
    list_scenarios,
    run_stress_test,
)


@pytest.fixture()
def mock_storage():
    """Mock storage with crypto + trad portfolio."""
    storage = MagicMock()
    storage.load_output.return_value = {
        "weights": {
            "BTCUSDT": 0.40,
            "ETHUSDT": 0.20,
            "SOLUSDT": 0.10,
            "SPY": 0.15,
            "GLD": 0.10,
            "TLT": 0.05,
        },
        "expected_return": 0.15,
        "volatility": 0.30,
    }
    return storage


class TestRunStressTest:
    """Tests for run_stress_test."""

    def test_crypto_crash_scenario(self, mock_storage):
        result = run_stress_test(
            scenario_name="crypto_crash", storage=mock_storage, save=False
        )
        assert result["scenario"]["name"] == "Crypto Crash"
        assert result["portfolio_impact"]["total_return_impact"] < 0

    def test_volatility_spike_scenario(self, mock_storage):
        result = run_stress_test(
            scenario_name="volatility_spike", storage=mock_storage, save=False
        )
        assert result["portfolio_impact"]["stressed_volatility"] > result["portfolio_impact"]["original_volatility"]

    def test_flight_to_safety_scenario(self, mock_storage):
        result = run_stress_test(
            scenario_name="flight_to_safety", storage=mock_storage, save=False
        )
        # GLD and TLT should have positive impact
        gld = next(a for a in result["asset_impacts"] if a["symbol"] == "GLD")
        assert gld["shock"] > 0

    def test_btc_halving_rally(self, mock_storage):
        result = run_stress_test(
            scenario_name="btc_halving_rally", storage=mock_storage, save=False
        )
        btc = next(a for a in result["asset_impacts"] if a["symbol"] == "BTCUSDT")
        assert btc["shock"] == 0.50
        assert result["portfolio_impact"]["total_return_impact"] > 0

    def test_black_swan_scenario(self, mock_storage):
        result = run_stress_test(
            scenario_name="black_swan", storage=mock_storage, save=False
        )
        assert result["portfolio_impact"]["total_return_impact"] == pytest.approx(-0.40, abs=0.01)

    def test_custom_shocks(self, mock_storage):
        result = run_stress_test(
            custom_shocks={"BTCUSDT": -0.50, "ETHUSDT": -0.30},
            storage=mock_storage,
            save=False,
        )
        assert result["scenario"]["type"] == "custom"
        btc = next(a for a in result["asset_impacts"] if a["symbol"] == "BTCUSDT")
        assert btc["impact"] == pytest.approx(-0.20, abs=1e-4)  # 0.40 * -0.50

    def test_output_keys(self, mock_storage):
        result = run_stress_test(
            scenario_name="crypto_crash", storage=mock_storage, save=False
        )
        assert "scenario" in result
        assert "asset_impacts" in result
        assert "portfolio_impact" in result
        assert "worst_hit" in result
        assert "best_performer" in result

    def test_asset_impacts_sorted_worst_first(self, mock_storage):
        result = run_stress_test(
            scenario_name="crypto_crash", storage=mock_storage, save=False
        )
        impacts = [a["impact"] for a in result["asset_impacts"]]
        assert impacts == sorted(impacts)

    def test_n_assets(self, mock_storage):
        result = run_stress_test(
            scenario_name="crypto_crash", storage=mock_storage, save=False
        )
        assert result["n_assets"] == 6

    def test_stressed_weight_computed(self, mock_storage):
        result = run_stress_test(
            scenario_name="black_swan", storage=mock_storage, save=False
        )
        btc = next(a for a in result["asset_impacts"] if a["symbol"] == "BTCUSDT")
        assert btc["stressed_weight"] == pytest.approx(0.40 * 0.60, abs=1e-4)

    def test_save_to_storage(self, mock_storage):
        run_stress_test(
            scenario_name="crypto_crash", storage=mock_storage, save=True
        )
        mock_storage.save_output.assert_called_once()
        assert mock_storage.save_output.call_args[0][0] == "stress_test"

    def test_unknown_scenario_raises(self, mock_storage):
        with pytest.raises(StressTestError, match="Unknown scenario"):
            run_stress_test(scenario_name="nonexistent", storage=mock_storage)

    def test_no_scenario_no_shocks_raises(self, mock_storage):
        with pytest.raises(StressTestError, match="Either scenario_name"):
            run_stress_test(storage=mock_storage)

    def test_missing_portfolio_raises(self):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(StressTestError, match="not found"):
            run_stress_test(scenario_name="crypto_crash", storage=storage)

    def test_empty_weights_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {}}
        with pytest.raises(StressTestError, match="no weights"):
            run_stress_test(scenario_name="crypto_crash", storage=storage)

    def test_var_1pct_computed(self, mock_storage):
        result = run_stress_test(
            scenario_name="crypto_crash", storage=mock_storage, save=False
        )
        assert "value_at_risk_1pct" in result["portfolio_impact"]


class TestListScenarios:
    """Tests for list_scenarios."""

    def test_returns_list(self):
        scenarios = list_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) == 5

    def test_scenario_fields(self):
        scenarios = list_scenarios()
        for s in scenarios:
            assert "id" in s
            assert "name" in s
            assert "description" in s

    def test_known_scenarios_present(self):
        ids = {s["id"] for s in list_scenarios()}
        assert "crypto_crash" in ids
        assert "black_swan" in ids
        assert "flight_to_safety" in ids
