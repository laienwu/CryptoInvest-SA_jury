"""Tests for portfolio decay analysis module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.decay import (
    DecayError,
    analyze_decay,
    compute_max_deviation,
    compute_tracking_error,
    optimal_rebalance_frequency,
    simulate_weight_drift,
)


class TestSimulateWeightDrift:
    """Tests for simulate_weight_drift."""

    def test_initial_weights_match_target(self):
        target = [0.5, 0.3, 0.2]
        returns = [[0.01, -0.02, 0.03]]
        result = simulate_weight_drift(target, returns)
        assert result[0] == target

    def test_weights_change_with_returns(self):
        target = [0.5, 0.5]
        returns = [[0.10, -0.05]]
        result = simulate_weight_drift(target, returns)
        # After: values = [0.55, 0.475], total = 1.025
        assert result[1][0] > 0.5  # BTC gained, weight should increase
        assert result[1][1] < 0.5  # ETH lost, weight should decrease

    def test_zero_returns_no_drift(self):
        target = [0.4, 0.3, 0.3]
        returns = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        result = simulate_weight_drift(target, returns)
        for row in result:
            for i, w in enumerate(row):
                assert w == pytest.approx(target[i], abs=1e-10)

    def test_weights_sum_to_one_each_period(self):
        target = [0.5, 0.3, 0.2]
        returns = [[0.05, -0.03, 0.02], [0.01, 0.04, -0.01], [-0.02, 0.01, 0.03]]
        result = simulate_weight_drift(target, returns)
        for row in result:
            assert sum(row) == pytest.approx(1.0, abs=1e-10)

    def test_result_length(self):
        target = [0.6, 0.4]
        returns = [[0.01, 0.02], [0.03, -0.01], [-0.01, 0.01]]
        result = simulate_weight_drift(target, returns)
        assert len(result) == 4  # T+1 = 3+1

    def test_empty_weights(self):
        result = simulate_weight_drift([], [[0.01]])
        assert result == []

    def test_empty_returns(self):
        target = [0.5, 0.5]
        result = simulate_weight_drift(target, [])
        assert len(result) == 1
        assert result[0] == target


class TestComputeTrackingError:
    """Tests for compute_tracking_error."""

    def test_zero_at_start(self):
        target = [0.5, 0.5]
        drifted = simulate_weight_drift(target, [[0.10, -0.05]])
        errors = compute_tracking_error(drifted, target)
        assert errors[0] == pytest.approx(0.0, abs=1e-8)

    def test_increases_over_time(self):
        target = [0.5, 0.5]
        returns = [[0.10, -0.05]] * 5
        drifted = simulate_weight_drift(target, returns)
        errors = compute_tracking_error(drifted, target)
        # Error should generally increase with persistent divergent returns
        assert errors[-1] > errors[0]

    def test_zero_drift_returns_zero(self):
        target = [0.4, 0.6]
        drifted = [target, target, target]
        errors = compute_tracking_error(drifted, target)
        for e in errors:
            assert e == pytest.approx(0.0, abs=1e-8)

    def test_known_value(self):
        target = [0.5, 0.5]
        drifted = [[0.5, 0.5], [0.6, 0.4]]
        errors = compute_tracking_error(drifted, target)
        # sqrt((0.1)^2 + (-0.1)^2) = sqrt(0.02) ~ 0.1414
        import math
        assert errors[1] == pytest.approx(math.sqrt(0.02), abs=1e-6)


class TestComputeMaxDeviation:
    """Tests for compute_max_deviation."""

    def test_zero_at_start(self):
        target = [0.5, 0.5]
        drifted = simulate_weight_drift(target, [[0.10, -0.05]])
        devs = compute_max_deviation(drifted, target)
        assert devs[0] == pytest.approx(0.0, abs=1e-8)

    def test_increases_with_drift(self):
        target = [0.5, 0.5]
        returns = [[0.10, -0.05]] * 5
        drifted = simulate_weight_drift(target, returns)
        devs = compute_max_deviation(drifted, target)
        assert devs[-1] > devs[0]

    def test_known_value(self):
        target = [0.5, 0.5]
        drifted = [[0.5, 0.5], [0.7, 0.3]]
        devs = compute_max_deviation(drifted, target)
        assert devs[1] == pytest.approx(0.2, abs=1e-6)

    def test_symmetric_deviation(self):
        target = [0.5, 0.5]
        drifted = [[0.5, 0.5], [0.6, 0.4]]
        devs = compute_max_deviation(drifted, target)
        # max(|0.1|, |-0.1|) = 0.1
        assert devs[1] == pytest.approx(0.1, abs=1e-6)


class TestOptimalRebalanceFrequency:
    """Tests for optimal_rebalance_frequency."""

    def test_basic(self):
        target = [0.5, 0.5]
        returns = [[0.10, -0.05]] * 20
        result = optimal_rebalance_frequency(target, returns, 0.05)
        assert "periods_to_threshold" in result
        assert "threshold" in result
        assert "max_drift_at_threshold" in result
        assert result["periods_to_threshold"] < 20

    def test_threshold_never_hit(self):
        target = [0.5, 0.5]
        returns = [[0.001, 0.001]] * 5  # Very small, nearly equal returns
        result = optimal_rebalance_frequency(target, returns, 0.50)
        assert result["periods_to_threshold"] == 5  # n_periods

    def test_immediate_breach(self):
        target = [0.5, 0.5]
        # Huge divergent return causes immediate breach
        returns = [[0.50, -0.40]]
        result = optimal_rebalance_frequency(target, returns, 0.01)
        assert result["periods_to_threshold"] == 1

    def test_threshold_value_preserved(self):
        target = [0.5, 0.5]
        returns = [[0.10, -0.05]] * 10
        threshold = 0.03
        result = optimal_rebalance_frequency(target, returns, threshold)
        assert result["threshold"] == threshold


class TestAnalyzeDecay:
    """Tests for analyze_decay."""

    @pytest.fixture()
    def mock_storage(self):
        storage = MagicMock()
        storage.load_output.return_value = {
            "weights": {
                "BTCUSDT": 0.5,
                "ETHUSDT": 0.3,
                "SOLUSDT": 0.2,
            },
        }
        storage.load_processed.return_value = {
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "per_asset": {
                "BTCUSDT": [0.01, -0.02, 0.03, 0.01, -0.01],
                "ETHUSDT": [-0.01, 0.03, -0.02, 0.02, 0.01],
                "SOLUSDT": [0.02, 0.01, 0.01, -0.03, 0.02],
            },
        }
        return storage

    def test_basic_output_keys(self, mock_storage):
        result = analyze_decay(storage=mock_storage, save=False)
        assert "target_weights" in result
        assert "drift_summary" in result
        assert "optimal_rebalance" in result
        assert "n_assets" in result
        assert "n_periods" in result
        assert "method" in result
        assert result["method"] == "decay_analysis"

    def test_n_assets(self, mock_storage):
        result = analyze_decay(storage=mock_storage, save=False)
        assert result["n_assets"] == 3

    def test_n_periods(self, mock_storage):
        result = analyze_decay(storage=mock_storage, save=False)
        assert result["n_periods"] == 5

    def test_saves_to_storage(self, mock_storage):
        analyze_decay(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        assert mock_storage.save_output.call_args[0][1] == "decay_analysis"

    def test_no_save(self, mock_storage):
        analyze_decay(storage=mock_storage, save=False)
        mock_storage.save_output.assert_not_called()

    def test_missing_weights_raises(self):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(DecayError, match="weights not found"):
            analyze_decay(storage=storage)

    def test_missing_returns_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {"BTCUSDT": 1.0}}
        storage.load_processed.side_effect = FileNotFoundError("not found")
        with pytest.raises(DecayError, match="Returns data not found"):
            analyze_decay(storage=storage)

    def test_empty_returns_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {"BTCUSDT": 1.0}}
        storage.load_processed.return_value = {"symbols": [], "per_asset": {}}
        with pytest.raises(DecayError, match="empty"):
            analyze_decay(storage=storage)

    def test_drift_summary_structure(self, mock_storage):
        result = analyze_decay(storage=mock_storage, save=False)
        summary = result["drift_summary"]
        assert len(summary) == 6  # T+1 = 5+1
        for entry in summary:
            assert "period" in entry
            assert "tracking_error" in entry
            assert "max_deviation" in entry

    def test_drift_summary_starts_at_zero(self, mock_storage):
        result = analyze_decay(storage=mock_storage, save=False)
        first = result["drift_summary"][0]
        assert first["tracking_error"] == pytest.approx(0.0, abs=1e-8)
        assert first["max_deviation"] == pytest.approx(0.0, abs=1e-8)

    def test_target_weights_sum_to_one(self, mock_storage):
        result = analyze_decay(storage=mock_storage, save=False)
        total = sum(result["target_weights"].values())
        assert total == pytest.approx(1.0, abs=1e-6)


class TestDecayError:
    """Tests for DecayError exception."""

    def test_message(self):
        err = DecayError("something failed", operation="load")
        assert str(err) == "something failed"
        assert err.message == "something failed"

    def test_operation(self):
        err = DecayError("bad data", operation="validate")
        assert err.operation == "validate"

    def test_default_operation(self):
        err = DecayError("oops")
        assert err.operation == "decay"
