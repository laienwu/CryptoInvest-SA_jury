"""Tests for per-asset risk contribution analysis."""

import math

import pytest

from src.pipeline.optimize import compute_risk_contribution


# 2-asset covariance matrix (annualized)
COV_2 = [
    [0.04, 0.01],  # asset 0: 20% vol
    [0.01, 0.09],  # asset 1: 30% vol
]


class TestComputeRiskContribution:
    """Tests for compute_risk_contribution."""

    def test_output_keys(self):
        result = compute_risk_contribution([0.6, 0.4], COV_2, ["A", "B"])
        assert "contributions" in result
        assert "portfolio_volatility" in result
        assert "n_assets" in result

    def test_n_assets(self):
        result = compute_risk_contribution([0.6, 0.4], COV_2)
        assert result["n_assets"] == 2

    def test_contributions_have_required_fields(self):
        result = compute_risk_contribution([0.6, 0.4], COV_2, ["A", "B"])
        item = result["contributions"][0]
        assert set(item.keys()) == {"symbol", "weight", "mctr", "risk_contribution", "pct_contribution"}

    def test_risk_contributions_sum_to_portfolio_vol(self):
        result = compute_risk_contribution([0.6, 0.4], COV_2, ["A", "B"])
        total_rc = sum(c["risk_contribution"] for c in result["contributions"])
        assert total_rc == pytest.approx(result["portfolio_volatility"], abs=1e-4)

    def test_pct_contributions_sum_to_one(self):
        result = compute_risk_contribution([0.6, 0.4], COV_2, ["A", "B"])
        total_pct = sum(c["pct_contribution"] for c in result["contributions"])
        assert total_pct == pytest.approx(1.0, abs=1e-3)

    def test_portfolio_volatility_matches_manual(self):
        w = [0.6, 0.4]
        # w'Σw = 0.6^2*0.04 + 2*0.6*0.4*0.01 + 0.4^2*0.09
        expected_var = 0.36 * 0.04 + 2 * 0.24 * 0.01 + 0.16 * 0.09
        expected_vol = math.sqrt(expected_var)
        result = compute_risk_contribution(w, COV_2)
        assert result["portfolio_volatility"] == pytest.approx(expected_vol, abs=1e-4)

    def test_single_asset(self):
        cov = [[0.04]]
        result = compute_risk_contribution([1.0], cov, ["BTC"])
        assert result["portfolio_volatility"] == pytest.approx(0.2, abs=1e-4)
        assert result["contributions"][0]["pct_contribution"] == pytest.approx(1.0, abs=1e-3)

    def test_equal_weight_symmetric(self):
        # Symmetric covariance, equal weights → equal risk contribution
        cov_sym = [[0.04, 0.02], [0.02, 0.04]]
        result = compute_risk_contribution([0.5, 0.5], cov_sym, ["A", "B"])
        rc_a = next(c for c in result["contributions"] if c["symbol"] == "A")
        rc_b = next(c for c in result["contributions"] if c["symbol"] == "B")
        assert rc_a["risk_contribution"] == pytest.approx(rc_b["risk_contribution"], abs=1e-4)

    def test_sorted_by_abs_risk_contribution(self):
        result = compute_risk_contribution([0.6, 0.4], COV_2, ["A", "B"])
        rcs = [abs(c["risk_contribution"]) for c in result["contributions"]]
        assert rcs == sorted(rcs, reverse=True)

    def test_default_symbol_names(self):
        result = compute_risk_contribution([0.6, 0.4], COV_2)
        symbols = {c["symbol"] for c in result["contributions"]}
        assert symbols == {"asset_0", "asset_1"}

    def test_three_assets(self):
        cov_3 = [
            [0.04, 0.01, 0.005],
            [0.01, 0.09, 0.02],
            [0.005, 0.02, 0.0625],
        ]
        result = compute_risk_contribution(
            [0.4, 0.35, 0.25], cov_3, ["BTC", "ETH", "SOL"]
        )
        assert result["n_assets"] == 3
        total_rc = sum(c["risk_contribution"] for c in result["contributions"])
        assert total_rc == pytest.approx(result["portfolio_volatility"], abs=1e-4)

    def test_zero_weight_asset(self):
        result = compute_risk_contribution([1.0, 0.0], COV_2, ["A", "B"])
        b_contrib = next(c for c in result["contributions"] if c["symbol"] == "B")
        assert b_contrib["risk_contribution"] == pytest.approx(0.0, abs=1e-6)
