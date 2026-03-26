"""Tests for the Black-Litterman portfolio optimization module."""

import pytest

from src.pipeline.black_litterman import (
    BlackLittermanError,
    analyze_black_litterman,
    compute_equilibrium_returns,
    compute_posterior_returns,
    create_view_matrix,
    optimize_black_litterman,
)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

def _cov_3x3():
    """3-asset covariance matrix."""
    return [
        [0.04, 0.006, 0.002],
        [0.006, 0.09, 0.004],
        [0.002, 0.004, 0.01],
    ]


def _cov_2x2():
    """2-asset covariance matrix."""
    return [
        [0.04, 0.01],
        [0.01, 0.09],
    ]


# ---------------------------------------------------------------------------
# TestComputeEquilibriumReturns
# ---------------------------------------------------------------------------

class TestComputeEquilibriumReturns:
    def test_basic(self):
        """Equilibrium returns are computed as delta * Sigma * w."""
        weights = [0.5, 0.5]
        cov = _cov_2x2()
        result = compute_equilibrium_returns(weights, cov, risk_aversion=2.5)
        assert len(result) == 2
        # Pi = 2.5 * [[0.04, 0.01], [0.01, 0.09]] * [0.5, 0.5]
        # = 2.5 * [0.025, 0.05] = [0.0625, 0.125]
        assert result[0] == pytest.approx(0.0625, abs=1e-6)
        assert result[1] == pytest.approx(0.125, abs=1e-6)

    def test_zero_risk_aversion(self):
        """Zero risk aversion yields zero equilibrium returns."""
        weights = [0.5, 0.5]
        cov = _cov_2x2()
        result = compute_equilibrium_returns(weights, cov, risk_aversion=0.0)
        assert all(r == pytest.approx(0.0) for r in result)

    def test_single_asset(self):
        """Single asset returns delta * variance * weight."""
        result = compute_equilibrium_returns([1.0], [[0.04]], risk_aversion=2.5)
        assert len(result) == 1
        assert result[0] == pytest.approx(0.1, abs=1e-6)

    def test_proportional_to_weights(self):
        """Higher weight should produce higher equilibrium return (same-variance case)."""
        cov = [[0.04, 0.0], [0.0, 0.04]]
        result_a = compute_equilibrium_returns([0.8, 0.2], cov, risk_aversion=2.5)
        result_b = compute_equilibrium_returns([0.2, 0.8], cov, risk_aversion=2.5)
        assert result_a[0] > result_b[0]
        assert result_a[1] < result_b[1]

    def test_three_assets(self):
        """Works with 3 assets."""
        weights = [1.0 / 3] * 3
        cov = _cov_3x3()
        result = compute_equilibrium_returns(weights, cov, risk_aversion=2.5)
        assert len(result) == 3
        assert all(isinstance(r, float) for r in result)


# ---------------------------------------------------------------------------
# TestCreateViewMatrix
# ---------------------------------------------------------------------------

class TestCreateViewMatrix:
    def test_single_absolute_view(self):
        """Single absolute view: asset 0 returns 5%."""
        views = [{"assets": [0], "weights": [1.0], "return": 0.05}]
        p, q = create_view_matrix(3, views)
        assert len(p) == 1
        assert len(q) == 1
        assert p[0] == [1.0, 0.0, 0.0]
        assert q[0] == 0.05

    def test_relative_view(self):
        """Relative view: asset 0 outperforms asset 1."""
        views = [{"assets": [0, 1], "weights": [1.0, -1.0], "return": 0.02}]
        p, q = create_view_matrix(3, views)
        assert p[0] == [1.0, -1.0, 0.0]
        assert q[0] == 0.02

    def test_multiple_views(self):
        """Multiple views produce correct P and Q dimensions."""
        views = [
            {"assets": [0], "weights": [1.0], "return": 0.05},
            {"assets": [1, 2], "weights": [1.0, -1.0], "return": 0.01},
        ]
        p, q = create_view_matrix(3, views)
        assert len(p) == 2
        assert len(q) == 2
        assert p[1] == [0.0, 1.0, -1.0]

    def test_empty_views(self):
        """Empty views return empty P and Q."""
        p, q = create_view_matrix(3, [])
        assert p == []
        assert q == []

    def test_mismatched_assets_weights_raises(self):
        """Mismatched assets/weights lengths raise error."""
        views = [{"assets": [0, 1], "weights": [1.0], "return": 0.02}]
        with pytest.raises(BlackLittermanError, match="mismatch"):
            create_view_matrix(3, views)

    def test_out_of_range_index_raises(self):
        """Asset index out of range raises error."""
        views = [{"assets": [5], "weights": [1.0], "return": 0.02}]
        with pytest.raises(BlackLittermanError, match="out of range"):
            create_view_matrix(3, views)


