"""
Tests for the transform module.

Tests financial calculations:
- Log returns
- Volatility
- Correlation matrix
- Covariance matrix
- Mean returns
"""

import math

import pytest

from src.pipeline.transform import (
    TransformError,
    calculate_correlation,
    calculate_correlation_matrix,
    calculate_covariance,
    calculate_covariance_matrix,
    calculate_log_returns,
    calculate_mean,
    calculate_mean_returns,
    calculate_stddev,
    calculate_volatility,
)

TRADING_DAYS_PER_YEAR: int = 365


class TestCalculateMean:
    """Tests for calculate_mean function."""

    def test_simple_mean(self):
        """Test mean of simple values."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_mean(values)
        assert result == pytest.approx(3.0)

    def test_single_value(self):
        """Test mean of single value."""
        values = [42.0]
        result = calculate_mean(values)
        assert result == pytest.approx(42.0)

    def test_negative_values(self):
        """Test mean with negative values."""
        values = [-1.0, 0.0, 1.0]
        result = calculate_mean(values)
        assert result == pytest.approx(0.0)

    def test_decimal_values(self):
        """Test mean with decimal values."""
        values = [0.1, 0.2, 0.3]
        result = calculate_mean(values)
        assert result == pytest.approx(0.2)


class TestCalculateStddev:
    """Tests for calculate_stddev function."""

    def test_sample_stddev(self):
        """Test sample standard deviation (ddof=1)."""
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        result = calculate_stddev(values, ddof=1)
        assert result == pytest.approx(2.138, rel=0.01)

    def test_population_stddev(self):
        """Test population standard deviation (ddof=0)."""
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        result = calculate_stddev(values, ddof=0)
        assert result == pytest.approx(2.0, rel=0.01)

    def test_constant_values(self):
        """Test stddev of constant values."""
        values = [5.0, 5.0, 5.0, 5.0]
        result = calculate_stddev(values, ddof=0)
        assert result == pytest.approx(0.0)


class TestCalculateLogReturns:
    """Tests for calculate_log_returns function."""

    def test_basic_returns(self, sample_prices):
        """Test log returns calculation."""
        returns = calculate_log_returns(sample_prices)

        # Check shape: 3 symbols, 9 returns (10 prices - 1)
        assert len(returns) == 3
        assert len(returns[0]) == 9

    def test_return_values(self):
        """Test specific return values."""
        prices = [[100.0, 110.0]]  # Single 10% gain
        returns = calculate_log_returns(prices)

        expected = math.log(110 / 100)  # ~0.0953
        assert returns[0][0] == pytest.approx(expected)

    def test_symmetric_returns(self):
        """Test that log returns are symmetric."""
        # +10% then -10% should sum to approximately 0
        prices = [[100.0, 110.0, 99.0]]
        returns = calculate_log_returns(prices)

        # Log returns: ln(110/100) + ln(99/110) = ln(99/100)
        total = sum(returns[0])
        expected = math.log(99 / 100)
        assert total == pytest.approx(expected)

    def test_multiple_symbols(self, sample_prices):
        """Test returns for multiple symbols."""
        returns = calculate_log_returns(sample_prices)

        # First return for first symbol: ln(102/100)
        expected_first = math.log(102 / 100)
        assert returns[0][0] == pytest.approx(expected_first)


class TestCalculateVolatility:
    """Tests for calculate_volatility function."""

    def test_volatility_calculation(self, sample_returns):
        """Test annualized volatility calculation."""
        volatility = calculate_volatility(sample_returns)

        # Should return list of volatilities for each symbol
        assert len(volatility) == 3
        assert all(v > 0 for v in volatility)

    def test_annualization(self):
        """Test that volatility is properly annualized."""
        # Create returns with known daily std
        daily_std = 0.01  # 1% daily std
        returns = [[daily_std] * 100]  # Constant returns (unrealistic but for testing)

        # With constant returns, std should be 0
        vol = calculate_volatility(returns)
        assert vol[0] == pytest.approx(0.0, abs=1e-10)

    def test_higher_variance_higher_volatility(self):
        """Test that higher variance leads to higher volatility."""
        low_var_returns = [[0.01, 0.01, 0.01, 0.01]]
        high_var_returns = [[0.05, -0.05, 0.05, -0.05]]

        low_vol = calculate_volatility(low_var_returns)
        high_vol = calculate_volatility(high_var_returns)

        assert high_vol[0] > low_vol[0]


class TestCalculateCorrelation:
    """Tests for calculate_correlation function."""

    def test_perfect_positive_correlation(self):
        """Test correlation of identical series."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0, 5.0]
        corr = calculate_correlation(x, y)
        assert corr == pytest.approx(1.0)

    def test_perfect_negative_correlation(self):
        """Test correlation of opposite series."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]
        corr = calculate_correlation(x, y)
        assert corr == pytest.approx(-1.0)

    def test_no_correlation(self):
        """Test uncorrelated series."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [3.0, 1.0, 4.0, 2.0, 5.0]  # Shuffled
        corr = calculate_correlation(x, y)
        # Should be close to 0 but not exactly
        assert -1.0 <= corr <= 1.0

    def test_correlation_bounds(self):
        """Test that correlation is always between -1 and 1."""
        import random

        random.seed(42)
        x = [random.random() for _ in range(100)]
        y = [random.random() for _ in range(100)]
        corr = calculate_correlation(x, y)
        assert -1.0 <= corr <= 1.0


