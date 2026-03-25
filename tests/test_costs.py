"""Tests for the transaction cost model module."""

import pytest

from src.pipeline.costs import (
    CostError,
    compute_cost_adjusted_returns,
    compute_rebalance_costs,
    estimate_trade_cost,
    analyze_costs,
    DEFAULT_MAKER_FEE,
    DEFAULT_TAKER_FEE,
    DEFAULT_SLIPPAGE_BPS,
)


# ---------------------------------------------------------------------------
# estimate_trade_cost
# ---------------------------------------------------------------------------

class TestEstimateTradeCost:
    def test_basic_cost(self):
        result = estimate_trade_cost(1000.0)
        assert result["fee_cost"] == pytest.approx(1.0, abs=0.01)  # 0.1%
        assert result["slippage_cost"] == pytest.approx(0.5, abs=0.01)  # 5bps
        assert result["total_cost"] == pytest.approx(1.5, abs=0.01)
        assert result["cost_pct"] == pytest.approx(0.0015, abs=1e-5)

    def test_zero_trade_value(self):
        result = estimate_trade_cost(0.0)
        assert result["fee_cost"] == 0.0
        assert result["slippage_cost"] == 0.0
        assert result["total_cost"] == 0.0
        assert result["cost_pct"] == 0.0

    def test_negative_trade_value_uses_abs(self):
        pos = estimate_trade_cost(1000.0)
        neg = estimate_trade_cost(-1000.0)
        assert pos["fee_cost"] == neg["fee_cost"]
        assert pos["total_cost"] == neg["total_cost"]

    def test_custom_fee_rate(self):
        result = estimate_trade_cost(1000.0, fee_rate=0.002)
        assert result["fee_cost"] == pytest.approx(2.0, abs=0.01)

    def test_custom_slippage(self):
        result = estimate_trade_cost(10000.0, slippage_bps=10)
        assert result["slippage_cost"] == pytest.approx(10.0, abs=0.01)

    def test_large_trade(self):
        result = estimate_trade_cost(1_000_000.0)
        assert result["total_cost"] > 0
        assert result["cost_pct"] == pytest.approx(0.0015, abs=1e-5)

    def test_return_keys(self):
        result = estimate_trade_cost(500.0)
        assert set(result.keys()) == {"fee_cost", "slippage_cost", "total_cost", "cost_pct"}


# ---------------------------------------------------------------------------
# compute_rebalance_costs
# ---------------------------------------------------------------------------

class TestComputeRebalanceCosts:
    def test_no_change_needed(self):
        weights = {"BTC": 0.5, "ETH": 0.5}
        result = compute_rebalance_costs(weights, weights)
        assert result["n_trades"] == 0
        assert result["total_cost_usd"] == 0.0

    def test_full_rebalance(self):
        current = {"BTC": 1.0}
        target = {"ETH": 1.0}
        result = compute_rebalance_costs(current, target, portfolio_value=10000.0)
        # BTC sold (1.0 -> 0.0 = $10k), ETH bought (0.0 -> 1.0 = $10k)
        assert result["n_trades"] == 2
        assert result["total_turnover_usd"] == pytest.approx(20000.0, abs=1)
        assert result["total_cost_usd"] > 0

    def test_partial_rebalance(self):
        current = {"BTC": 0.6, "ETH": 0.4}
        target = {"BTC": 0.5, "ETH": 0.5}
        result = compute_rebalance_costs(current, target, portfolio_value=10000.0)
        assert result["n_trades"] == 2
        # 10% change on $10k = $1k per asset
        assert result["total_turnover_usd"] == pytest.approx(2000.0, abs=1)

    def test_trades_sorted_by_value(self):
        current = {"A": 0.5, "B": 0.3, "C": 0.2}
        target = {"A": 0.2, "B": 0.6, "C": 0.2}
        result = compute_rebalance_costs(current, target, portfolio_value=10000.0)
        values = [t["trade_value_usd"] for t in result["trades"]]
        assert values == sorted(values, reverse=True)

    def test_buy_sell_labels(self):
        current = {"BTC": 0.8, "ETH": 0.2}
        target = {"BTC": 0.3, "ETH": 0.7}
        result = compute_rebalance_costs(current, target)
        actions = {t["symbol"]: t["action"] for t in result["trades"]}
        assert actions["BTC"] == "SELL"
        assert actions["ETH"] == "BUY"

    def test_tiny_changes_ignored(self):
        current = {"BTC": 0.5000001, "ETH": 0.4999999}
        target = {"BTC": 0.5, "ETH": 0.5}
        result = compute_rebalance_costs(current, target, portfolio_value=10000.0)
        assert result["n_trades"] == 0

    def test_cost_pct_of_portfolio(self):
        current = {"BTC": 1.0}
        target = {"ETH": 1.0}
        result = compute_rebalance_costs(current, target, portfolio_value=10000.0)
        assert result["cost_pct_of_portfolio"] > 0
        assert result["cost_pct_of_portfolio"] < 1.0

    def test_zero_portfolio_value(self):
        result = compute_rebalance_costs({"BTC": 1.0}, {"ETH": 1.0}, portfolio_value=0.0)
        assert result["cost_pct_of_portfolio"] == 0.0

    def test_return_keys(self):
        result = compute_rebalance_costs({"BTC": 0.5}, {"BTC": 0.5})
        expected = {
            "trades", "total_cost_usd", "total_turnover_usd",
            "cost_pct_of_portfolio", "n_trades", "fee_rate",
            "slippage_bps", "portfolio_value",
        }
        assert set(result.keys()) == expected


