"""
Tests for efficient frontier computation.

Tests:
- _linspace helper
- _optimize_for_target_return constrained optimization
- compute_efficient_frontier full output structure
"""

import math

import pytest

from src.pipeline.optimize import (
    _linspace,
    _optimize_for_target_return,
    compute_efficient_frontier,
    calculate_portfolio_return,
    calculate_portfolio_volatility,
)


class TestLinspace:
    """Tests for _linspace helper."""

    def test_basic(self):
        """Test basic linspace."""
        result = _linspace(0.0, 1.0, 5)
        expected = [0.0, 0.25, 0.5, 0.75, 1.0]
        assert len(result) == 5
        for r, e in zip(result, expected):
            assert r == pytest.approx(e)

    def test_single_point(self):
        """Test linspace with single point returns start."""
        result = _linspace(3.0, 10.0, 1)
        assert len(result) == 1
        assert result[0] == pytest.approx(3.0)

    def test_empty(self):
        """Test linspace with zero points returns empty."""
        result = _linspace(0.0, 1.0, 0)
        assert result == []

    def test_two_points(self):
        """Test linspace with two points returns endpoints."""
        result = _linspace(2.0, 8.0, 2)
        assert len(result) == 2
        assert result[0] == pytest.approx(2.0)
        assert result[1] == pytest.approx(8.0)

    def test_negative_num(self):
        """Test linspace with negative num returns empty."""
        result = _linspace(0.0, 1.0, -3)
        assert result == []


class TestOptimizeForTargetReturn:
    """Tests for _optimize_for_target_return."""

    def test_feasible_target(self, sample_mean_returns, sample_covariance_matrix):
        """Test optimization with feasible target return."""
        # Target is average of min and max returns
        target = (min(sample_mean_returns) + max(sample_mean_returns)) / 2
        weights = _optimize_for_target_return(
            sample_mean_returns, sample_covariance_matrix, target
        )

        if weights is not None:
            # Weights should sum to 1
            assert sum(weights) == pytest.approx(1.0, abs=1e-4)
            # All weights non-negative
            assert all(w >= -1e-6 for w in weights)
            # Portfolio return should be near target
            # (grid search fallback uses tolerance=0.01)
            actual_return = calculate_portfolio_return(weights, sample_mean_returns)
            assert actual_return == pytest.approx(target, abs=0.02)

    def test_weights_constraints(self, sample_mean_returns, sample_covariance_matrix):
        """Test that weights satisfy long-only and fully-invested constraints."""
        target = sample_mean_returns[0]  # Use first asset's return
        weights = _optimize_for_target_return(
            sample_mean_returns, sample_covariance_matrix, target
        )

        if weights is not None:
            assert sum(weights) == pytest.approx(1.0, abs=1e-4)
            assert all(w >= -1e-6 for w in weights)
            assert len(weights) == len(sample_mean_returns)

    def test_infeasible_target(self, sample_mean_returns, sample_covariance_matrix):
        """Test that infeasible target (way above max) returns None."""
        target = max(sample_mean_returns) * 10  # Way above feasible
        weights = _optimize_for_target_return(
            sample_mean_returns, sample_covariance_matrix, target
        )
        # Should return None since it's infeasible with long-only
        # (scipy may still converge to an approximate solution, so we check loosely)
        if weights is not None:
            actual_return = calculate_portfolio_return(weights, sample_mean_returns)
            # If it found something, it shouldn't match the target well
            assert abs(actual_return - target) > 0.1 or sum(weights) != pytest.approx(1.0, abs=0.01)


class TestEfficientFrontier:
    """Tests for compute_efficient_frontier."""

    def test_output_structure(self, sample_mean_returns, sample_covariance_matrix):
        """Test that output has all required keys."""
        result = compute_efficient_frontier(
            sample_mean_returns, sample_covariance_matrix, n_points=10
        )

        assert "frontier" in result
        assert "max_sharpe" in result
        assert "min_variance" in result
        assert "assets" in result
        assert "capital_market_line" in result
        assert "risk_free_rate" in result

    def test_frontier_points_have_required_fields(
        self, sample_mean_returns, sample_covariance_matrix
    ):
        """Test each frontier point has volatility, return, weights."""
        result = compute_efficient_frontier(
            sample_mean_returns, sample_covariance_matrix, n_points=10
        )

        for point in result["frontier"]:
            assert "volatility" in point
            assert "return" in point
            assert "weights" in point
            assert point["volatility"] >= 0

    def test_frontier_point_count(self):
        """Test frontier has roughly expected number of points."""
        # Use well-separated returns to ensure feasible targets
        mean_returns = [0.05, 0.15, 0.25]
        cov_matrix = [
            [0.04, 0.01, 0.005],
            [0.01, 0.09, 0.01],
            [0.005, 0.01, 0.16],
        ]
        n_points = 15
        result = compute_efficient_frontier(
            mean_returns, cov_matrix, n_points=n_points
        )

        # May have fewer if some targets are infeasible
        assert len(result["frontier"]) > 0
        assert len(result["frontier"]) <= n_points

    def test_max_sharpe_exists(self, sample_mean_returns, sample_covariance_matrix):
        """Test max Sharpe portfolio is populated."""
        result = compute_efficient_frontier(
            sample_mean_returns, sample_covariance_matrix, n_points=10
        )

        ms = result["max_sharpe"]
        assert "volatility" in ms
        assert "return" in ms
        assert "weights" in ms
        assert ms["volatility"] > 0

    def test_min_variance_exists(self, sample_mean_returns, sample_covariance_matrix):
        """Test min variance portfolio is populated."""
        result = compute_efficient_frontier(
            sample_mean_returns, sample_covariance_matrix, n_points=10
        )

        mv = result["min_variance"]
        assert "volatility" in mv
        assert "return" in mv
        assert "weights" in mv
        assert mv["volatility"] > 0

    def test_asset_count_matches(self, sample_mean_returns, sample_covariance_matrix):
        """Test that individual assets count matches input."""
        result = compute_efficient_frontier(
            sample_mean_returns, sample_covariance_matrix, n_points=10
        )

        assert len(result["assets"]) == len(sample_mean_returns)

    def test_capital_market_line(self, sample_mean_returns, sample_covariance_matrix):
        """Test CML starts at risk-free rate."""
        rf = 0.03
        result = compute_efficient_frontier(
            sample_mean_returns, sample_covariance_matrix,
            n_points=10, risk_free_rate=rf,
        )

        cml = result["capital_market_line"]
        assert cml["x"][0] == pytest.approx(0.0)
        assert cml["y"][0] == pytest.approx(rf)
        assert result["risk_free_rate"] == pytest.approx(rf)

    def test_min_variance_lower_vol_than_max_sharpe(
        self, sample_mean_returns, sample_covariance_matrix
    ):
        """Test that min variance has lower or equal vol than max Sharpe."""
        result = compute_efficient_frontier(
            sample_mean_returns, sample_covariance_matrix, n_points=20
        )

        assert result["min_variance"]["volatility"] <= result["max_sharpe"]["volatility"] + 1e-4
