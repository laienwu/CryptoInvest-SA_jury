"""
Position sizing module.

Computes how much capital to allocate per trade using:
- Kelly criterion: optimal fraction based on win rate and payoff ratio
- Fixed fractional: risk a fixed % of portfolio per trade
- Volatility targeting: size positions to achieve a target portfolio vol

Given portfolio weights and total capital, outputs dollar amounts and
unit quantities per asset.

Output: data/output/position_sizing.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class PositionSizingError(Exception):
    """Error during position sizing."""

    def __init__(self, message: str, *, operation: str = "position_sizing") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


# =============================================================================
# Sizing Methods
# =============================================================================


def kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """
    Kelly criterion optimal bet fraction.

    f* = (p * b - q) / b
    where p = win rate, q = 1-p, b = avg_win/avg_loss (payoff ratio).

    Returns fraction of capital to risk (0 to 1, clamped).
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0

    b = avg_win / avg_loss  # Payoff ratio
    q = 1.0 - win_rate
    f = (win_rate * b - q) / b

    return max(0.0, min(f, 1.0))


def half_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Half-Kelly: more conservative, reduces variance of returns."""
    return kelly_fraction(win_rate, avg_win, avg_loss) / 2.0


def fixed_fractional(
    portfolio_value: float,
    risk_per_trade: float,
    stop_loss_pct: float,
) -> float:
    """
    Fixed fractional sizing.

    Position size = (portfolio × risk%) / stop_loss%

    Args:
        portfolio_value: Total portfolio value in USD.
        risk_per_trade: Fraction of portfolio to risk (e.g., 0.02 = 2%).
        stop_loss_pct: Stop-loss distance as fraction (e.g., 0.05 = 5%).

    Returns:
        Position size in USD.
    """
    if stop_loss_pct <= 0 or risk_per_trade <= 0:
        return 0.0

    return (portfolio_value * risk_per_trade) / stop_loss_pct


def volatility_target_weight(
    asset_volatility: float,
    target_volatility: float,
    current_weight: float,
) -> float:
    """
    Volatility-targeted weight adjustment.

    Scales weight so the asset's contribution to portfolio vol matches target.

    adjusted_weight = current_weight × (target_vol / asset_vol)

    Args:
        asset_volatility: Annualized volatility of the asset.
        target_volatility: Target portfolio volatility.
        current_weight: Current portfolio weight.

    Returns:
        Adjusted weight (may exceed 1.0 for leveraged portfolios).
    """
    if asset_volatility <= 0:
        return 0.0

    return current_weight * (target_volatility / asset_volatility)


# =============================================================================
# Portfolio-Level Position Sizing
# =============================================================================


def compute_position_sizes(
    weights: dict[str, float],
    portfolio_value: float = 10000.0,
    volatilities: dict[str, float] | None = None,
    target_volatility: float = 0.15,
    risk_per_trade: float = 0.02,
    method: str = "weight",
) -> dict[str, Any]:
    """
    Compute position sizes for all assets.

    Args:
        weights: Portfolio weights {symbol: weight}.
        portfolio_value: Total portfolio value in USD.
        volatilities: Per-asset annualized volatility {symbol: vol}.
        target_volatility: Target portfolio vol (for vol-targeting method).
        risk_per_trade: Risk per trade as fraction (for fixed-fractional).
        method: Sizing method — "weight", "vol_target", or "fixed_fractional".

    Returns:
        Dictionary with per-asset sizes, dollar amounts, and method info.
    """
    if not weights:
        return {"positions": [], "total_allocated": 0.0, "n_assets": 0, "method": method}

    positions: list[dict[str, Any]] = []
    total_allocated = 0.0

    for symbol, weight in weights.items():
        if method == "vol_target" and volatilities:
            asset_vol = volatilities.get(symbol, 0.0)
            adjusted_weight = volatility_target_weight(asset_vol, target_volatility, weight)
        elif method == "fixed_fractional" and volatilities:
            asset_vol = volatilities.get(symbol, 0.0)
            if asset_vol > 0:
                size_usd = fixed_fractional(portfolio_value, risk_per_trade, asset_vol * 0.1)
                adjusted_weight = size_usd / portfolio_value if portfolio_value > 0 else 0.0
            else:
                adjusted_weight = weight
        else:
            adjusted_weight = weight

        amount_usd = round(portfolio_value * adjusted_weight, 2)
        total_allocated += amount_usd

        positions.append({
            "symbol": symbol,
            "original_weight": round(weight, 6),
            "adjusted_weight": round(adjusted_weight, 6),
            "amount_usd": amount_usd,
        })

    positions.sort(key=lambda p: p["amount_usd"], reverse=True)

    return {
        "positions": positions,
        "total_allocated": round(total_allocated, 2),
        "portfolio_value": portfolio_value,
        "method": method,
        "target_volatility": target_volatility if method == "vol_target" else None,
        "risk_per_trade": risk_per_trade if method == "fixed_fractional" else None,
        "n_assets": len(positions),
    }


def analyze_position_sizing(
    portfolio_key: str = "weights",
    portfolio_value: float = 10000.0,
    method: str = "weight",
    target_volatility: float = 0.15,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Compute position sizes using portfolio weights and volatility data.

    Args:
        portfolio_key: Storage key for portfolio weights.
        portfolio_value: Total capital in USD.
        method: Sizing method.
        target_volatility: Target vol for vol-targeting.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Position sizing results.

    Raises:
        PositionSizingError: If data is missing.
    """
    if storage is None:
        storage = get_storage()

    try:
        portfolio = storage.load_output(portfolio_key)
    except (StorageError, FileNotFoundError) as e:
        raise PositionSizingError(
            f"Portfolio not found (key={portfolio_key})", operation="load"
        ) from e

    weights = portfolio.get("weights", {})
    if not weights:
        raise PositionSizingError("Portfolio has no weights", operation="validate")

    # Load volatilities if needed
    volatilities: dict[str, float] | None = None
    if method in ("vol_target", "fixed_fractional"):
        try:
            vol_data = storage.load_processed("volatility")
            symbols = vol_data.get("symbols", [])
            values = vol_data.get("values", [])
            if symbols and values:
                volatilities = dict(zip(symbols, values))
        except (StorageError, FileNotFoundError):
            logger.warning("Volatility data not found, using weight-based sizing")
            method = "weight"

    result = compute_position_sizes(
        weights=weights,
        portfolio_value=portfolio_value,
        volatilities=volatilities,
        target_volatility=target_volatility,
        method=method,
    )

    if save:
        storage.save_output("position_sizing", result)
        logger.info(
            "Position sizing (%s): %d assets, $%.2f allocated",
            method, result["n_assets"], result["total_allocated"],
        )

    return result
