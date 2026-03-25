"""
Transaction cost model module.

Models trading costs that eat into portfolio returns:
- Exchange fees (Binance taker/maker fee tiers)
- Slippage estimate based on trade size and volume
- Spread cost estimate
- Net-of-cost portfolio returns and cost-adjusted Sharpe ratio

Output: data/output/cost_analysis.json
"""

import logging
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)

# Binance fee tiers (VIP 0 defaults)
DEFAULT_MAKER_FEE = 0.001  # 0.10%
DEFAULT_TAKER_FEE = 0.001  # 0.10%
DEFAULT_SLIPPAGE_BPS = 5   # 5 basis points


class CostError(Exception):
    """Error during cost analysis."""

    def __init__(self, message: str, *, operation: str = "costs") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def estimate_trade_cost(
    trade_value_usd: float,
    fee_rate: float = DEFAULT_TAKER_FEE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
) -> dict[str, float]:
    """
    Estimate total cost for a single trade.

    Args:
        trade_value_usd: Dollar value of the trade.
        fee_rate: Exchange fee as decimal (e.g., 0.001 = 0.10%).
        slippage_bps: Estimated slippage in basis points.

    Returns:
        Breakdown of fee cost, slippage cost, and total.
    """
    fee_cost = abs(trade_value_usd) * fee_rate
    slippage_cost = abs(trade_value_usd) * (slippage_bps / 10000)
    total = fee_cost + slippage_cost

    return {
        "fee_cost": round(fee_cost, 4),
        "slippage_cost": round(slippage_cost, 4),
        "total_cost": round(total, 4),
        "cost_pct": round(total / abs(trade_value_usd), 6) if trade_value_usd != 0 else 0.0,
    }


def compute_rebalance_costs(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    portfolio_value: float = 10000.0,
    fee_rate: float = DEFAULT_TAKER_FEE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
) -> dict[str, Any]:
    """
    Compute total cost of rebalancing from current to target weights.

    Args:
        current_weights: Current portfolio weights.
        target_weights: Target portfolio weights.
        portfolio_value: Total portfolio value in USD.
        fee_rate: Exchange fee rate.
        slippage_bps: Slippage in basis points.

    Returns:
        Per-asset trade costs, total cost, and cost as % of portfolio.
    """
    all_symbols = set(current_weights.keys()) | set(target_weights.keys())

    trades: list[dict[str, Any]] = []
    total_cost = 0.0
    total_turnover = 0.0

    for symbol in sorted(all_symbols):
        current = current_weights.get(symbol, 0.0)
        target = target_weights.get(symbol, 0.0)
        weight_change = target - current
        trade_value = abs(weight_change) * portfolio_value

        if trade_value < 0.01:
            continue

        cost = estimate_trade_cost(trade_value, fee_rate, slippage_bps)
        total_cost += cost["total_cost"]
        total_turnover += trade_value

        trades.append({
            "symbol": symbol,
            "weight_change": round(weight_change, 6),
            "trade_value_usd": round(trade_value, 2),
            "action": "BUY" if weight_change > 0 else "SELL",
            **cost,
        })

    trades.sort(key=lambda t: t["trade_value_usd"], reverse=True)

    return {
        "trades": trades,
        "total_cost_usd": round(total_cost, 4),
        "total_turnover_usd": round(total_turnover, 2),
        "cost_pct_of_portfolio": round(total_cost / portfolio_value, 6) if portfolio_value > 0 else 0.0,
        "n_trades": len(trades),
        "fee_rate": fee_rate,
        "slippage_bps": slippage_bps,
        "portfolio_value": portfolio_value,
    }


def compute_cost_adjusted_returns(
    gross_return: float,
    n_rebalances_per_year: int,
    cost_per_rebalance_pct: float,
    volatility: float,
) -> dict[str, Any]:
    """
    Compute net-of-cost return and Sharpe ratio.

    Args:
        gross_return: Annualized gross expected return.
        n_rebalances_per_year: How often the portfolio rebalances.
        cost_per_rebalance_pct: Cost per rebalance as fraction of portfolio.
        volatility: Annualized portfolio volatility.

    Returns:
        Net return, total annual cost, and cost-adjusted Sharpe.
    """
    annual_cost = n_rebalances_per_year * cost_per_rebalance_pct
    net_return = gross_return - annual_cost
    net_sharpe = net_return / volatility if volatility > 0 else 0.0
    gross_sharpe = gross_return / volatility if volatility > 0 else 0.0

    return {
        "gross_return": round(gross_return, 6),
        "net_return": round(net_return, 6),
        "annual_cost": round(annual_cost, 6),
        "gross_sharpe": round(gross_sharpe, 4),
        "net_sharpe": round(net_sharpe, 4),
        "sharpe_drag": round(gross_sharpe - net_sharpe, 4),
        "n_rebalances_per_year": n_rebalances_per_year,
        "cost_per_rebalance": round(cost_per_rebalance_pct, 6),
    }


def analyze_costs(
    portfolio_key: str = "weights",
    portfolio_value: float = 10000.0,
    n_rebalances: int = 12,
    fee_rate: float = DEFAULT_TAKER_FEE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run cost analysis on portfolio.

    Args:
        portfolio_key: Storage key for portfolio weights.
        portfolio_value: Total portfolio value.
        n_rebalances: Number of rebalances per year.
        fee_rate: Exchange fee rate.
        slippage_bps: Slippage in basis points.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Complete cost analysis with rebalance costs and net returns.

    Raises:
        CostError: If portfolio data is missing.
    """
    if storage is None:
        storage = get_storage()

    try:
        portfolio = storage.load_output(portfolio_key)
    except (StorageError, FileNotFoundError) as e:
        raise CostError(
            f"Portfolio not found (key={portfolio_key})", operation="load"
        ) from e

    weights = portfolio.get("weights", {})
    if not weights:
        raise CostError("Portfolio has no weights", operation="validate")

    exp_return = portfolio.get("expected_return", 0.0)
    volatility = portfolio.get("volatility", 0.0)

    # Simulate rebalance from equal-weight to optimal
    n = len(weights)
    equal_weights = {s: 1.0 / n for s in weights}
    rebalance = compute_rebalance_costs(
        equal_weights, weights, portfolio_value, fee_rate, slippage_bps
    )

    # Net-of-cost returns
    cost_pct = rebalance["cost_pct_of_portfolio"]
    adjusted = compute_cost_adjusted_returns(
        exp_return, n_rebalances, cost_pct, volatility
    )

    result: dict[str, Any] = {
        "rebalance_costs": rebalance,
        "cost_adjusted_returns": adjusted,
        "portfolio_key": portfolio_key,
    }

    if save:
        storage.save_output(result, "cost_analysis")
        logger.info(
            "Cost analysis: %.4f%% per rebalance, net Sharpe %.4f (drag %.4f)",
            cost_pct * 100, adjusted["net_sharpe"], adjusted["sharpe_drag"],
        )

    return result
