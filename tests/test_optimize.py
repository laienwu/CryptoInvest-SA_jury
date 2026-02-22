"""
Tests for the optimize module.

Tests portfolio optimization functions:
- Portfolio return calculation
- Portfolio volatility calculation
- Sharpe ratio calculation
- Weight generation
- Matrix operations
"""

import math

import pytest

from src.pipeline.optimize import (
    OptimizeError,
    calculate_portfolio_return,
    calculate_portfolio_variance,
    calculate_portfolio_volatility,
    calculate_sharpe_ratio,
    dot_product,
    matrix_vector_multiply,
    optimize_minimum_variance,
)

RISK_FREE_RATE: float = 0.05


class TestMatrixOperations:
    """Tests for matrix/vector operations."""

    def test_dot_product(self):
        """Test dot product calculation."""
        v1 = [1.0, 2.0, 3.0]
        v2 = [4.0, 5.0, 6.0]
        result = dot_product(v1, v2)
        expected = 1 * 4 + 2 * 5 + 3 * 6  # 32
        assert result == pytest.approx(expected)

    def test_dot_product_zero_vector(self):
        """Test dot product with zero vector."""
        v1 = [1.0, 2.0, 3.0]
        v2 = [0.0, 0.0, 0.0]
        result = dot_product(v1, v2)
        assert result == pytest.approx(0.0)

    def test_matrix_vector_multiply(self):
        """Test matrix-vector multiplication."""
        matrix = [
            [1.0, 2.0],
            [3.0, 4.0],
        ]
        vector = [5.0, 6.0]
        result = matrix_vector_multiply(matrix, vector)
        expected = [1 * 5 + 2 * 6, 3 * 5 + 4 * 6]  # [17, 39]
        assert result[0] == pytest.approx(expected[0])
        assert result[1] == pytest.approx(expected[1])


class TestPortfolioReturn:
    """Tests for portfolio return calculation."""

    def test_equal_weight_portfolio(self, sample_mean_returns):
        """Test return of equal-weight portfolio."""
        weights = [1 / 3, 1 / 3, 1 / 3]
        result = calculate_portfolio_return(weights, sample_mean_returns)

        expected = (0.15 + 0.20 + 0.10) / 3
        assert result == pytest.approx(expected)

    def test_concentrated_portfolio(self, sample_mean_returns):
        """Test return of concentrated (single asset) portfolio."""
        weights = [1.0, 0.0, 0.0]
        result = calculate_portfolio_return(weights, sample_mean_returns)

        assert result == pytest.approx(0.15)  # First asset return

    def test_custom_weights(self, sample_mean_returns):
        """Test return with custom weights."""
        weights = [0.5, 0.3, 0.2]
        result = calculate_portfolio_return(weights, sample_mean_returns)

        expected = 0.5 * 0.15 + 0.3 * 0.20 + 0.2 * 0.10
        assert result == pytest.approx(expected)

    def test_zero_weights_rejected(self, sample_mean_returns):
        """Test that zero weights are rejected (sum != 1)."""
        from src.pipeline.optimize import OptimizeError

        weights = [0.0, 0.0, 0.0]
        with pytest.raises(OptimizeError, match="sum to"):
            calculate_portfolio_return(weights, sample_mean_returns)


class TestPortfolioVariance:
    """Tests for portfolio variance calculation."""

    def test_single_asset_variance(self, sample_covariance_matrix):
        """Test variance of single-asset portfolio equals asset variance."""
        weights = [1.0, 0.0, 0.0]
        variance = calculate_portfolio_variance(weights, sample_covariance_matrix)

        # Should equal first asset's variance (diagonal element)
        assert variance == pytest.approx(0.04)

    def test_two_asset_portfolio(self, sample_covariance_matrix):
        """Test variance of two-asset portfolio."""
        weights = [0.5, 0.5, 0.0]
        variance = calculate_portfolio_variance(weights, sample_covariance_matrix)

        # Var = w1^2 * var1 + w2^2 * var2 + 2*w1*w2*cov12
        expected = (
            0.5**2 * 0.04
            + 0.5**2 * 0.09
            + 2 * 0.5 * 0.5 * 0.02
        )
        assert variance == pytest.approx(expected)

    def test_diversification_reduces_variance(self, sample_covariance_matrix):
        """Test that diversification can reduce portfolio variance."""
        # Concentrated portfolio
        concentrated = [1.0, 0.0, 0.0]
        var_concentrated = calculate_portfolio_variance(
            concentrated, sample_covariance_matrix
        )

        # Diversified portfolio
        diversified = [0.4, 0.4, 0.2]
        var_diversified = calculate_portfolio_variance(
            diversified, sample_covariance_matrix
        )

        # Diversification should reduce variance (not always guaranteed
        # but typical with positive correlations < 1)
        assert var_diversified < var_concentrated


