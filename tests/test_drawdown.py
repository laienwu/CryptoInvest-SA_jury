"""Tests for portfolio drawdown analysis module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.drawdown import (
    DrawdownError,
    _compute_drawdown_series,
    _identify_drawdown_periods,
    analyze_portfolio_drawdowns,
    compute_drawdown_analysis,
)


class TestComputeDrawdownSeries:
    """Tests for _compute_drawdown_series."""

    def test_empty_values(self):
        assert _compute_drawdown_series([]) == []

    def test_monotonic_increase(self):
        result = _compute_drawdown_series([1.0, 1.1, 1.2, 1.3])
        assert all(d == 0.0 for d in result)

    def test_single_drop(self):
        result = _compute_drawdown_series([1.0, 0.8, 0.9, 1.0])
        assert result[0] == 0.0
        assert result[1] == pytest.approx(-0.2, abs=1e-6)
        assert result[2] == pytest.approx(-0.1, abs=1e-6)
        assert result[3] == 0.0

    def test_new_peak_resets(self):
        result = _compute_drawdown_series([1.0, 1.2, 1.0])
        assert result[0] == 0.0
        assert result[1] == 0.0
        # 1.0 from peak 1.2 = -0.1667
        assert result[2] == pytest.approx(-1 / 6, abs=1e-4)

    def test_length_matches_input(self):
        vals = [1.0, 0.9, 0.8, 0.95, 1.1]
        assert len(_compute_drawdown_series(vals)) == len(vals)


class TestIdentifyDrawdownPeriods:
    """Tests for _identify_drawdown_periods."""

    def test_no_drawdowns(self):
        series = [0.0, 0.0, 0.0, 0.0]
        assert _identify_drawdown_periods(series) == []

    def test_single_period(self):
        series = [0.0, -0.1, -0.2, -0.1, 0.0]
        periods = _identify_drawdown_periods(series)
        assert len(periods) == 1
        assert periods[0]["start_idx"] == 1
        assert periods[0]["end_idx"] == 3
        assert periods[0]["max_drawdown"] == pytest.approx(-0.2)
        assert periods[0]["duration"] == 3
        assert periods[0]["recovered"] is True

    def test_two_periods(self):
        series = [0.0, -0.1, 0.0, -0.05, 0.0]
        periods = _identify_drawdown_periods(series)
        assert len(periods) == 2

    def test_unrecovered_period(self):
        series = [0.0, -0.1, -0.15, -0.1]
        periods = _identify_drawdown_periods(series)
        assert len(periods) == 1
        assert periods[0]["recovered"] is False
        assert "recovery_idx" not in periods[0]

    def test_with_dates(self):
        series = [0.0, -0.1, -0.2, 0.0]
        dates = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"]
        periods = _identify_drawdown_periods(series, dates)
        assert periods[0]["start_date"] == "2025-01-02"
        assert periods[0]["trough_date"] == "2025-01-03"
        assert periods[0]["recovery_date"] == "2025-01-04"

    def test_recovery_duration(self):
        series = [0.0, -0.1, -0.2, -0.1, -0.05, 0.0]
        periods = _identify_drawdown_periods(series)
        # Trough at idx 2, recovery at idx 5
        assert periods[0]["recovery_duration"] == 3


class TestComputeDrawdownAnalysis:
    """Tests for compute_drawdown_analysis."""

    def test_empty_values(self):
        result = compute_drawdown_analysis([])
        assert result["drawdown_series"] == []
        assert result["periods"] == []
        assert result["summary"]["max_drawdown"] == 0.0

    def test_summary_keys(self):
        result = compute_drawdown_analysis([1.0, 0.8, 0.9, 1.0, 0.7])
        summary = result["summary"]
        assert "max_drawdown" in summary
        assert "avg_drawdown" in summary
        assert "n_periods" in summary
        assert "longest_duration" in summary
        assert "current_drawdown" in summary
        assert "time_in_drawdown_pct" in summary

    def test_max_drawdown_correct(self):
        # Peak 1.0, trough 0.7 => -0.3
        result = compute_drawdown_analysis([1.0, 0.8, 0.7, 0.9, 1.0])
        assert result["summary"]["max_drawdown"] == pytest.approx(-0.3, abs=1e-4)

    def test_strategy_name(self):
        result = compute_drawdown_analysis([1.0, 0.9], strategy_name="my_strat")
        assert result["strategy"] == "my_strat"

    def test_time_in_drawdown(self):
        # [1.0, 0.9, 0.8, 1.0, 1.1] => 2 out of 5 in drawdown
        result = compute_drawdown_analysis([1.0, 0.9, 0.8, 1.0, 1.1])
        assert result["summary"]["time_in_drawdown_pct"] == pytest.approx(0.4, abs=0.01)

    def test_current_drawdown_when_at_peak(self):
        result = compute_drawdown_analysis([1.0, 0.9, 1.1])
        assert result["summary"]["current_drawdown"] == 0.0

    def test_current_drawdown_when_in_drawdown(self):
        result = compute_drawdown_analysis([1.0, 1.2, 1.0])
        assert result["summary"]["current_drawdown"] < 0


class TestAnalyzePortfolioDrawdowns:
    """Tests for analyze_portfolio_drawdowns."""

    @pytest.fixture()
    def mock_storage(self):
        storage = MagicMock()
        storage.load_output.return_value = {
            "cumulative_values": {
                "dates": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
                "strategy": [1.0, 0.95, 0.90, 1.05],
                "equal_weight": [1.0, 0.98, 0.96, 1.02],
                "btc_only": [1.0, 0.85, 0.80, 0.95],
            }
        }
        return storage

    def test_output_keys(self, mock_storage):
        result = analyze_portfolio_drawdowns(storage=mock_storage, save=False)
        assert "analyses" in result
        assert "comparison" in result
        assert "n_strategies" in result

    def test_all_strategies_analyzed(self, mock_storage):
        result = analyze_portfolio_drawdowns(storage=mock_storage, save=False)
        assert "strategy" in result["analyses"]
        assert "equal_weight" in result["analyses"]
        assert "btc_only" in result["analyses"]
        assert result["n_strategies"] == 3

    def test_comparison_sorted_worst_first(self, mock_storage):
        result = analyze_portfolio_drawdowns(storage=mock_storage, save=False)
        dd_values = [c["max_drawdown"] for c in result["comparison"]]
        assert dd_values == sorted(dd_values)

    def test_btc_only_worst_drawdown(self, mock_storage):
        result = analyze_portfolio_drawdowns(storage=mock_storage, save=False)
        assert result["comparison"][0]["strategy"] == "btc_only"

    def test_save_to_storage(self, mock_storage):
        analyze_portfolio_drawdowns(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        assert mock_storage.save_output.call_args[0][1] == "drawdown"

    def test_missing_backtest_raises(self):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(DrawdownError, match="not found"):
            analyze_portfolio_drawdowns(storage=storage)

    def test_empty_cumulative_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"cumulative_values": {}}
        with pytest.raises(DrawdownError):
            analyze_portfolio_drawdowns(storage=storage)

    def test_no_cumulative_key_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {}
        with pytest.raises(DrawdownError, match="no cumulative_values"):
            analyze_portfolio_drawdowns(storage=storage)

    def test_only_dates_no_strategies_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {
            "cumulative_values": {"dates": ["2025-01-01"]}
        }
        with pytest.raises(DrawdownError, match="No strategy series"):
            analyze_portfolio_drawdowns(storage=storage)
