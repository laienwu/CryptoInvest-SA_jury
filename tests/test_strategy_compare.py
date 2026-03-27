"""Tests for strategy comparison module."""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.strategy_compare import StrategyCompareError, compare_strategies

# ---------------------------------------------------------------------------
# Canned results
# ---------------------------------------------------------------------------

WEIGHTS = {"BTCUSDT": 0.5, "ETHUSDT": 0.3, "BNBUSDT": 0.2}


def _make_result(expected_return: float, volatility: float, sharpe_ratio: float) -> dict:
    return {
        "weights": dict(WEIGHTS),
        "expected_return": expected_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
    }


CANNED = {
    "max_sharpe": _make_result(0.15, 0.20, 0.75),
    "hrp": _make_result(0.12, 0.18, 0.67),
    "risk_parity": _make_result(0.10, 0.15, 0.67),
    "min_variance": _make_result(0.08, 0.12, 0.67),
    "max_diversification": _make_result(0.13, 0.17, 0.76),
    "black_litterman": _make_result(0.14, 0.19, 0.74),
}

# Patch targets (where the functions are imported in strategy_compare)
_P_OPT = "src.pipeline.strategy_compare.optimize_portfolio"
_P_HRP = "src.pipeline.strategy_compare.analyze_hrp"
_P_RP = "src.pipeline.strategy_compare.optimize_risk_parity"
_P_MV = "src.pipeline.strategy_compare.analyze_min_variance"
_P_MD = "src.pipeline.strategy_compare.analyze_max_diversification"
_P_BL = "src.pipeline.strategy_compare.analyze_black_litterman"


def _mock_storage() -> MagicMock:
    return MagicMock()


def _patch_all_success():
    """Return a list of patch decorators for all 6 strategies succeeding."""
    return [
        patch(_P_BL, return_value=CANNED["black_litterman"]),
        patch(_P_MD, return_value=CANNED["max_diversification"]),
        patch(_P_MV, return_value=CANNED["min_variance"]),
        patch(_P_RP, return_value=CANNED["risk_parity"]),
        patch(_P_HRP, return_value=CANNED["hrp"]),
        patch(_P_OPT, return_value=CANNED["max_sharpe"]),
    ]


def _apply_patches(patches: list):
    """Apply all patches and return the mocks."""
    mocks = []
    for p in patches:
        mocks.append(p.start())
    return mocks


def _stop_patches(patches: list):
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# TestCompareStrategies
# ---------------------------------------------------------------------------


