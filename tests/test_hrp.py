"""Tests for Hierarchical Risk Parity (HRP) allocation module."""

import math
from unittest.mock import MagicMock

import pytest

from src.pipeline.hrp import (
    HRPError,
    _correlation_to_distance,
    _quasi_diagonalize,
    _recursive_bisection,
    _single_linkage_cluster,
    analyze_hrp,
    compute_hrp_weights,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COV_3x3 = [
    [0.04, 0.01, 0.005],
    [0.01, 0.06, 0.01],
    [0.005, 0.01, 0.09],
]

CORR_3x3 = [
    [1.0, 0.204, 0.083],
    [0.204, 1.0, 0.136],
    [0.083, 0.136, 1.0],
]


def _mock_storage():
    """Build a mock storage returning 3-asset processed data."""
    storage = MagicMock()
    storage.load_processed.side_effect = lambda name: {
        "returns": {
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "annualized_mean": [0.15, 0.20, 0.25],
        },
        "covariance": {"matrix": COV_3x3},
        "correlation": {"matrix": CORR_3x3},
    }[name]
    return storage


# ---------------------------------------------------------------------------
# TestCorrelationDistance
# ---------------------------------------------------------------------------


class TestCorrelationDistance:
    """Tests for _correlation_to_distance."""

    def test_perfect_correlation_gives_zero(self):
        corr = [[1.0, 1.0], [1.0, 1.0]]
        dist = _correlation_to_distance(corr)
        assert dist[0][1] == pytest.approx(0.0, abs=1e-10)
        assert dist[1][0] == pytest.approx(0.0, abs=1e-10)

    def test_zero_correlation_gives_sqrt_half(self):
        corr = [[1.0, 0.0], [0.0, 1.0]]
        dist = _correlation_to_distance(corr)
        expected = math.sqrt(0.5)
        assert dist[0][1] == pytest.approx(expected, abs=1e-10)

    def test_negative_correlation_gives_high_distance(self):
        corr = [[1.0, -1.0], [-1.0, 1.0]]
        dist = _correlation_to_distance(corr)
        assert dist[0][1] == pytest.approx(1.0, abs=1e-10)

    def test_diagonal_is_zero(self):
        corr = [[1.0, 0.5], [0.5, 1.0]]
        dist = _correlation_to_distance(corr)
        assert dist[0][0] == pytest.approx(0.0, abs=1e-10)
        assert dist[1][1] == pytest.approx(0.0, abs=1e-10)

    def test_symmetric(self):
        corr = [[1.0, 0.3], [0.3, 1.0]]
        dist = _correlation_to_distance(corr)
        assert dist[0][1] == pytest.approx(dist[1][0], abs=1e-10)


# ---------------------------------------------------------------------------
# TestSingleLinkage
# ---------------------------------------------------------------------------


class TestSingleLinkage:
    """Tests for _single_linkage_cluster."""

    def test_two_assets(self):
        dist = [[0.0, 0.5], [0.5, 0.0]]
        linkage = _single_linkage_cluster(dist)
        assert len(linkage) == 1
        a, b, d = linkage[0]
        assert {a, b} == {0, 1}
        assert d == pytest.approx(0.5)

    def test_three_assets(self):
        # Assets 0-1 closest, then merge with 2
        dist = [
            [0.0, 0.1, 0.9],
            [0.1, 0.0, 0.8],
            [0.9, 0.8, 0.0],
        ]
        linkage = _single_linkage_cluster(dist)
        assert len(linkage) == 2
        # First merge should be 0 and 1 (distance 0.1)
        a, b, d = linkage[0]
        assert {a, b} == {0, 1}
        assert d == pytest.approx(0.1)

    def test_identical_distances(self):
        dist = [
            [0.0, 0.5, 0.5],
            [0.5, 0.0, 0.5],
            [0.5, 0.5, 0.0],
        ]
        linkage = _single_linkage_cluster(dist)
        assert len(linkage) == 2
        # All distances equal — any merge is valid, just check structure
        assert linkage[0][2] == pytest.approx(0.5)

    def test_single_asset_returns_empty(self):
        linkage = _single_linkage_cluster([[0.0]])
        assert linkage == []

    def test_empty_returns_empty(self):
        linkage = _single_linkage_cluster([])
        assert linkage == []


# ---------------------------------------------------------------------------
# TestQuasiDiagonalize
# ---------------------------------------------------------------------------


class TestQuasiDiagonalize:
    """Tests for _quasi_diagonalize."""

    def test_two_assets(self):
        linkage = [(0, 1, 0.5)]
        order = _quasi_diagonalize(linkage, 2)
        assert set(order) == {0, 1}
        assert len(order) == 2

    def test_three_assets(self):
        linkage = [(0, 1, 0.1), (2, 2, 0.8)]  # cluster 2=original, 2+0=merge
        # Build proper linkage: first merge 0,1 -> cluster 3; then merge 2,3 -> cluster 4
        linkage = [(0, 1, 0.1), (2, 3, 0.8)]
        order = _quasi_diagonalize(linkage, 3)
        assert len(order) == 3
        assert set(order) == {0, 1, 2}

    def test_preserves_all_indices(self):
        # 4 assets
        linkage = [(0, 1, 0.1), (2, 3, 0.2), (4, 5, 0.5)]
        order = _quasi_diagonalize(linkage, 4)
        assert sorted(order) == [0, 1, 2, 3]

    def test_single_asset(self):
        order = _quasi_diagonalize([], 1)
        assert order == [0]

    def test_empty(self):
        order = _quasi_diagonalize([], 0)
        assert order == []


# ---------------------------------------------------------------------------
# TestRecursiveBisection
# ---------------------------------------------------------------------------


class TestRecursiveBisection:
    """Tests for _recursive_bisection."""

    def test_two_assets_equal_vol(self):
        cov = [[0.04, 0.0], [0.0, 0.04]]
        order = [0, 1]
        weights = _recursive_bisection(cov, order)
        assert weights[0] == pytest.approx(0.5, abs=0.01)
        assert weights[1] == pytest.approx(0.5, abs=0.01)

    def test_three_assets_weights_sum_to_one(self):
        weights = _recursive_bisection(COV_3x3, [0, 1, 2])
        assert sum(weights) == pytest.approx(1.0, abs=1e-6)

    def test_weights_sum_to_one(self):
        cov = [
            [0.01, 0.0, 0.0],
            [0.0, 0.04, 0.0],
            [0.0, 0.0, 0.16],
        ]
        weights = _recursive_bisection(cov, [0, 1, 2])
        assert sum(weights) == pytest.approx(1.0, abs=1e-6)

    def test_higher_var_lower_weight(self):
        cov = [
            [0.01, 0.0],
            [0.0, 0.16],
        ]
        weights = _recursive_bisection(cov, [0, 1])
        assert weights[0] > weights[1]

    def test_empty(self):
        assert _recursive_bisection([], []) == []


# ---------------------------------------------------------------------------
# TestComputeHRPWeights
# ---------------------------------------------------------------------------


class TestComputeHRPWeights:
    """Tests for compute_hrp_weights."""

    def test_basic(self):
        result = compute_hrp_weights(COV_3x3, CORR_3x3)
        assert sum(result["weights"]) == pytest.approx(1.0, abs=1e-4)
        assert result["n_assets"] == 3

    def test_single_asset(self):
        result = compute_hrp_weights([[0.04]], [[1.0]])
        assert result["weights"] == [1.0]
        assert result["order"] == [0]
        assert result["n_assets"] == 1

    def test_return_keys(self):
        result = compute_hrp_weights(COV_3x3, CORR_3x3)
        assert "weights" in result
        assert "order" in result
        assert "n_assets" in result

    def test_empty(self):
        result = compute_hrp_weights([], [])
        assert result["weights"] == []
        assert result["n_assets"] == 0

    def test_all_weights_positive(self):
        result = compute_hrp_weights(COV_3x3, CORR_3x3)
        assert all(w >= 0 for w in result["weights"])


# ---------------------------------------------------------------------------
# TestAnalyzeHRP
# ---------------------------------------------------------------------------


class TestAnalyzeHRP:
    """Tests for analyze_hrp."""

    def test_basic(self):
        storage = _mock_storage()
        result = analyze_hrp(storage=storage, save=False)
        assert "weights" in result
        assert "expected_return" in result
        assert "volatility" in result
        assert "sharpe_ratio" in result
        assert result["method"] == "hrp"

    def test_saves(self):
        storage = _mock_storage()
        analyze_hrp(storage=storage, save=True)
        storage.save_output.assert_called_once()
        args = storage.save_output.call_args
        assert args[0][1] == "hrp"

    def test_no_save(self):
        storage = _mock_storage()
        analyze_hrp(storage=storage, save=False)
        storage.save_output.assert_not_called()

    def test_missing_data_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = FileNotFoundError("not found")
        with pytest.raises(HRPError, match="not found"):
            analyze_hrp(storage=storage)

    def test_weights_sum_to_one(self):
        storage = _mock_storage()
        result = analyze_hrp(storage=storage, save=False)
        assert sum(result["weights"].values()) == pytest.approx(1.0, abs=1e-4)

    def test_weights_are_named(self):
        storage = _mock_storage()
        result = analyze_hrp(storage=storage, save=False)
        assert isinstance(result["weights"], dict)
        assert set(result["weights"].keys()) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def test_incomplete_data_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = lambda name: {
            "returns": {"symbols": [], "annualized_mean": []},
            "covariance": {"matrix": []},
            "correlation": {"matrix": []},
        }[name]
        with pytest.raises(HRPError, match="incomplete"):
            analyze_hrp(storage=storage)


# ---------------------------------------------------------------------------
# TestHRPError
# ---------------------------------------------------------------------------


class TestHRPError:
    """Tests for HRPError exception."""

    def test_message(self):
        err = HRPError("something failed")
        assert err.message == "something failed"
        assert str(err) == "something failed"

    def test_custom_operation(self):
        err = HRPError("bad data", operation="load")
        assert err.operation == "load"

    def test_default_operation(self):
        err = HRPError("oops")
        assert err.operation == "hrp"
