"""
Tests for the backtesting engine.

Tests:
- Rolling window creation
- Cumulative value computation
- Max drawdown calculation
- Performance metrics
- Window optimization
- Portfolio returns on test data
"""

import math

import pytest

from src.pipeline.backtest import (
    BacktestError,
    _create_rolling_windows,
    _cumulative_values,
    _max_drawdown,
    _compute_metrics,
    _optimize_on_window,
    _compute_portfolio_daily_returns,
)


@pytest.fixture
def sample_dates() -> list[str]:
    """100 days of dates for backtesting."""
    return [f"2024-01-{i:02d}" if i <= 31
            else f"2024-02-{i-31:02d}" if i <= 59
            else f"2024-03-{i-59:02d}" if i <= 90
            else f"2024-04-{i-90:02d}"
            for i in range(1, 101)]


@pytest.fixture
def sample_prices_100() -> list[list[float]]:
    """Price matrix for 3 symbols over 100 days with realistic trends."""
    import math
    prices = []
    for base in [100.0, 50.0, 10.0]:
        series = []
        price = base
        for i in range(100):
            price = base * (1 + 0.001 * i + 0.02 * math.sin(i / 5))
            series.append(max(price, 0.01))
        prices.append(series)
    return prices


class TestRollingWindows:
    """Tests for _create_rolling_windows."""

    def test_window_creation(self, sample_dates, sample_prices_100):
        """Test basic window creation."""
        windows = _create_rolling_windows(
            sample_dates, sample_prices_100, train_window=20, test_window=10
        )

        assert len(windows) > 0
        for w in windows:
            assert "window_id" in w
            assert "train_start_idx" in w
            assert "train_end_idx" in w
            assert "test_start_idx" in w
            assert "test_end_idx" in w
            # Training window correct size
            assert w["train_end_idx"] - w["train_start_idx"] == 20
            # Test immediately follows train
            assert w["test_start_idx"] == w["train_end_idx"]

    def test_non_overlapping_test_windows(self, sample_dates, sample_prices_100):
        """Test that test windows don't overlap."""
        windows = _create_rolling_windows(
            sample_dates, sample_prices_100, train_window=20, test_window=10
        )

        for i in range(1, len(windows)):
            # Next window starts where previous test ended
            assert windows[i]["train_start_idx"] >= windows[i - 1]["test_end_idx"]

    def test_insufficient_data(self):
        """Test that insufficient data raises error."""
        dates = [f"2024-01-{i:02d}" for i in range(1, 6)]  # 5 days
        prices = [[100.0, 101.0, 102.0, 103.0, 104.0]]

        with pytest.raises(BacktestError):
            _create_rolling_windows(dates, prices, train_window=60, test_window=30)

    def test_exact_fit(self):
        """Test window creation when data fits exactly."""
        dates = [f"2024-01-{i:02d}" for i in range(1, 11)]  # 10 days
        prices = [[float(i) for i in range(1, 11)]]

        windows = _create_rolling_windows(dates, prices, train_window=5, test_window=5)
        assert len(windows) == 1
        assert windows[0]["train_start_idx"] == 0
        assert windows[0]["train_end_idx"] == 5
        assert windows[0]["test_start_idx"] == 5
        assert windows[0]["test_end_idx"] == 10


class TestCumulativeValues:
    """Tests for _cumulative_values."""

    def test_positive_returns(self):
        """Test cumulative values with positive returns."""
        returns = [0.01, 0.02, 0.03]
        values = _cumulative_values(returns, initial=1.0)

        assert len(values) == 4  # initial + 3 returns
        assert values[0] == pytest.approx(1.0)
        # Each value should be greater than previous (positive returns)
        for i in range(1, len(values)):
            assert values[i] > values[i - 1]

    def test_zero_returns(self):
        """Test cumulative values with zero returns."""
        returns = [0.0, 0.0, 0.0]
        values = _cumulative_values(returns, initial=1.0)

        assert len(values) == 4
        for v in values:
            assert v == pytest.approx(1.0)

    def test_custom_initial(self):
        """Test with custom initial value."""
        returns = [0.1]
        values = _cumulative_values(returns, initial=100.0)

        assert values[0] == pytest.approx(100.0)
        assert values[1] == pytest.approx(100.0 * math.exp(0.1))

    def test_empty_returns(self):
        """Test with empty returns."""
        values = _cumulative_values([], initial=1.0)
        assert values == [1.0]