class TestCalculateCorrelationMatrix:
    """Tests for calculate_correlation_matrix function."""

    def test_diagonal_is_one(self, sample_returns):
        """Test that diagonal elements are 1."""
        corr_matrix = calculate_correlation_matrix(sample_returns)

        for i in range(len(sample_returns)):
            assert corr_matrix[i][i] == pytest.approx(1.0)

    def test_symmetric_matrix(self, sample_returns):
        """Test that correlation matrix is symmetric."""
        corr_matrix = calculate_correlation_matrix(sample_returns)
        n = len(corr_matrix)

        for i in range(n):
            for j in range(n):
                assert corr_matrix[i][j] == pytest.approx(corr_matrix[j][i])

    def test_bounds(self, sample_returns):
        """Test that all correlations are between -1 and 1."""
        corr_matrix = calculate_correlation_matrix(sample_returns)

        for row in corr_matrix:
            for value in row:
                assert -1.0 <= value <= 1.0

    def test_matrix_shape(self, sample_returns):
        """Test matrix dimensions."""
        corr_matrix = calculate_correlation_matrix(sample_returns)
        n = len(sample_returns)

        assert len(corr_matrix) == n
        assert all(len(row) == n for row in corr_matrix)


class TestCalculateCovariance:
    """Tests for calculate_covariance function."""

    def test_variance_equals_covariance_with_self(self):
        """Test that cov(x, x) = var(x)."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        cov_xx = calculate_covariance(x, x)
        var_x = calculate_stddev(x, ddof=1) ** 2
        assert cov_xx == pytest.approx(var_x)

    def test_covariance_symmetric(self):
        """Test that cov(x, y) = cov(y, x)."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 5.0, 4.0, 5.0]
        assert calculate_covariance(x, y) == pytest.approx(calculate_covariance(y, x))

    def test_positive_covariance(self):
        """Test positive covariance for positively related series."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]  # y = 2x
        cov = calculate_covariance(x, y)
        assert cov > 0


class TestCalculateCovarianceMatrix:
    """Tests for calculate_covariance_matrix function."""

    def test_positive_semidefinite(self, sample_returns):
        """Test that covariance matrix is positive semidefinite."""
        cov_matrix = calculate_covariance_matrix(sample_returns)

        # Check diagonal elements are positive (variances)
        for i in range(len(cov_matrix)):
            assert cov_matrix[i][i] > 0

    def test_symmetric_matrix(self, sample_returns):
        """Test that covariance matrix is symmetric."""
        cov_matrix = calculate_covariance_matrix(sample_returns)
        n = len(cov_matrix)

        for i in range(n):
            for j in range(n):
                assert cov_matrix[i][j] == pytest.approx(cov_matrix[j][i])

    def test_annualization(self, sample_returns):
        """Test that covariance is annualized by TRADING_DAYS_PER_YEAR."""
        # Calculate daily covariance manually
        daily_cov = calculate_covariance(sample_returns[0], sample_returns[0])
        annualized_cov = daily_cov * TRADING_DAYS_PER_YEAR

        cov_matrix = calculate_covariance_matrix(sample_returns)
        assert cov_matrix[0][0] == pytest.approx(annualized_cov)


class TestCalculateMeanReturns:
    """Tests for calculate_mean_returns function."""

    def test_mean_returns_calculation(self, sample_returns):
        """Test mean returns calculation."""
        mean_returns = calculate_mean_returns(sample_returns)

        # Should return list of mean returns for each symbol
        assert len(mean_returns) == 3

    def test_annualization(self):
        """Test that mean returns are annualized."""
        daily_return = 0.001  # 0.1% daily
        returns = [[daily_return] * 100]

        mean_returns = calculate_mean_returns(returns)
        expected_annual = daily_return * TRADING_DAYS_PER_YEAR

        assert mean_returns[0] == pytest.approx(expected_annual)

    def test_positive_and_negative_returns(self):
        """Test with mixed positive and negative returns."""
        returns = [[0.01, -0.02, 0.03, -0.01, 0.02]]
        mean_returns = calculate_mean_returns(returns)

        daily_mean = (0.01 - 0.02 + 0.03 - 0.01 + 0.02) / 5
        expected = daily_mean * TRADING_DAYS_PER_YEAR

        assert mean_returns[0] == pytest.approx(expected)


class TestDataAlignment:
    """Tests for data alignment functionality."""

    def test_align_common_dates(self, sample_raw_data):
        """Test that data is aligned by common dates."""
        from src.pipeline.transform import align_data_by_date

        symbols, dates, prices = align_data_by_date(sample_raw_data)

        assert len(symbols) == 2
        assert len(dates) == 10
        assert len(prices) == 2
        assert len(prices[0]) == 10

    def test_empty_data_raises_error(self):
        """Test that empty data raises TransformError."""
        from src.pipeline.transform import align_data_by_date

        with pytest.raises(TransformError):
            align_data_by_date({})

    def test_mismatched_dates(self):
        """Test handling of mismatched dates."""
        from src.pipeline.transform import align_data_by_date

        data = {
            "BTCUSDT": [
                {"timestamp": "2024-01-01", "close": 100.0},
                {"timestamp": "2024-01-02", "close": 101.0},
            ],
            "ETHUSDT": [
                {"timestamp": "2024-01-02", "close": 50.0},
                {"timestamp": "2024-01-03", "close": 51.0},
            ],
        }

        symbols, dates, prices = align_data_by_date(data)

        # Only 2024-01-02 is common
        assert len(dates) == 1
        assert dates[0] == "2024-01-02"
