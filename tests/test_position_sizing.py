"""Tests for position sizing module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.position_sizing import (
    PositionSizingError,
    analyze_position_sizing,
    compute_position_sizes,
    fixed_fractional,
    half_kelly,
    kelly_fraction,
    volatility_target_weight,
)


class TestKellyFraction:
    def test_positive_edge(self):
        # 60% win rate, 1:1 payoff → f* = (0.6*1 - 0.4)/1 = 0.2
        assert kelly_fraction(0.6, 1.0, 1.0) == pytest.approx(0.2, abs=1e-4)

    def test_no_edge(self):
        # 50% win rate, 1:1 payoff → f* = 0
        assert kelly_fraction(0.5, 1.0, 1.0) == pytest.approx(0.0, abs=1e-4)

    def test_high_payoff(self):
        # 50% win rate, 2:1 payoff → f* = (0.5*2 - 0.5)/2 = 0.25
        assert kelly_fraction(0.5, 2.0, 1.0) == pytest.approx(0.25, abs=1e-4)

    def test_clamped_at_zero(self):
        # Negative edge
        assert kelly_fraction(0.3, 1.0, 1.0) == 0.0

    def test_zero_loss(self):
        assert kelly_fraction(0.6, 1.0, 0.0) == 0.0

    def test_zero_win_rate(self):
        assert kelly_fraction(0.0, 1.0, 1.0) == 0.0


class TestHalfKelly:
    def test_half_of_full(self):
        full = kelly_fraction(0.6, 1.0, 1.0)
        assert half_kelly(0.6, 1.0, 1.0) == pytest.approx(full / 2, abs=1e-6)


class TestFixedFractional:
    def test_basic(self):
        # $10000, risk 2%, stop loss 5% → position = $4000
        result = fixed_fractional(10000, 0.02, 0.05)
        assert result == pytest.approx(4000.0, abs=0.01)

    def test_zero_stop(self):
        assert fixed_fractional(10000, 0.02, 0.0) == 0.0

    def test_zero_risk(self):
        assert fixed_fractional(10000, 0.0, 0.05) == 0.0


class TestVolatilityTargetWeight:
    def test_lower_vol_increases_weight(self):
        # Asset vol 10%, target 20% → 2x weight
        result = volatility_target_weight(0.10, 0.20, 0.5)
        assert result == pytest.approx(1.0, abs=1e-4)

    def test_higher_vol_decreases_weight(self):
        # Asset vol 40%, target 20% → 0.5x weight
        result = volatility_target_weight(0.40, 0.20, 0.5)
        assert result == pytest.approx(0.25, abs=1e-4)

    def test_zero_vol(self):
        assert volatility_target_weight(0.0, 0.20, 0.5) == 0.0


class TestComputePositionSizes:
    def test_empty_weights(self):
        result = compute_position_sizes({})
        assert result["positions"] == []
        assert result["n_assets"] == 0

    def test_weight_method(self):
        result = compute_position_sizes(
            {"BTCUSDT": 0.6, "ETHUSDT": 0.4},
            portfolio_value=10000,
            method="weight",
        )
        amounts = {p["symbol"]: p["amount_usd"] for p in result["positions"]}
        assert amounts["BTCUSDT"] == pytest.approx(6000, abs=0.01)
        assert amounts["ETHUSDT"] == pytest.approx(4000, abs=0.01)

    def test_total_allocated(self):
        result = compute_position_sizes(
            {"BTCUSDT": 0.5, "ETHUSDT": 0.5},
            portfolio_value=10000,
            method="weight",
        )
        assert result["total_allocated"] == pytest.approx(10000, abs=0.01)

    def test_vol_target_method(self):
        result = compute_position_sizes(
            {"BTCUSDT": 0.5, "ETHUSDT": 0.5},
            portfolio_value=10000,
            volatilities={"BTCUSDT": 0.30, "ETHUSDT": 0.15},
            target_volatility=0.15,
            method="vol_target",
        )
        # BTC: higher vol → lower adjusted weight
        positions = {p["symbol"]: p for p in result["positions"]}
        assert positions["BTCUSDT"]["adjusted_weight"] < positions["ETHUSDT"]["adjusted_weight"]

    def test_sorted_by_amount(self):
        result = compute_position_sizes(
            {"A": 0.1, "B": 0.3, "C": 0.6},
            portfolio_value=10000,
            method="weight",
        )
        amounts = [p["amount_usd"] for p in result["positions"]]
        assert amounts == sorted(amounts, reverse=True)

    def test_output_keys(self):
        result = compute_position_sizes(
            {"BTCUSDT": 1.0}, portfolio_value=10000
        )
        p = result["positions"][0]
        assert "symbol" in p
        assert "original_weight" in p
        assert "adjusted_weight" in p
        assert "amount_usd" in p


class TestAnalyzePositionSizing:
    @pytest.fixture()
    def mock_storage(self):
        storage = MagicMock()
        storage.load_output.return_value = {
            "weights": {"BTCUSDT": 0.6, "ETHUSDT": 0.4},
        }
        storage.load_processed.return_value = {
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "values": [0.30, 0.20],
        }
        return storage

    def test_output_keys(self, mock_storage):
        result = analyze_position_sizing(storage=mock_storage, save=False)
        assert "positions" in result
        assert "total_allocated" in result
        assert "method" in result

    def test_save_to_storage(self, mock_storage):
        analyze_position_sizing(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()

    def test_missing_portfolio_raises(self):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(PositionSizingError, match="not found"):
            analyze_position_sizing(storage=storage)

    def test_empty_weights_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {}}
        with pytest.raises(PositionSizingError, match="no weights"):
            analyze_position_sizing(storage=storage)