class TestCompareStrategies:
    """Tests for compare_strategies function."""

    def setup_method(self):
        self.patches = _patch_all_success()
        self.mocks = _apply_patches(self.patches)
        self.storage = _mock_storage()

    def teardown_method(self):
        _stop_patches(self.patches)

    def test_all_strategies_present(self):
        result = compare_strategies(storage=self.storage)
        assert len(result["strategies"]) == 6

    def test_ranking_by_sharpe(self):
        result = compare_strategies(storage=self.storage)
        strategies = result["strategies"]
        ranked = [s for s in strategies if s["rank"] is not None]
        # Max Div (0.76) -> rank 1, Max Sharpe (0.75) -> rank 2
        assert ranked[0]["name"] == "Max Diversification"
        assert ranked[0]["rank"] == 1
        assert ranked[1]["name"] == "Max Sharpe"
        assert ranked[1]["rank"] == 2
        # Black-Litterman (0.74) -> rank 3
        assert ranked[2]["name"] == "Black-Litterman"
        assert ranked[2]["rank"] == 3

    def test_best_strategy_correct(self):
        result = compare_strategies(storage=self.storage)
        assert result["best_strategy"] == "Max Diversification"

    def test_worst_strategy_correct(self):
        result = compare_strategies(storage=self.storage)
        # Three strategies tied at 0.67; last in sorted order depends on
        # stable sort — the last of the three tied is the worst.
        worst = result["worst_strategy"]
        assert worst in ("HRP", "Risk Parity", "Min Variance")

    def test_symbols_from_weights(self):
        result = compare_strategies(storage=self.storage)
        assert set(result["symbols"]) == {"BTCUSDT", "ETHUSDT", "BNBUSDT"}

    def test_n_assets_correct(self):
        result = compare_strategies(storage=self.storage)
        assert result["n_assets"] == 3

    def test_method_field(self):
        result = compare_strategies(storage=self.storage)
        assert result["method"] == "strategy_comparison"

    def test_n_strategies_field(self):
        result = compare_strategies(storage=self.storage)
        assert result["n_strategies"] == 6

    def test_saves_to_storage(self):
        compare_strategies(storage=self.storage, save=True)
        self.storage.save_output.assert_called_once()
        args = self.storage.save_output.call_args
        assert args[0][1] == "strategy_comparison"

    def test_no_save(self):
        compare_strategies(storage=self.storage, save=False)
        self.storage.save_output.assert_not_called()

    def test_one_strategy_fails_gracefully(self):
        _stop_patches(self.patches)
        patches = _patch_all_success()
        # Make HRP fail
        patches[4] = patch(_P_HRP, side_effect=RuntimeError("HRP boom"))
        _apply_patches(patches)

        result = compare_strategies(storage=self.storage)
        names = [s["name"] for s in result["strategies"]]
        assert "HRP" in names
        # 5 successful + 1 failed
        successful = [s for s in result["strategies"] if s["error"] is None]
        assert len(successful) == 5

        _stop_patches(patches)
        # Re-apply original patches for teardown
        self.patches = _patch_all_success()
        self.mocks = _apply_patches(self.patches)

    def test_all_strategies_fail_raises(self):
        _stop_patches(self.patches)
        fail_patches = [
            patch(_P_BL, side_effect=RuntimeError("fail")),
            patch(_P_MD, side_effect=RuntimeError("fail")),
            patch(_P_MV, side_effect=RuntimeError("fail")),
            patch(_P_RP, side_effect=RuntimeError("fail")),
            patch(_P_HRP, side_effect=RuntimeError("fail")),
            patch(_P_OPT, side_effect=RuntimeError("fail")),
        ]
        _apply_patches(fail_patches)

        with pytest.raises(StrategyCompareError, match="All strategies failed"):
            compare_strategies(storage=self.storage)

        _stop_patches(fail_patches)
        # Re-apply original patches for teardown
        self.patches = _patch_all_success()
        self.mocks = _apply_patches(self.patches)

    def test_failed_strategy_has_null_fields(self):
        _stop_patches(self.patches)
        patches = _patch_all_success()
        patches[4] = patch(_P_HRP, side_effect=RuntimeError("boom"))
        _apply_patches(patches)

        result = compare_strategies(storage=self.storage)
        hrp = next(s for s in result["strategies"] if s["name"] == "HRP")
        assert hrp["weights"] is None
        assert hrp["expected_return"] is None
        assert hrp["volatility"] is None
        assert hrp["sharpe_ratio"] is None
        assert hrp["rank"] is None

        _stop_patches(patches)
        self.patches = _patch_all_success()
        self.mocks = _apply_patches(self.patches)

    def test_failed_strategy_has_error_message(self):
        _stop_patches(self.patches)
        patches = _patch_all_success()
        patches[4] = patch(_P_HRP, side_effect=RuntimeError("HRP boom"))
        _apply_patches(patches)

        result = compare_strategies(storage=self.storage)
        hrp = next(s for s in result["strategies"] if s["name"] == "HRP")
        assert hrp["error"] == "HRP boom"

        _stop_patches(patches)
        self.patches = _patch_all_success()
        self.mocks = _apply_patches(self.patches)

    def test_default_storage(self):
        _stop_patches(self.patches)
        patches = _patch_all_success()
        _apply_patches(patches)

        with patch("src.pipeline.strategy_compare.get_storage") as mock_get:
            mock_get.return_value = _mock_storage()
            result = compare_strategies(storage=None, save=False)
            mock_get.assert_called_once()
            assert result["n_strategies"] == 6

        _stop_patches(patches)
        self.patches = _patch_all_success()
        self.mocks = _apply_patches(self.patches)

    def test_successful_strategies_have_weights(self):
        result = compare_strategies(storage=self.storage)
        successful = [s for s in result["strategies"] if s["error"] is None]
        for s in successful:
            assert s["weights"] is not None
            assert isinstance(s["weights"], dict)

    def test_successful_strategies_have_sharpe(self):
        result = compare_strategies(storage=self.storage)
        successful = [s for s in result["strategies"] if s["error"] is None]
        for s in successful:
            assert s["sharpe_ratio"] is not None
            assert s["sharpe_ratio"] > 0

    def test_ranks_are_contiguous(self):
        result = compare_strategies(storage=self.storage)
        ranks = sorted(s["rank"] for s in result["strategies"] if s["rank"] is not None)
        assert ranks == list(range(1, 7))

    def test_strategy_names(self):
        result = compare_strategies(storage=self.storage)
        names = {s["name"] for s in result["strategies"]}
        expected = {
            "Max Sharpe",
            "HRP",
            "Risk Parity",
            "Min Variance",
            "Max Diversification",
            "Black-Litterman",
        }
        assert names == expected

    def test_save_output_data_is_dict(self):
        compare_strategies(storage=self.storage, save=True)
        args = self.storage.save_output.call_args
        saved_data = args[0][0]
        assert isinstance(saved_data, dict)
        assert "strategies" in saved_data

    def test_multiple_failures_partial_result(self):
        _stop_patches(self.patches)
        patches = [
            patch(_P_BL, side_effect=RuntimeError("fail")),
            patch(_P_MD, side_effect=RuntimeError("fail")),
            patch(_P_MV, return_value=CANNED["min_variance"]),
            patch(_P_RP, return_value=CANNED["risk_parity"]),
            patch(_P_HRP, side_effect=RuntimeError("fail")),
            patch(_P_OPT, return_value=CANNED["max_sharpe"]),
        ]
        _apply_patches(patches)

        result = compare_strategies(storage=self.storage, save=False)
        successful = [s for s in result["strategies"] if s["error"] is None]
        failed = [s for s in result["strategies"] if s["error"] is not None]
        assert len(successful) == 3
        assert len(failed) == 3

        _stop_patches(patches)
        self.patches = _patch_all_success()
        self.mocks = _apply_patches(self.patches)


# ---------------------------------------------------------------------------
# TestStrategyCompareError
# ---------------------------------------------------------------------------


class TestStrategyCompareError:
    """Tests for StrategyCompareError exception."""

    def test_message(self):
        err = StrategyCompareError("something went wrong")
        assert err.message == "something went wrong"
        assert str(err) == "something went wrong"

    def test_operation(self):
        err = StrategyCompareError("fail", operation="custom_op")
        assert err.operation == "custom_op"

    def test_default_operation(self):
        err = StrategyCompareError("fail")
        assert err.operation == "strategy_compare"