# ---------------------------------------------------------------------------
# TestComputePosteriorReturns
# ---------------------------------------------------------------------------

class TestComputePosteriorReturns:
    def test_no_views_returns_equilibrium(self):
        """No views means posterior equals equilibrium."""
        eq = [0.05, 0.10]
        cov = _cov_2x2()
        result = compute_posterior_returns(eq, cov, [], [])
        assert result == eq

    def test_with_views_differs_from_equilibrium(self):
        """Adding views should shift returns away from equilibrium."""
        eq = [0.05, 0.10]
        cov = _cov_2x2()
        p = [[1.0, 0.0]]  # view on asset 0
        q = [0.15]  # view: asset 0 returns 15%
        result = compute_posterior_returns(eq, cov, p, q, tau=0.05)
        # Posterior should be shifted toward the view
        assert result[0] > eq[0]

    def test_tau_sensitivity(self):
        """Higher tau gives more weight to views (with fixed omega)."""
        eq = [0.05, 0.10]
        cov = [[0.04, 0.0], [0.0, 0.04]]
        p = [[1.0, 0.0]]
        q = [0.50]  # strong bullish view on asset 0
        # Use fixed omega so tau doesn't cancel out
        fixed_omega = [[0.01]]

        result_low_tau = compute_posterior_returns(eq, cov, p, q, tau=0.01, omega=fixed_omega)
        result_high_tau = compute_posterior_returns(eq, cov, p, q, tau=0.50, omega=fixed_omega)

        # Higher tau → more uncertainty in prior → more weight to views
        assert result_high_tau[0] > result_low_tau[0]

    def test_posterior_between_prior_and_view(self):
        """Posterior should lie between equilibrium and view for absolute view."""
        eq = [0.05, 0.10]
        cov = _cov_2x2()
        p = [[1.0, 0.0]]
        q = [0.20]  # view: asset 0 returns 20%
        result = compute_posterior_returns(eq, cov, p, q, tau=0.05)
        # Posterior for asset 0 should be between equilibrium and view
        assert eq[0] < result[0] < q[0]

    def test_returns_correct_length(self):
        """Posterior has same length as equilibrium."""
        eq = [0.05, 0.10, 0.08]
        cov = _cov_3x3()
        p = [[1.0, 0.0, 0.0]]
        q = [0.15]
        result = compute_posterior_returns(eq, cov, p, q, tau=0.05)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# TestOptimizeBlackLitterman
# ---------------------------------------------------------------------------

class TestOptimizeBlackLitterman:
    def test_weights_sum_to_one(self):
        """Optimal weights sum to 1."""
        posterior = [0.08, 0.12, 0.06]
        cov = _cov_3x3()
        weights = optimize_black_litterman(posterior, cov)
        assert sum(weights) == pytest.approx(1.0, abs=1e-4)

    def test_long_only(self):
        """All weights are non-negative."""
        posterior = [0.08, 0.12, 0.06]
        cov = _cov_3x3()
        weights = optimize_black_litterman(posterior, cov)
        assert all(w >= -1e-6 for w in weights)

    def test_single_asset(self):
        """Single asset gets full weight."""
        weights = optimize_black_litterman([0.10], [[0.04]])
        assert len(weights) == 1
        assert weights[0] == pytest.approx(1.0)

    def test_empty(self):
        """Empty inputs return empty weights."""
        assert optimize_black_litterman([], []) == []

    def test_favors_higher_return(self):
        """Asset with much higher return should get more weight."""
        # Uncorrelated assets, same variance, very different returns
        cov = [[0.04, 0.0], [0.0, 0.04]]
        posterior = [0.02, 0.20]
        weights = optimize_black_litterman(posterior, cov)
        assert weights[1] > weights[0]