# ---------------------------------------------------------------------------
# compute_cost_adjusted_returns
# ---------------------------------------------------------------------------

class TestComputeCostAdjustedReturns:
    def test_basic_adjustment(self):
        result = compute_cost_adjusted_returns(
            gross_return=0.10, n_rebalances_per_year=12,
            cost_per_rebalance_pct=0.001, volatility=0.20,
        )
        assert result["annual_cost"] == pytest.approx(0.012, abs=1e-5)
        assert result["net_return"] == pytest.approx(0.088, abs=1e-5)
        assert result["gross_sharpe"] == pytest.approx(0.5, abs=0.01)
        assert result["net_sharpe"] < result["gross_sharpe"]
        assert result["sharpe_drag"] > 0

    def test_zero_volatility(self):
        result = compute_cost_adjusted_returns(0.10, 12, 0.001, 0.0)
        assert result["gross_sharpe"] == 0.0
        assert result["net_sharpe"] == 0.0

    def test_zero_rebalances(self):
        result = compute_cost_adjusted_returns(0.10, 0, 0.001, 0.20)
        assert result["annual_cost"] == 0.0
        assert result["net_return"] == result["gross_return"]

    def test_high_cost_negative_net(self):
        result = compute_cost_adjusted_returns(0.05, 52, 0.002, 0.20)
        # 52 * 0.002 = 0.104 > 0.05
        assert result["net_return"] < 0

    def test_return_keys(self):
        result = compute_cost_adjusted_returns(0.10, 12, 0.001, 0.20)
        expected = {
            "gross_return", "net_return", "annual_cost",
            "gross_sharpe", "net_sharpe", "sharpe_drag",
            "n_rebalances_per_year", "cost_per_rebalance",
        }
        assert set(result.keys()) == expected


# ---------------------------------------------------------------------------
# analyze_costs (integration with storage)
# ---------------------------------------------------------------------------

class TestAnalyzeCosts:
    def _make_storage(self, portfolio=None):
        """Create a mock storage with portfolio data."""
        class MockStorage:
            def __init__(self, data):
                self._data = data
                self._saved = {}

            def load_output(self, key):
                if key not in self._data:
                    raise FileNotFoundError(f"Key {key} not found")
                return self._data[key]

            def save_output(self, key, data):
                self._saved[key] = data

        if portfolio is None:
            portfolio = {
                "weights": {"BTC": 0.6, "ETH": 0.3, "BNB": 0.1},
                "expected_return": 0.15,
                "volatility": 0.25,
            }
        return MockStorage({"weights": portfolio})

    def test_basic_analysis(self):
        storage = self._make_storage()
        result = analyze_costs(storage=storage, save=False)
        assert "rebalance_costs" in result
        assert "cost_adjusted_returns" in result
        assert result["portfolio_key"] == "weights"

    def test_custom_portfolio_key(self):
        storage = self._make_storage()
        storage._data["my_portfolio"] = storage._data["weights"]
        result = analyze_costs(portfolio_key="my_portfolio", storage=storage, save=False)
        assert result["portfolio_key"] == "my_portfolio"

    def test_missing_portfolio_raises(self):
        storage = self._make_storage()
        with pytest.raises(CostError, match="Portfolio not found"):
            analyze_costs(portfolio_key="nonexistent", storage=storage)

    def test_empty_weights_raises(self):
        storage = self._make_storage({"weights": {}, "expected_return": 0.1, "volatility": 0.2})
        with pytest.raises(CostError, match="no weights"):
            analyze_costs(storage=storage)

    def test_saves_when_requested(self):
        storage = self._make_storage()
        analyze_costs(storage=storage, save=True)
        assert "cost_analysis" in storage._saved

    def test_no_save_when_disabled(self):
        storage = self._make_storage()
        analyze_costs(storage=storage, save=False)
        assert "cost_analysis" not in storage._saved

    def test_custom_parameters(self):
        storage = self._make_storage()
        result = analyze_costs(
            storage=storage, save=False,
            portfolio_value=50000.0, fee_rate=0.002, slippage_bps=10,
        )
        rebalance = result["rebalance_costs"]
        assert rebalance["fee_rate"] == 0.002
        assert rebalance["slippage_bps"] == 10
        assert rebalance["portfolio_value"] == 50000.0


# ---------------------------------------------------------------------------
# CostError
# ---------------------------------------------------------------------------

class TestCostError:
    def test_message(self):
        err = CostError("test error")
        assert str(err) == "test error"
        assert err.operation == "costs"

    def test_custom_operation(self):
        err = CostError("fail", operation="load")
        assert err.operation == "load"


# ---------------------------------------------------------------------------
# Default constants
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_default_fees(self):
        assert DEFAULT_MAKER_FEE == 0.001
        assert DEFAULT_TAKER_FEE == 0.001

    def test_default_slippage(self):
        assert DEFAULT_SLIPPAGE_BPS == 5
