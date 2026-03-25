"""Tests for portfolio rebalancing alerts."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.rebalance import RebalanceError, compute_rebalance_alerts


@pytest.fixture()
def mock_storage():
    """Mock storage with optimal portfolio."""
    storage = MagicMock()
    storage.load_output.return_value = {
        "weights": {"BTCUSDT": 0.50, "ETHUSDT": 0.30, "SOLUSDT": 0.20},
    }
    return storage


class TestRebalanceAlerts:
    """Tests for compute_rebalance_alerts."""

    def test_no_drift_when_current_equals_target(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={"BTCUSDT": 0.50, "ETHUSDT": 0.30, "SOLUSDT": 0.20},
            storage=mock_storage,
            save=False,
        )
        assert result["summary"]["n_alerts"] == 0
        assert result["summary"]["needs_rebalance"] is False

    def test_no_drift_when_current_is_none(self, mock_storage):
        result = compute_rebalance_alerts(storage=mock_storage, save=False)
        assert result["summary"]["n_alerts"] == 0

    def test_drift_above_threshold_triggers_alert(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={"BTCUSDT": 0.60, "ETHUSDT": 0.25, "SOLUSDT": 0.15},
            drift_threshold=0.05,
            storage=mock_storage,
            save=False,
        )
        assert result["summary"]["n_alerts"] == 2  # BTC +10%, ETH -5%
        assert result["summary"]["needs_rebalance"] is True

    def test_drift_below_threshold_no_alert(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={"BTCUSDT": 0.52, "ETHUSDT": 0.29, "SOLUSDT": 0.19},
            drift_threshold=0.05,
            storage=mock_storage,
            save=False,
        )
        assert result["summary"]["n_alerts"] == 0

    def test_sell_action_when_overweight(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={"BTCUSDT": 0.70, "ETHUSDT": 0.20, "SOLUSDT": 0.10},
            drift_threshold=0.05,
            storage=mock_storage,
            save=False,
        )
        btc_alert = next(a for a in result["alerts"] if a["symbol"] == "BTCUSDT")
        assert btc_alert["action"] == "SELL"
        assert btc_alert["drift"] > 0

    def test_buy_action_when_underweight(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={"BTCUSDT": 0.70, "ETHUSDT": 0.20, "SOLUSDT": 0.10},
            drift_threshold=0.05,
            storage=mock_storage,
            save=False,
        )
        eth_alert = next(a for a in result["alerts"] if a["symbol"] == "ETHUSDT")
        assert eth_alert["action"] == "BUY"

    def test_trade_amounts_reflect_portfolio_value(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={"BTCUSDT": 0.60, "ETHUSDT": 0.25, "SOLUSDT": 0.15},
            portfolio_value=100000.0,
            drift_threshold=0.05,
            storage=mock_storage,
            save=False,
        )
        btc_trade = next(t for t in result["trades"] if t["symbol"] == "BTCUSDT")
        assert btc_trade["amount_usd"] == pytest.approx(10000.0, abs=1)  # 10% * 100k

    def test_new_symbol_in_target_generates_buy(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={"BTCUSDT": 0.50, "ETHUSDT": 0.30},
            drift_threshold=0.05,
            storage=mock_storage,
            save=False,
        )
        sol_alert = next(a for a in result["alerts"] if a["symbol"] == "SOLUSDT")
        assert sol_alert["action"] == "BUY"
        assert sol_alert["current_weight"] == 0.0

    def test_extra_symbol_in_current_generates_sell(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={
                "BTCUSDT": 0.40, "ETHUSDT": 0.25, "SOLUSDT": 0.15, "ADAUSDT": 0.20,
            },
            drift_threshold=0.05,
            storage=mock_storage,
            save=False,
        )
        ada_alert = next(a for a in result["alerts"] if a["symbol"] == "ADAUSDT")
        assert ada_alert["action"] == "SELL"
        assert ada_alert["target_weight"] == 0.0

    def test_summary_total_drift(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={"BTCUSDT": 0.60, "ETHUSDT": 0.25, "SOLUSDT": 0.15},
            drift_threshold=0.01,
            storage=mock_storage,
            save=False,
        )
        assert result["summary"]["total_drift"] == pytest.approx(0.20, abs=1e-4)

    def test_save_to_storage(self, mock_storage):
        compute_rebalance_alerts(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        assert mock_storage.save_output.call_args[0][1] == "rebalance_alerts"

    def test_missing_optimal_portfolio(self):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(RebalanceError, match="not found"):
            compute_rebalance_alerts(storage=storage)

    def test_empty_optimal_weights(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {}}
        with pytest.raises(RebalanceError, match="no weights"):
            compute_rebalance_alerts(storage=storage)

    def test_invalid_threshold_negative(self, mock_storage):
        with pytest.raises(RebalanceError, match="between 0 and 1"):
            compute_rebalance_alerts(drift_threshold=-0.1, storage=mock_storage)

    def test_invalid_threshold_above_one(self, mock_storage):
        with pytest.raises(RebalanceError, match="between 0 and 1"):
            compute_rebalance_alerts(drift_threshold=1.5, storage=mock_storage)

    def test_trad_portfolio_key(self):
        storage = MagicMock()
        storage.load_output.return_value = {
            "weights": {"SPY": 0.6, "GLD": 0.4},
        }
        result = compute_rebalance_alerts(
            portfolio_key="weights_trad",
            storage=storage,
            save=False,
        )
        assert result["portfolio_key"] == "weights_trad"
        storage.load_output.assert_called_with("weights_trad")

    def test_drift_pct_field(self, mock_storage):
        result = compute_rebalance_alerts(
            current_weights={"BTCUSDT": 0.60, "ETHUSDT": 0.25, "SOLUSDT": 0.15},
            drift_threshold=0.05,
            storage=mock_storage,
            save=False,
        )
        btc_alert = next(a for a in result["alerts"] if a["symbol"] == "BTCUSDT")
        assert btc_alert["drift_pct"] == pytest.approx(10.0, abs=0.1)
