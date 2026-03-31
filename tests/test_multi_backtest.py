"""
Tests for the multi-strategy backtest engine.

Tests:
- Multi-strategy backtest returns all strategies
- Equal-weight benchmark included
- Ranking by Sharpe ratio
- Strategy failure graceful handling
- _std helper function
- Save / no-save behavior
- Missing data raises BacktestError
"""

import math
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.backtest import (
    BacktestError,
    MULTI_STRATEGIES,
    _std,
    run_multi_backtest,
)


# =============================================================================
# Fixtures
# =============================================================================

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]


def _make_raw_data(n_days: int = 120) -> dict:
    """Build raw data in the format align_data_by_date expects."""
    raw_data = {}
    for i, sym in enumerate(SYMBOLS):
        base = [100.0, 50.0, 10.0][i]
        records = []
        for d in range(n_days):
            records.append({
                "timestamp": f"2024-{(d // 28) + 1:02d}-{(d % 28) + 1:02d}",
                "open": base * (1 + 0.001 * d),
                "high": base * (1 + 0.001 * d) * 1.01,
                "low": base * (1 + 0.001 * d) * 0.99,
                "close": base * (1 + 0.001 * d + 0.01 * math.sin(d / 5)),
                "volume": 1000.0,
            })
        raw_data[sym] = records
    return raw_data


@pytest.fixture
def mock_storage():
    """MockStorage that returns data in the correct format."""
    storage = MagicMock()
    storage.load_raw.return_value = _make_raw_data()
    storage.save_output = MagicMock()
    return storage


# =============================================================================
# _std tests
# =============================================================================


class TestStd:
    """Tests for the _std helper."""

    def test_empty_list(self):
        assert _std([]) == 0.0

    def test_single_value(self):
        assert _std([5.0]) == 0.0

    def test_known_values(self):
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        result = _std(values)
        assert result == pytest.approx(2.138, abs=0.01)

    def test_identical_values(self):
        assert _std([3.0, 3.0, 3.0, 3.0]) == 0.0

    def test_two_values(self):
        result = _std([0.0, 2.0])
        expected = math.sqrt(2.0)
        assert result == pytest.approx(expected, abs=0.01)


# =============================================================================
# MULTI_STRATEGIES constant
# =============================================================================


class TestMultiStrategies:
    """Tests for the MULTI_STRATEGIES constant."""

    def test_has_five_strategies(self):
        assert len(MULTI_STRATEGIES) == 5

    def test_contains_max_sharpe(self):
        assert "max_sharpe" in MULTI_STRATEGIES

    def test_contains_hrp(self):
        assert "hrp" in MULTI_STRATEGIES

    def test_contains_risk_parity(self):
        assert "risk_parity" in MULTI_STRATEGIES

    def test_contains_min_variance(self):
        assert "min_variance" in MULTI_STRATEGIES

    def test_contains_max_diversification(self):
        assert "max_diversification" in MULTI_STRATEGIES


# =============================================================================
# run_multi_backtest tests
# =============================================================================