class TestPortfolioVolatility:
    """Tests for portfolio volatility calculation."""

    def test_volatility_is_sqrt_variance(self, sample_covariance_matrix, sample_weights):
        """Test that volatility = sqrt(variance)."""
        variance = calculate_portfolio_variance(sample_weights, sample_covariance_matrix)
        volatility = calculate_portfolio_volatility(
            sample_weights, sample_covariance_matrix
        )

        assert volatility == pytest.approx(math.sqrt(variance))

    def test_volatility_positive(self, sample_covariance_matrix, sample_weights):
        """Test that volatility is always non-negative."""
        volatility = calculate_portfolio_volatility(
            sample_weights, sample_covariance_matrix
        )
        assert volatility >= 0


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_sharpe_ratio_formula(
        self, sample_covariance_matrix, sample_mean_returns, sample_weights
    ):
        """Test Sharpe ratio calculation."""
        sharpe = calculate_sharpe_ratio(
            sample_weights,
            sample_mean_returns,
            sample_covariance_matrix,
            risk_free_rate=0.05,
        )

        # Manual calculation
        portfolio_return = calculate_portfolio_return(sample_weights, sample_mean_returns)
        portfolio_vol = calculate_portfolio_volatility(
            sample_weights, sample_covariance_matrix
        )
        expected = (portfolio_return - 0.05) / portfolio_vol

        assert sharpe == pytest.approx(expected)

    def test_sharpe_with_zero_volatility(self):
        """Test Sharpe ratio when volatility is zero."""
        weights = [1.0]
        mean_returns = [0.10]
        cov_matrix = [[0.0]]  # Zero variance

        sharpe = calculate_sharpe_ratio(
            weights, mean_returns, cov_matrix, risk_free_rate=0.05
        )
        assert sharpe == 0.0  # Should return 0 to avoid division by zero

    def test_negative_sharpe(self, sample_covariance_matrix):
        """Test negative Sharpe ratio when return < risk-free rate."""
        weights = [1 / 3, 1 / 3, 1 / 3]
        mean_returns = [0.01, 0.02, 0.01]  # Low returns
        risk_free_rate = 0.05  # Higher than portfolio return

        sharpe = calculate_sharpe_ratio(
            weights, mean_returns, sample_covariance_matrix, risk_free_rate
        )
        assert sharpe < 0

    def test_higher_return_higher_sharpe(self, sample_covariance_matrix):
        """Test that higher return leads to higher Sharpe (same volatility)."""
        weights = [1 / 3, 1 / 3, 1 / 3]
        low_returns = [0.10, 0.10, 0.10]
        high_returns = [0.20, 0.20, 0.20]

        sharpe_low = calculate_sharpe_ratio(
            weights, low_returns, sample_covariance_matrix
        )
        sharpe_high = calculate_sharpe_ratio(
            weights, high_returns, sample_covariance_matrix
        )

        assert sharpe_high > sharpe_low


class TestMinimumVariancePortfolio:
    """Tests for minimum variance portfolio optimization."""

    def test_two_asset_minimum_variance(self):
        """Test minimum variance portfolio for 2 assets."""
        # Simple case: two assets with known optimal solution
        cov_matrix = [
            [0.04, 0.01],  # var1 = 0.04, cov = 0.01
            [0.01, 0.09],  # var2 = 0.09
        ]

        weights = optimize_minimum_variance(cov_matrix)

        # Analytical solution:
        # w1 = (var2 - cov) / (var1 + var2 - 2*cov)
        var1, var2, cov = 0.04, 0.09, 0.01
        expected_w1 = (var2 - cov) / (var1 + var2 - 2 * cov)
        expected_w2 = 1 - expected_w1

        assert weights[0] == pytest.approx(expected_w1, rel=0.1)
        assert weights[1] == pytest.approx(expected_w2, rel=0.1)

    def test_weights_sum_to_one(self, sample_covariance_matrix):
        """Test that minimum variance weights sum to 1."""
        weights = optimize_minimum_variance(sample_covariance_matrix)
        assert sum(weights) == pytest.approx(1.0, rel=0.01)

    def test_lower_variance_than_equal_weight(self, sample_covariance_matrix):
        """Test min variance portfolio has lower variance than equal weight."""
        weights = optimize_minimum_variance(sample_covariance_matrix)
        n = len(sample_covariance_matrix)
        equal_w = [1.0 / n] * n
        min_var = calculate_portfolio_variance(weights, sample_covariance_matrix)
        eq_var = calculate_portfolio_variance(equal_w, sample_covariance_matrix)
        assert min_var <= eq_var


class TestOptimizeError:
    """Tests for OptimizeError exception."""

    def test_error_message(self):
        """Test error message."""
        error = OptimizeError("Test error", operation="test_op")
        assert error.message == "Test error"
        assert error.operation == "test_op"
        assert str(error) == "Test error"

    def test_error_without_operation(self):
        """Test error without operation."""
        error = OptimizeError("Simple error")
        assert error.message == "Simple error"
        assert error.operation is None


class TestPortfolioMetricsIntegration:
    """Integration tests for portfolio metrics."""

    def test_consistent_metrics(
        self, sample_covariance_matrix, sample_mean_returns, sample_weights
    ):
        """Test that all metrics are consistent."""
        portfolio_return = calculate_portfolio_return(sample_weights, sample_mean_returns)
        portfolio_vol = calculate_portfolio_volatility(
            sample_weights, sample_covariance_matrix
        )
        sharpe = calculate_sharpe_ratio(
            sample_weights,
            sample_mean_returns,
            sample_covariance_matrix,
            RISK_FREE_RATE,
        )

        # Verify Sharpe formula
        expected_sharpe = (portfolio_return - RISK_FREE_RATE) / portfolio_vol
        assert sharpe == pytest.approx(expected_sharpe)

    def test_equal_weight_benchmark(self, sample_covariance_matrix, sample_mean_returns):
        """Test equal weight portfolio as benchmark."""
        n = len(sample_mean_returns)
        equal_weights = [1.0 / n] * n

        # All metrics should be computable
        ret = calculate_portfolio_return(equal_weights, sample_mean_returns)
        vol = calculate_portfolio_volatility(equal_weights, sample_covariance_matrix)
        sharpe = calculate_sharpe_ratio(
            equal_weights, sample_mean_returns, sample_covariance_matrix
        )

        assert ret > 0
        assert vol > 0
        assert isinstance(sharpe, float)