# ---------------------------------------------------------------------------
# TestAnalyzeBlackLitterman
# ---------------------------------------------------------------------------

class TestAnalyzeBlackLitterman:
    def _make_storage(self, returns_data=None, cov_data=None):
        class MockStorage:
            def __init__(self, processed):
                self._processed = processed
                self._saved = {}

            def load_processed(self, key):
                if key not in self._processed:
                    raise FileNotFoundError(f"Key {key} not found")
                return self._processed[key]

            def save_output(self, data, key):
                self._saved[key] = data

        if returns_data is None:
            returns_data = {
                "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                "annualized_mean": [0.15, 0.20, 0.10],
            }
        if cov_data is None:
            cov_data = {
                "matrix": [
                    [0.04, 0.006, 0.002],
                    [0.006, 0.09, 0.004],
                    [0.002, 0.004, 0.01],
                ],
            }

        return MockStorage({
            "returns": returns_data,
            "covariance": cov_data,
        })

    def test_basic_analysis(self):
        storage = self._make_storage()
        result = analyze_black_litterman(storage=storage, save=False)
        assert "weights" in result
        assert "equilibrium_returns" in result
        assert "posterior_returns" in result
        assert "views" in result
        assert "expected_return" in result
        assert "volatility" in result
        assert "sharpe_ratio" in result
        assert "n_assets" in result
        assert result["method"] == "black_litterman"

    def test_saves_to_storage(self):
        storage = self._make_storage()
        analyze_black_litterman(storage=storage, save=True)
        assert "black_litterman" in storage._saved

    def test_no_save_when_disabled(self):
        storage = self._make_storage()
        analyze_black_litterman(storage=storage, save=False)
        assert "black_litterman" not in storage._saved

    def test_missing_data_raises(self):
        class EmptyStorage:
            def load_processed(self, key):
                raise FileNotFoundError("no data")

        with pytest.raises(BlackLittermanError, match="Processed data not found"):
            analyze_black_litterman(storage=EmptyStorage())

    def test_empty_data_raises(self):
        storage = self._make_storage(
            returns_data={"symbols": [], "annualized_mean": []},
            cov_data={"matrix": []},
        )
        with pytest.raises(BlackLittermanError, match="incomplete"):
            analyze_black_litterman(storage=storage)

    def test_default_views_created(self):
        """When no views provided, default views are created."""
        storage = self._make_storage()
        result = analyze_black_litterman(storage=storage, save=False)
        assert len(result["views"]) >= 1

    def test_custom_views(self):
        """Custom views are used when provided."""
        storage = self._make_storage()
        custom_views = [
            {"assets": [0], "weights": [1.0], "return": 0.30},
        ]
        result = analyze_black_litterman(
            views=custom_views, storage=storage, save=False
        )
        assert result["views"] == custom_views

    def test_weights_sum_to_one(self):
        storage = self._make_storage()
        result = analyze_black_litterman(storage=storage, save=False)
        total = sum(result["weights"].values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_parameters_recorded(self):
        storage = self._make_storage()
        result = analyze_black_litterman(
            risk_aversion=3.0, tau=0.10, storage=storage, save=False
        )
        assert result["parameters"]["risk_aversion"] == 3.0
        assert result["parameters"]["tau"] == 0.10


# ---------------------------------------------------------------------------
# TestBlackLittermanError
# ---------------------------------------------------------------------------

class TestBlackLittermanError:
    def test_message(self):
        err = BlackLittermanError("test error")
        assert str(err) == "test error"
        assert err.message == "test error"
        assert err.operation == "black_litterman"

    def test_custom_operation(self):
        err = BlackLittermanError("fail", operation="load")
        assert err.operation == "load"