class TestMaxDrawdown:
    """Tests for _max_drawdown."""

    def test_no_drawdown(self):
        """Test monotonically increasing values have zero drawdown."""
        values = [1.0, 1.1, 1.2, 1.3, 1.4]
        assert _max_drawdown(values) == pytest.approx(0.0)

    def test_simple_drawdown(self):
        """Test simple drawdown calculation."""
        values = [1.0, 1.2, 0.9, 1.0]
        # Peak = 1.2, trough = 0.9, drawdown = (1.2 - 0.9) / 1.2 = 0.25
        assert _max_drawdown(values) == pytest.approx(0.25)

    def test_multiple_peaks(self):
        """Test drawdown with multiple peaks."""
        values = [1.0, 1.5, 1.0, 2.0, 1.2]
        # First drawdown: (1.5 - 1.0) / 1.5 = 0.333
        # Second drawdown: (2.0 - 1.2) / 2.0 = 0.4
        assert _max_drawdown(values) == pytest.approx(0.4)

    def test_empty_values(self):
        """Test empty values."""
        assert _max_drawdown([]) == pytest.approx(0.0)

    def test_single_value(self):
        """Test single value."""
        assert _max_drawdown([1.0]) == pytest.approx(0.0)


class TestMetrics:
    """Tests for _compute_metrics."""

    def test_structure(self):
        """Test metrics output has required keys."""
        returns = [0.01, 0.02, -0.01, 0.015, 0.005]
        metrics = _compute_metrics(returns)

        assert "cumulative_return" in metrics
        assert "annualized_return" in metrics
        assert "max_drawdown" in metrics
        assert "sharpe_ratio" in metrics
        assert "calmar_ratio" in metrics

    def test_positive_returns_positive_sharpe(self):
        """Test that positive returns with variance give positive Sharpe."""
        # Need some variance for stddev > 0, but all positive
        returns = [0.01, 0.02, 0.015, 0.012, 0.018] * 6  # 30 days
        metrics = _compute_metrics(returns, risk_free_rate=0.05)

        assert metrics["sharpe_ratio"] > 0
        assert metrics["cumulative_return"] > 0
        assert metrics["annualized_return"] > 0

    def test_empty_returns(self):
        """Test metrics with empty returns."""
        metrics = _compute_metrics([])
        assert metrics["cumulative_return"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0

    def test_negative_returns(self):
        """Test metrics with negative returns."""
        returns = [-0.01] * 30
        metrics = _compute_metrics(returns)

        assert metrics["cumulative_return"] < 0
        assert metrics["max_drawdown"] > 0


class TestOptimizeOnWindow:
    """Tests for _optimize_on_window."""

    def test_max_sharpe(self, sample_prices):
        """Test max Sharpe optimization on a price window."""
        weights = _optimize_on_window(sample_prices, strategy="max_sharpe")

        assert len(weights) == len(sample_prices)
        assert sum(weights) == pytest.approx(1.0, abs=0.01)
        assert all(w >= -1e-6 for w in weights)

    def test_min_variance(self, sample_prices):
        """Test min variance optimization on a price window."""
        weights = _optimize_on_window(sample_prices, strategy="min_variance")

        assert len(weights) == len(sample_prices)
        assert sum(weights) == pytest.approx(1.0, abs=0.01)
        assert all(w >= -0.01 for w in weights)

    def test_unknown_strategy_raises(self, sample_prices):
        """Test that unknown strategy raises BacktestError."""
        with pytest.raises(BacktestError):
            _optimize_on_window(sample_prices, strategy="unknown")


class TestPortfolioReturnsOnTest:
    """Tests for _compute_portfolio_daily_returns."""

    def test_equal_weight(self, sample_prices):
        """Test equal weight portfolio returns."""
        n = len(sample_prices)
        weights = [1.0 / n] * n
        returns = _compute_portfolio_daily_returns(sample_prices, weights)

        # Should have n_days - 1 returns
        assert len(returns) == len(sample_prices[0]) - 1

    def test_concentrated_portfolio(self, sample_prices):
        """Test single-asset portfolio returns."""
        n = len(sample_prices)
        weights = [1.0] + [0.0] * (n - 1)
        returns = _compute_portfolio_daily_returns(sample_prices, weights)

        # Should match first asset's log returns
        import math
        expected = [
            math.log(sample_prices[0][i] / sample_prices[0][i - 1])
            for i in range(1, len(sample_prices[0]))
        ]
        for r, e in zip(returns, expected):
            assert r == pytest.approx(e, abs=1e-6)

    def test_returns_length(self, sample_prices):
        """Test that returns have correct length."""
        weights = [1.0 / len(sample_prices)] * len(sample_prices)
        returns = _compute_portfolio_daily_returns(sample_prices, weights)
        assert len(returns) == len(sample_prices[0]) - 1


class TestBacktestError:
    """Tests for BacktestError exception."""

    def test_error_message(self):
        """Test error message and operation."""
        error = BacktestError("Test error", operation="test_op")
        assert error.message == "Test error"
        assert error.operation == "test_op"
        assert str(error) == "Test error"

    def test_error_without_operation(self):
        """Test error without operation."""
        error = BacktestError("Simple error")
        assert error.message == "Simple error"
        assert error.operation is None
