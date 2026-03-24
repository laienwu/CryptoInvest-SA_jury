"""Tests for rolling correlation analysis."""

import pytest

from src.pipeline.transform import TransformError, compute_rolling_correlation


# 3 symbols, 10 periods of returns
RETURNS_3x10 = [
    [0.01, -0.02, 0.03, 0.01, -0.01, 0.02, 0.00, 0.01, -0.03, 0.02],
    [0.02, -0.01, 0.02, 0.00, -0.02, 0.03, 0.01, 0.00, -0.02, 0.01],
    [-0.01, 0.03, -0.02, 0.01, 0.02, -0.01, 0.00, 0.02, 0.01, -0.01],
]
SYMBOLS_3 = ["BTC", "ETH", "SOL"]


class TestComputeRollingCorrelation:
    """Tests for compute_rolling_correlation."""

    def test_output_keys(self):
        result = compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=5)
        assert "pairs" in result
        assert "window" in result
        assert "n_periods" in result
        assert "n_pairs" in result

    def test_n_pairs_for_3_symbols(self):
        result = compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=5)
        assert result["n_pairs"] == 3  # C(3,2) = 3

    def test_n_pairs_for_2_symbols(self):
        result = compute_rolling_correlation(
            RETURNS_3x10[:2], SYMBOLS_3[:2], window=5
        )
        assert result["n_pairs"] == 1

    def test_pair_names(self):
        result = compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=5)
        pair_names = {p["pair"] for p in result["pairs"]}
        assert pair_names == {"BTC/ETH", "BTC/SOL", "ETH/SOL"}

    def test_correlations_length_matches_periods(self):
        result = compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=5)
        for pair in result["pairs"]:
            assert len(pair["correlations"]) == 10

    def test_first_values_are_none(self):
        result = compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=5)
        pair = result["pairs"][0]
        # First 4 values (indices 0-3) should be None (window=5, first valid at index 4)
        for i in range(4):
            assert pair["correlations"][i] is None

    def test_values_after_window_are_floats(self):
        result = compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=5)
        pair = result["pairs"][0]
        for i in range(4, 10):
            assert isinstance(pair["correlations"][i], float)

    def test_correlations_in_range(self):
        result = compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=5)
        for pair in result["pairs"]:
            for val in pair["correlations"]:
                if val is not None:
                    assert -1.0 <= val <= 1.0

    def test_window_preserved(self):
        result = compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=7)
        assert result["window"] == 7

    def test_window_too_small_raises(self):
        with pytest.raises(TransformError, match="must be >= 2"):
            compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=1)

    def test_window_exceeds_periods_raises(self):
        with pytest.raises(TransformError, match="exceeds available periods"):
            compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=20)

    def test_minimum_window(self):
        result = compute_rolling_correlation(RETURNS_3x10, SYMBOLS_3, window=2)
        pair = result["pairs"][0]
        assert pair["correlations"][0] is None
        assert pair["correlations"][1] is not None

    def test_identical_series_correlation_is_one(self):
        identical = [
            [0.01, 0.02, 0.03, 0.04, 0.05],
            [0.01, 0.02, 0.03, 0.04, 0.05],
        ]
        result = compute_rolling_correlation(identical, ["A", "B"], window=3)
        pair = result["pairs"][0]
        for val in pair["correlations"]:
            if val is not None:
                assert val == pytest.approx(1.0, abs=1e-3)

    def test_opposite_series_correlation_is_negative_one(self):
        opposite = [
            [0.01, -0.01, 0.01, -0.01, 0.01],
            [-0.01, 0.01, -0.01, 0.01, -0.01],
        ]
        result = compute_rolling_correlation(opposite, ["A", "B"], window=3)
        pair = result["pairs"][0]
        for val in pair["correlations"]:
            if val is not None:
                assert val == pytest.approx(-1.0, abs=1e-3)
