"""Tests for portfolio performance attribution module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.attribution import (
    AttributionError,
    analyze_performance_attribution,
    compute_attribution,
)


class TestComputeAttribution:
    """Tests for compute_attribution."""

    def test_empty_weights(self):
        result = compute_attribution({}, {"BTCUSDT": 0.10})
        assert result["contributions"] == []
        assert result["portfolio_return"] == 0.0
        assert result["n_assets"] == 0

    def test_single_asset(self):
        result = compute_attribution(
            {"BTCUSDT": 1.0}, {"BTCUSDT": 0.15}
        )
        assert result["portfolio_return"] == pytest.approx(0.15, abs=1e-4)
        assert result["n_assets"] == 1
        assert result["contributions"][0]["contribution"] == pytest.approx(0.15, abs=1e-4)

    def test_two_assets_contribution(self):
        result = compute_attribution(
            {"BTCUSDT": 0.6, "ETHUSDT": 0.4},
            {"BTCUSDT": 0.10, "ETHUSDT": -0.05},
        )
        # 0.6 * 0.10 + 0.4 * (-0.05) = 0.06 - 0.02 = 0.04
        assert result["portfolio_return"] == pytest.approx(0.04, abs=1e-4)

    def test_sorted_best_first(self):
        result = compute_attribution(
            {"A": 0.5, "B": 0.3, "C": 0.2},
            {"A": 0.10, "B": -0.05, "C": 0.20},
        )
        contribs = [c["contribution"] for c in result["contributions"]]
        assert contribs == sorted(contribs, reverse=True)

    def test_pct_contribution_sums_to_one(self):
        result = compute_attribution(
            {"A": 0.5, "B": 0.3, "C": 0.2},
            {"A": 0.10, "B": 0.05, "C": 0.20},
        )
        total_pct = sum(c["pct_contribution"] for c in result["contributions"])
        assert total_pct == pytest.approx(1.0, abs=0.01)

    def test_missing_return_defaults_to_zero(self):
        result = compute_attribution(
            {"BTCUSDT": 0.5, "UNKNOWN": 0.5},
            {"BTCUSDT": 0.10},
        )
        unknown = next(c for c in result["contributions"] if c["symbol"] == "UNKNOWN")
        assert unknown["asset_return"] == 0.0
        assert unknown["contribution"] == 0.0

    def test_output_keys(self):
        result = compute_attribution(
            {"BTCUSDT": 1.0}, {"BTCUSDT": 0.10}
        )
        assert "contributions" in result
        assert "portfolio_return" in result
        assert "n_assets" in result
        c = result["contributions"][0]
        assert "symbol" in c
        assert "weight" in c
        assert "asset_return" in c
        assert "contribution" in c
        assert "pct_contribution" in c

    def test_zero_portfolio_return_pct(self):
        # If portfolio return is zero, pct_contribution should be 0
        result = compute_attribution(
            {"A": 0.5, "B": 0.5},
            {"A": 0.10, "B": -0.10},
        )
        assert result["portfolio_return"] == pytest.approx(0.0, abs=1e-4)
        for c in result["contributions"]:
            assert c["pct_contribution"] == 0.0


class TestAnalyzePerformanceAttribution:
    """Tests for analyze_performance_attribution."""

    @pytest.fixture()
    def mock_storage(self):
        storage = MagicMock()
        storage.load_output.return_value = {
            "weights": {
                "BTCUSDT": 0.40,
                "ETHUSDT": 0.30,
                "SOLUSDT": 0.30,
            },
        }
        storage.load_processed.return_value = {
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "values": [
                [0.02, 0.01, -0.01],
                [0.03, -0.02, 0.01],
                [-0.01, 0.02, 0.03],
            ],
        }
        return storage

    def test_output_keys(self, mock_storage):
        result = analyze_performance_attribution(storage=mock_storage, save=False)
        assert "contributions" in result
        assert "portfolio_return" in result
        assert "top_contributors" in result
        assert "bottom_contributors" in result
        assert "portfolio_key" in result

    def test_all_assets_attributed(self, mock_storage):
        result = analyze_performance_attribution(storage=mock_storage, save=False)
        symbols = {c["symbol"] for c in result["contributions"]}
        assert symbols == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    def test_save_to_storage(self, mock_storage):
        analyze_performance_attribution(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        assert mock_storage.save_output.call_args[0][0] == "attribution"

    def test_missing_portfolio_raises(self):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(AttributionError, match="not found"):
            analyze_performance_attribution(storage=storage)

    def test_empty_weights_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {}}
        with pytest.raises(AttributionError, match="no weights"):
            analyze_performance_attribution(storage=storage)

    def test_missing_returns_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {"BTCUSDT": 1.0}}
        storage.load_processed.side_effect = FileNotFoundError("not found")
        with pytest.raises(AttributionError, match="Returns data not found"):
            analyze_performance_attribution(storage=storage)

    def test_empty_returns_raises(self):
        storage = MagicMock()
        storage.load_output.return_value = {"weights": {"BTCUSDT": 1.0}}
        storage.load_processed.return_value = {"symbols": [], "values": []}
        with pytest.raises(AttributionError, match="Returns data is empty"):
            analyze_performance_attribution(storage=storage)

    def test_top_contributors_length(self, mock_storage):
        result = analyze_performance_attribution(storage=mock_storage, save=False)
        assert len(result["top_contributors"]) == 3

    def test_portfolio_return_nonzero(self, mock_storage):
        result = analyze_performance_attribution(storage=mock_storage, save=False)
        assert result["portfolio_return"] != 0.0