class TestRunMultiBacktest:
    """Tests for run_multi_backtest."""

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_returns_all_strategies(self, mock_opt, mock_cfg, mock_storage):
        """All requested strategies appear in results."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        for strat in MULTI_STRATEGIES:
            assert strat in result["strategies"]

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_equal_weight_benchmark(self, mock_opt, mock_cfg, mock_storage):
        """Equal-weight benchmark is included."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        assert "equal_weight" in result
        assert "cumulative_values" in result["equal_weight"]
        assert "total_return" in result["equal_weight"]

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_ranking_present(self, mock_opt, mock_cfg, mock_storage):
        """Ranking list is populated."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        assert "ranking" in result
        assert len(result["ranking"]) > 0
        assert result["ranking"][0]["rank"] == 1

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_ranking_sorted_by_sharpe(self, mock_opt, mock_cfg, mock_storage):
        """Ranking is sorted descending by Sharpe ratio."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        sharpes = [r["sharpe_ratio"] for r in result["ranking"]]
        assert sharpes == sorted(sharpes, reverse=True)

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_config_in_result(self, mock_opt, mock_cfg, mock_storage):
        """Config block present with expected keys."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        assert result["config"]["train_window"] == 20
        assert result["config"]["test_window"] == 10
        assert result["method"] == "multi_backtest"

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_symbols_in_result(self, mock_opt, mock_cfg, mock_storage):
        """Symbols list is included."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        assert "symbols" in result
        assert len(result["symbols"]) == 3

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_n_windows_positive(self, mock_opt, mock_cfg, mock_storage):
        """Number of windows is positive."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        assert result["n_windows"] > 0

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_cumulative_values_start_at_one(self, mock_opt, mock_cfg, mock_storage):
        """Cumulative value series starts at 1.0."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        for strat in MULTI_STRATEGIES:
            sr = result["strategies"][strat]
            if sr["cumulative_values"]:
                assert sr["cumulative_values"][0] == 1.0

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_strategy_failure_graceful(self, mock_opt, mock_cfg, mock_storage):
        """A failing strategy returns error entry, others still succeed."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )

        def side_effect(strategy, mean_returns, cov_matrix, risk_free_rate=0.05):
            if strategy == "hrp":
                raise ValueError("HRP failed")
            return [0.4, 0.3, 0.3]

        mock_opt.side_effect = side_effect

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        assert result["strategies"]["hrp"]["error"] is not None
        for strat in ["max_sharpe", "risk_parity", "min_variance", "max_diversification"]:
            assert result["strategies"][strat]["error"] is None

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_custom_strategy_list(self, mock_opt, mock_cfg, mock_storage):
        """Can pass a custom subset of strategies."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20,
            test_window=10,
            strategies=["max_sharpe", "min_variance"],
            storage=mock_storage,
            save=False,
        )

        assert "max_sharpe" in result["strategies"]
        assert "min_variance" in result["strategies"]
        assert "hrp" not in result["strategies"]

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_save_calls_storage(self, mock_opt, mock_cfg, mock_storage):
        """When save=True, result is saved to storage."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=True
        )

        mock_storage.save_output.assert_called_once()
        args = mock_storage.save_output.call_args[0]
        assert args[1] == "backtest_multi"

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_no_save(self, mock_opt, mock_cfg, mock_storage):
        """When save=False, storage.save_output is not called."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        mock_storage.save_output.assert_not_called()

    @patch("src.pipeline.backtest.load_config")
    def test_missing_data_raises_error(self, mock_cfg, mock_storage):
        """Missing raw data raises BacktestError."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_storage.load_raw.side_effect = FileNotFoundError("No data")

        with pytest.raises(BacktestError, match="Failed to load raw data"):
            run_multi_backtest(storage=mock_storage, save=False)

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_strategy_result_keys(self, mock_opt, mock_cfg, mock_storage):
        """Each strategy result has required keys."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        expected_keys = {
            "cumulative_values", "total_return", "annualized_return",
            "volatility", "sharpe_ratio", "n_periods", "error",
        }
        for strat in MULTI_STRATEGIES:
            assert set(result["strategies"][strat].keys()) == expected_keys

    @patch("src.pipeline.backtest.load_config")
    @patch("src.pipeline.backtest.optimize_weights")
    def test_equal_weight_keys(self, mock_opt, mock_cfg, mock_storage):
        """Equal-weight benchmark has expected keys."""
        mock_cfg.return_value = MagicMock(
            storage_backend="parquet", trading_days_per_year=365
        )
        mock_opt.return_value = [0.4, 0.3, 0.3]

        result = run_multi_backtest(
            train_window=20, test_window=10, storage=mock_storage, save=False
        )

        eq = result["equal_weight"]
        assert "cumulative_values" in eq
        assert "total_return" in eq
        assert "annualized_return" in eq
        assert "volatility" in eq
        assert "sharpe_ratio" in eq
