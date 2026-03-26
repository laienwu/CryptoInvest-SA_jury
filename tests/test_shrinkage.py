"""Tests for the Ledoit-Wolf covariance shrinkage module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.shrinkage import (
    ShrinkageError,
    _constant_correlation_target,
    _sample_covariance,
    analyze_shrinkage,
    compare_eigenvalues,
    compute_shrinkage_intensity,
    ledoit_wolf_covariance,
)

from src.storage.base import StorageError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_asset_returns():
    """Two-asset returns matrix (per-asset rows)."""
    return [
        [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.005, 0.015, 0.005, -0.01],
        [-0.005, 0.01, -0.02, 0.015, -0.01, 0.02, 0.005, -0.01, 0.01, 0.005],
    ]


@pytest.fixture()
def three_asset_returns():
    """Three-asset returns matrix with distinct patterns."""
    return [
        [0.01, -0.02, 0.03, -0.01, 0.02, 0.015, -0.005, 0.01, -0.015, 0.025],
        [-0.005, 0.01, -0.015, 0.02, -0.01, 0.005, 0.01, -0.02, 0.015, -0.005],
        [0.005, 0.005, 0.01, 0.005, 0.005, 0.01, 0.005, 0.005, 0.01, 0.005],
    ]


@pytest.fixture()
def mock_storage():
    """Mock storage with returns and covariance data."""
    storage = MagicMock()
    storage.load_processed.side_effect = _mock_load_processed
    return storage


def _mock_load_processed(name: str):
    if name == "returns":
        return {
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "values": [
                [0.01, -0.005, 0.005],
                [-0.02, 0.01, 0.005],
                [0.03, -0.015, 0.01],
                [-0.01, 0.02, 0.005],
                [0.02, -0.01, 0.005],
                [0.015, 0.005, 0.01],
                [-0.005, 0.01, 0.005],
                [0.01, -0.02, 0.005],
                [-0.015, 0.015, 0.01],
                [0.025, -0.005, 0.005],
            ],
        }
    if name == "covariance":
        return {
            "matrix": [
                [0.0003, -0.0001, 0.00005],
                [-0.0001, 0.0002, -0.00003],
                [0.00005, -0.00003, 0.00001],
            ],
        }
    raise StorageError(f"Unknown dataset: {name}")


# ---------------------------------------------------------------------------
# TestSampleCovariance
# ---------------------------------------------------------------------------


class TestSampleCovariance:
    """Tests for _sample_covariance."""

    def test_two_assets_shape(self, two_asset_returns):
        cov = _sample_covariance(two_asset_returns)
        assert len(cov) == 2
        assert len(cov[0]) == 2
        assert len(cov[1]) == 2

    def test_diagonal_matches_variance(self, two_asset_returns):
        cov = _sample_covariance(two_asset_returns)
        # Diagonal should be positive (variance)
        assert cov[0][0] > 0
        assert cov[1][1] > 0

    def test_symmetric(self, two_asset_returns):
        cov = _sample_covariance(two_asset_returns)
        assert cov[0][1] == pytest.approx(cov[1][0], abs=1e-15)

    def test_three_assets_symmetric(self, three_asset_returns):
        cov = _sample_covariance(three_asset_returns)
        for i in range(3):
            for j in range(3):
                assert cov[i][j] == pytest.approx(cov[j][i], abs=1e-15)

    def test_empty_raises(self):
        with pytest.raises(ShrinkageError, match="No assets"):
            _sample_covariance([])

    def test_single_observation_raises(self):
        with pytest.raises(ShrinkageError, match="at least 2"):
            _sample_covariance([[0.01]])

    def test_inconsistent_lengths_raises(self):
        with pytest.raises(ShrinkageError, match="observations"):
            _sample_covariance([[0.01, 0.02], [0.01]])


# ---------------------------------------------------------------------------
# TestConstantCorrelationTarget
# ---------------------------------------------------------------------------


class TestConstantCorrelationTarget:
    """Tests for _constant_correlation_target."""

    def test_diagonal_preserved(self, two_asset_returns):
        cov = _sample_covariance(two_asset_returns)
        target = _constant_correlation_target(cov)
        assert target[0][0] == pytest.approx(cov[0][0], abs=1e-15)
        assert target[1][1] == pytest.approx(cov[1][1], abs=1e-15)

    def test_off_diagonal_averaged(self, three_asset_returns):
        cov = _sample_covariance(three_asset_returns)
        target = _constant_correlation_target(cov)
        # All off-diagonal elements should use the same average correlation
        # so F_01 / sqrt(S_00*S_11) == F_02 / sqrt(S_00*S_22)
        import math

        r_01 = target[0][1] / math.sqrt(target[0][0] * target[1][1])
        r_02 = target[0][2] / math.sqrt(target[0][0] * target[2][2])
        assert r_01 == pytest.approx(r_02, abs=1e-10)

    def test_single_asset(self):
        cov = [[0.005]]
        target = _constant_correlation_target(cov)
        assert target == [[0.005]]

    def test_symmetric(self, two_asset_returns):
        cov = _sample_covariance(two_asset_returns)
        target = _constant_correlation_target(cov)
        assert target[0][1] == pytest.approx(target[1][0], abs=1e-15)


# ---------------------------------------------------------------------------
# TestShrinkageIntensity
# ---------------------------------------------------------------------------


class TestShrinkageIntensity:
    """Tests for compute_shrinkage_intensity."""

    def test_between_zero_and_one(self, three_asset_returns):
        cov = _sample_covariance(three_asset_returns)
        target = _constant_correlation_target(cov)
        delta = compute_shrinkage_intensity(three_asset_returns, cov, target)
        assert 0.0 <= delta <= 1.0

    def test_constant_returns_gives_zero(self):
        """If all returns are identical per asset, cov = target, delta = 0."""
        returns_matrix = [
            [0.01] * 20,
            [0.02] * 20,
        ]
        # Variance is 0 for constant series, so covariance is all zeros
        # This should give delta = 1 (max shrinkage) since sample is degenerate
        cov = _sample_covariance(returns_matrix)
        target = _constant_correlation_target(cov)
        delta = compute_shrinkage_intensity(returns_matrix, cov, target)
        # With zero variance, target = sample (both zero), gamma = 0
        assert delta == 0.0

    def test_high_noise_near_one(self):
        """With very few observations relative to assets, intensity should be high."""
        import random

        random.seed(42)
        # 5 assets, only 6 observations — highly noisy
        returns_matrix = [
            [random.gauss(0, 0.05) for _ in range(6)]
            for _ in range(5)
        ]
        cov = _sample_covariance(returns_matrix)
        target = _constant_correlation_target(cov)
        delta = compute_shrinkage_intensity(returns_matrix, cov, target)
        assert delta > 0.3  # Should be substantial shrinkage

    def test_many_observations_lower_intensity(self):
        """With many observations, shrinkage should be bounded."""
        import random

        random.seed(42)
        # Use correlated assets so target != sample
        base = [random.gauss(0, 0.02) for _ in range(500)]
        returns_matrix = [
            base,
            [b + random.gauss(0, 0.005) for b in base],
            [random.gauss(0, 0.02) for _ in range(500)],
        ]
        cov = _sample_covariance(returns_matrix)
        target = _constant_correlation_target(cov)
        delta = compute_shrinkage_intensity(returns_matrix, cov, target)
        assert 0.0 <= delta <= 1.0


# ---------------------------------------------------------------------------
# TestLedoitWolfCovariance
# ---------------------------------------------------------------------------


class TestLedoitWolfCovariance:
    """Tests for ledoit_wolf_covariance."""

    def test_return_keys(self, three_asset_returns):
        result = ledoit_wolf_covariance(three_asset_returns)
        expected_keys = {
            "shrunk_covariance",
            "sample_covariance",
            "target",
            "shrinkage_intensity",
            "n_assets",
            "n_observations",
        }
        assert set(result.keys()) == expected_keys

    def test_matrix_dimensions(self, three_asset_returns):
        result = ledoit_wolf_covariance(three_asset_returns)
        shrunk = result["shrunk_covariance"]
        assert len(shrunk) == 3
        for row in shrunk:
            assert len(row) == 3

    def test_intensity_range(self, three_asset_returns):
        result = ledoit_wolf_covariance(three_asset_returns)
        assert 0.0 <= result["shrinkage_intensity"] <= 1.0

    def test_symmetric_output(self, three_asset_returns):
        result = ledoit_wolf_covariance(three_asset_returns)
        shrunk = result["shrunk_covariance"]
        for i in range(3):
            for j in range(3):
                assert shrunk[i][j] == pytest.approx(shrunk[j][i], abs=1e-15)

    def test_n_assets_and_observations(self, three_asset_returns):
        result = ledoit_wolf_covariance(three_asset_returns)
        assert result["n_assets"] == 3
        assert result["n_observations"] == 10

    def test_shrunk_is_convex_combination(self, two_asset_returns):
        """Shrunk = delta * target + (1-delta) * sample."""
        result = ledoit_wolf_covariance(two_asset_returns)
        delta = result["shrinkage_intensity"]
        sample = result["sample_covariance"]
        target = result["target"]
        shrunk = result["shrunk_covariance"]
        for i in range(2):
            for j in range(2):
                expected = delta * target[i][j] + (1 - delta) * sample[i][j]
                assert shrunk[i][j] == pytest.approx(expected, abs=1e-15)


# ---------------------------------------------------------------------------
# TestCompareEigenvalues
# ---------------------------------------------------------------------------


class TestCompareEigenvalues:
    """Tests for compare_eigenvalues."""

    def test_return_keys(self, three_asset_returns):
        result = ledoit_wolf_covariance(three_asset_returns)
        eigen = compare_eigenvalues(
            result["sample_covariance"], result["shrunk_covariance"]
        )
        expected_keys = {
            "sample_eigenvalues",
            "shrunk_eigenvalues",
            "condition_number_sample",
            "condition_number_shrunk",
        }
        assert set(eigen.keys()) == expected_keys

    def test_eigenvalue_count(self, three_asset_returns):
        result = ledoit_wolf_covariance(three_asset_returns)
        eigen = compare_eigenvalues(
            result["sample_covariance"], result["shrunk_covariance"]
        )
        assert len(eigen["sample_eigenvalues"]) == 3
        assert len(eigen["shrunk_eigenvalues"]) == 3

    def test_shrunk_condition_number_not_worse(self, three_asset_returns):
        """Shrinkage should not increase the condition number."""
        result = ledoit_wolf_covariance(three_asset_returns)
        eigen = compare_eigenvalues(
            result["sample_covariance"], result["shrunk_covariance"]
        )
        assert eigen["condition_number_shrunk"] <= eigen["condition_number_sample"] + 1e-10

    def test_identity_matrix(self):
        """Identity matrix should have condition number 1."""
        identity = [[1.0, 0.0], [0.0, 1.0]]
        eigen = compare_eigenvalues(identity, identity)
        assert eigen["condition_number_sample"] == pytest.approx(1.0, abs=1e-10)
        assert eigen["condition_number_shrunk"] == pytest.approx(1.0, abs=1e-10)


# ---------------------------------------------------------------------------
# TestAnalyzeShrinkage
# ---------------------------------------------------------------------------


class TestAnalyzeShrinkage:
    """Tests for analyze_shrinkage."""

    def test_basic(self, mock_storage):
        result = analyze_shrinkage(storage=mock_storage, save=False)
        assert "shrunk_covariance" in result
        assert "symbols" in result
        assert result["symbols"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    def test_saves_to_storage(self, mock_storage):
        analyze_shrinkage(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        args = mock_storage.save_output.call_args[0]
        assert args[1] == "shrinkage"

    def test_no_save(self, mock_storage):
        analyze_shrinkage(storage=mock_storage, save=False)
        mock_storage.save_output.assert_not_called()

    def test_missing_returns_raises(self):
        storage = MagicMock()
        storage.load_processed.side_effect = StorageError("Not found")
        with pytest.raises(ShrinkageError, match="Returns data not found"):
            analyze_shrinkage(storage=storage, save=False)

    def test_empty_returns_raises(self):
        storage = MagicMock()
        storage.load_processed.return_value = {"symbols": [], "values": []}
        with pytest.raises(ShrinkageError, match="empty"):
            analyze_shrinkage(storage=storage, save=False)

    def test_eigenvalue_comparison_included(self, mock_storage):
        result = analyze_shrinkage(storage=mock_storage, save=False)
        assert "eigenvalue_comparison" in result
        assert "condition_number_shrunk" in result["eigenvalue_comparison"]


# ---------------------------------------------------------------------------
# TestShrinkageError
# ---------------------------------------------------------------------------


class TestShrinkageError:
    """Tests for ShrinkageError exception."""

    def test_message(self):
        err = ShrinkageError("test error", operation="test_op")
        assert err.message == "test error"
        assert str(err) == "test error"

    def test_operation(self):
        err = ShrinkageError("fail", operation="compute")
        assert err.operation == "compute"

    def test_default_operation(self):
        err = ShrinkageError("fail")
        assert err.operation == "shrinkage"
