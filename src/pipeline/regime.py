"""
Market regime detection module.

Classifies market conditions into regimes (bull, bear, sideways) using
a combination of trend and volatility indicators:

- Trend: SMA slope direction (50-period SMA vs 20-period SMA)
- Volatility: realized vol vs historical median vol
- Regime labels: BULL, BEAR, SIDEWAYS
- Confidence: fraction of indicators agreeing on the regime

Output: data/output/regime.json
"""

import logging
import math
from typing import Any

from src.config import load_config
from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)

REGIME_BULL = "BULL"
REGIME_BEAR = "BEAR"
REGIME_SIDEWAYS = "SIDEWAYS"


class RegimeError(Exception):
    """Error during regime detection."""

    def __init__(self, message: str, *, operation: str = "regime") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def _sma(prices: list[float], window: int) -> float | None:
    """Simple moving average of last `window` prices."""
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window


def _realized_volatility(returns: list[float], window: int = 20) -> float:
    """Annualized realized volatility from recent returns."""
    if len(returns) < window:
        if len(returns) < 2:
            return 0.0
        subset = returns
    else:
        subset = returns[-window:]

    n = len(subset)
    mean = sum(subset) / n
    var = sum((r - mean) ** 2 for r in subset) / (n - 1)
    return math.sqrt(var) * math.sqrt(365)


def _median(values: list[float]) -> float:
    """Median of a list."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def detect_regime_for_symbol(
    prices: list[float],
    returns: list[float],
    short_window: int = 20,
    long_window: int = 50,
    vol_window: int = 20,
) -> dict[str, Any]:
    """
    Detect market regime for a single asset.

    Uses three signals:
    1. Trend: short SMA vs long SMA (above = bullish)
    2. Price vs long SMA (above = bullish)
    3. Volatility regime: current vol vs median vol (high vol = uncertain)

    Args:
        prices: List of closing prices (oldest first).
        returns: List of log returns (oldest first).
        short_window: Short SMA window.
        long_window: Long SMA window.
        vol_window: Volatility lookback window.

    Returns:
        Regime classification with confidence.
    """
    if len(prices) < long_window:
        return {
            "regime": REGIME_SIDEWAYS,
            "confidence": 0.0,
            "trend_signal": "NEUTRAL",
            "vol_regime": "UNKNOWN",
            "short_sma": None,
            "long_sma": None,
            "current_vol": 0.0,
            "median_vol": 0.0,
            "n_periods": len(prices),
        }

    short_sma = _sma(prices, short_window)
    long_sma = _sma(prices, long_window)
    current_price = prices[-1]

    # Signal 1: SMA crossover
    sma_bullish = short_sma is not None and long_sma is not None and short_sma > long_sma

    # Signal 2: Price vs long SMA
    price_above_sma = long_sma is not None and current_price > long_sma

    # Signal 3: Volatility regime
    current_vol = _realized_volatility(returns, vol_window)

    # Compute rolling vol for median comparison
    rolling_vols: list[float] = []
    for i in range(vol_window, len(returns) + 1):
        rv = _realized_volatility(returns[i - vol_window : i], vol_window)
        rolling_vols.append(rv)
    median_vol = _median(rolling_vols) if rolling_vols else current_vol

    high_vol = current_vol > median_vol * 1.2 if median_vol > 0 else False

    # Combine signals
    bull_signals = sum([sma_bullish, price_above_sma])
    bear_signals = sum([not sma_bullish, not price_above_sma])

    if bull_signals == 2 and not high_vol:
        regime = REGIME_BULL
        confidence = 1.0
    elif bull_signals == 2 and high_vol:
        regime = REGIME_BULL
        confidence = 0.7
    elif bear_signals == 2 and not high_vol:
        regime = REGIME_BEAR
        confidence = 1.0
    elif bear_signals == 2 and high_vol:
        regime = REGIME_BEAR
        confidence = 0.7
    else:
        regime = REGIME_SIDEWAYS
        confidence = 0.5

    if sma_bullish:
        trend_signal = "BULLISH"
    elif short_sma is not None and long_sma is not None and short_sma < long_sma:
        trend_signal = "BEARISH"
    else:
        trend_signal = "NEUTRAL"

    vol_regime = "HIGH" if high_vol else "LOW"

    return {
        "regime": regime,
        "confidence": round(confidence, 2),
        "trend_signal": trend_signal,
        "vol_regime": vol_regime,
        "short_sma": round(short_sma, 4) if short_sma is not None else None,
        "long_sma": round(long_sma, 4) if long_sma is not None else None,
        "current_vol": round(current_vol, 6),
        "median_vol": round(median_vol, 6),
        "n_periods": len(prices),
    }


def analyze_regimes(
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Detect market regimes for all portfolio symbols.

    Loads raw price data from storage, computes per-symbol regime,
    and summarizes overall market conditions.

    Args:
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Per-symbol regimes and market summary.

    Raises:
        RegimeError: If price data is missing.
    """
    if storage is None:
        storage = get_storage()

    # Load raw kline data (only configured symbols to avoid mixing frequencies)
    cfg = load_config()
    try:
        raw_data = storage.load_raw(list(cfg.symbols))
    except (StorageError, FileNotFoundError) as e:
        raise RegimeError(
            "Raw price data not found", operation="load"
        ) from e

    if not raw_data:
        raise RegimeError("No price data available", operation="validate")

    regimes: list[dict[str, Any]] = []

    for symbol, klines in sorted(raw_data.items()):
        if not isinstance(klines, list) or len(klines) < 2:
            continue

        # Extract close prices
        prices = [k["close"] for k in klines if "close" in k]
        if len(prices) < 2:
            continue

        # Compute log returns
        returns: list[float] = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0 and prices[i] > 0:
                returns.append(math.log(prices[i] / prices[i - 1]))

        regime = detect_regime_for_symbol(prices, returns)
        regime["symbol"] = symbol
        regimes.append(regime)

    # Market summary
    bull_count = sum(1 for r in regimes if r["regime"] == REGIME_BULL)
    bear_count = sum(1 for r in regimes if r["regime"] == REGIME_BEAR)
    sideways_count = sum(1 for r in regimes if r["regime"] == REGIME_SIDEWAYS)

    total = len(regimes)
    if bull_count > bear_count and bull_count > sideways_count:
        market_regime = REGIME_BULL
    elif bear_count > bull_count and bear_count > sideways_count:
        market_regime = REGIME_BEAR
    else:
        market_regime = REGIME_SIDEWAYS

    result: dict[str, Any] = {
        "regimes": regimes,
        "summary": {
            "market_regime": market_regime,
            "bull_count": bull_count,
            "bear_count": bear_count,
            "sideways_count": sideways_count,
            "n_assets": total,
        },
    }

    if save:
        storage.save_output(result, "regime")
        logger.info(
            "Regime detection: %s (bull=%d, bear=%d, sideways=%d)",
            market_regime, bull_count, bear_count, sideways_count,
        )

    return result
