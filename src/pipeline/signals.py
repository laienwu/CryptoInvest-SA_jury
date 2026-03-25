"""
Trading signals module.

Generates BUY/SELL/HOLD signals from technical indicators:
- SMA crossover (short/long moving average)
- RSI (Relative Strength Index) overbought/oversold
- MACD histogram crossover
- Bollinger Band breakout

Each indicator produces a signal per asset per period.
Combined signal uses majority voting across indicators.

Output: data/output/signals.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)

# Signal constants
BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"


class SignalError(Exception):
    """Error during signal generation."""

    def __init__(self, message: str, *, operation: str = "signals") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


# =============================================================================
# Technical Indicator Helpers
# =============================================================================


def _sma(values: list[float], window: int) -> list[float | None]:
    """Simple Moving Average. Returns None for periods before window fills."""
    result: list[float | None] = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            result.append(sum(values[i - window + 1 : i + 1]) / window)
    return result


def _ema(values: list[float], window: int) -> list[float | None]:
    """Exponential Moving Average."""
    if not values:
        return []

    result: list[float | None] = [None] * (window - 1)
    # Seed with SMA
    sma_seed = sum(values[:window]) / window
    result.append(sma_seed)

    multiplier = 2.0 / (window + 1)
    prev = sma_seed
    for i in range(window, len(values)):
        ema_val = (values[i] - prev) * multiplier + prev
        result.append(ema_val)
        prev = ema_val

    return result


def _rsi(prices: list[float], window: int = 14) -> list[float | None]:
    """
    Relative Strength Index.

    RSI = 100 - 100/(1 + RS), where RS = avg_gain / avg_loss.
    """
    if len(prices) < window + 1:
        return [None] * len(prices)

    result: list[float | None] = [None] * window

    # First window: simple average of gains/losses
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, window + 1):
        delta = prices[i] - prices[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window

    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - 100.0 / (1.0 + rs))

    # Subsequent: smoothed average
    for i in range(window + 1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)

        avg_gain = (avg_gain * (window - 1) + gain) / window
        avg_loss = (avg_loss * (window - 1) + loss) / window

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1.0 + rs))

    return result


def _bollinger_bands(
    prices: list[float], window: int = 20, num_std: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Bollinger Bands: (upper, middle, lower)."""
    middle = _sma(prices, window)
    upper: list[float | None] = []
    lower: list[float | None] = []

    for i in range(len(prices)):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            subset = prices[i - window + 1 : i + 1]
            mean = middle[i]
            assert mean is not None
            variance = sum((x - mean) ** 2 for x in subset) / window
            std = math.sqrt(variance)
            upper.append(mean + num_std * std)
            lower.append(mean - num_std * std)

    return upper, middle, lower


# =============================================================================
# Signal Generators
# =============================================================================


def sma_crossover_signal(
    prices: list[float],
    short_window: int = 10,
    long_window: int = 30,
) -> list[str | None]:
    """
    SMA crossover: BUY when short crosses above long, SELL when below.
    """
    short_sma = _sma(prices, short_window)
    long_sma = _sma(prices, long_window)

    signals: list[str | None] = []
    for i in range(len(prices)):
        s, l = short_sma[i], long_sma[i]
        if s is None or l is None:
            signals.append(None)
        elif s > l:
            signals.append(BUY)
        elif s < l:
            signals.append(SELL)
        else:
            signals.append(HOLD)

    return signals


def rsi_signal(
    prices: list[float],
    window: int = 14,
    overbought: float = 70.0,
    oversold: float = 30.0,
) -> list[str | None]:
    """
    RSI signal: SELL when overbought (>70), BUY when oversold (<30).
    """
    rsi_values = _rsi(prices, window)

    signals: list[str | None] = []
    for val in rsi_values:
        if val is None:
            signals.append(None)
        elif val >= overbought:
            signals.append(SELL)
        elif val <= oversold:
            signals.append(BUY)
        else:
            signals.append(HOLD)

    return signals


def macd_signal(
    prices: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_window: int = 9,
) -> list[str | None]:
    """
    MACD histogram crossover: BUY when histogram turns positive, SELL when negative.
    """
    fast_ema = _ema(prices, fast)
    slow_ema = _ema(prices, slow)

    # MACD line = fast EMA - slow EMA
    macd_line: list[float | None] = []
    for f, s in zip(fast_ema, slow_ema):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)

    # Signal line = EMA of MACD line
    macd_values = [v for v in macd_line if v is not None]
    if len(macd_values) < signal_window:
        return [None] * len(prices)

    signal_ema = _ema(macd_values, signal_window)

    # Align signal EMA back to full length
    offset = len(prices) - len(macd_values)
    signals: list[str | None] = [None] * offset

    for i, macd_val in enumerate(macd_values):
        if i < len(signal_ema) and signal_ema[i] is not None:
            histogram = macd_val - signal_ema[i]  # type: ignore[operator]
            if histogram > 0:
                signals.append(BUY)
            elif histogram < 0:
                signals.append(SELL)
            else:
                signals.append(HOLD)
        else:
            signals.append(None)

    return signals


def bollinger_signal(
    prices: list[float],
    window: int = 20,
    num_std: float = 2.0,
) -> list[str | None]:
    """
    Bollinger breakout: BUY when price breaks above upper band (momentum),
    SELL when price breaks below lower band.
    """
    upper, _middle, lower = _bollinger_bands(prices, window, num_std)

    signals: list[str | None] = []
    for i in range(len(prices)):
        u, l = upper[i], lower[i]
        if u is None or l is None:
            signals.append(None)
        elif prices[i] > u:
            signals.append(BUY)
        elif prices[i] < l:
            signals.append(SELL)
        else:
            signals.append(HOLD)

    return signals


# =============================================================================
# Combined Signal
# =============================================================================


def _majority_vote(signals: list[str | None]) -> str | None:
    """Majority vote across indicator signals."""
    valid = [s for s in signals if s is not None]
    if not valid:
        return None

    buy_count = valid.count(BUY)
    sell_count = valid.count(SELL)

    if buy_count > sell_count:
        return BUY
    elif sell_count > buy_count:
        return SELL
    return HOLD


def generate_signals_for_asset(
    prices: list[float],
    sma_short: int = 10,
    sma_long: int = 30,
    rsi_window: int = 14,
) -> dict[str, Any]:
    """
    Generate all signals for a single asset.

    Returns the latest signal from each indicator + combined signal.
    """
    sma_sigs = sma_crossover_signal(prices, sma_short, sma_long)
    rsi_sigs = rsi_signal(prices, rsi_window)
    macd_sigs = macd_signal(prices)
    boll_sigs = bollinger_signal(prices)

    # Latest signal from each
    latest_sma = next((s for s in reversed(sma_sigs) if s is not None), None)
    latest_rsi = next((s for s in reversed(rsi_sigs) if s is not None), None)
    latest_macd = next((s for s in reversed(macd_sigs) if s is not None), None)
    latest_boll = next((s for s in reversed(boll_sigs) if s is not None), None)

    combined = _majority_vote([latest_sma, latest_rsi, latest_macd, latest_boll])

    # Compute latest RSI value for display
    rsi_vals = _rsi(prices, rsi_window)
    latest_rsi_value = next((v for v in reversed(rsi_vals) if v is not None), None)

    return {
        "sma_crossover": latest_sma,
        "rsi": latest_rsi,
        "macd": latest_macd,
        "bollinger": latest_boll,
        "combined": combined,
        "rsi_value": round(latest_rsi_value, 2) if latest_rsi_value is not None else None,
        "n_periods": len(prices),
    }


def generate_portfolio_signals(
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Generate trading signals for all portfolio assets.

    Loads raw price data and computes signals per asset.

    Args:
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Dictionary with per-asset signals, summary, and counts.

    Raises:
        SignalError: If price data is missing.
    """
    if storage is None:
        storage = get_storage()

    try:
        raw_data = storage.load_raw()
    except (StorageError, FileNotFoundError) as e:
        raise SignalError("Raw price data not found", operation="load") from e

    if not raw_data:
        raise SignalError("No raw price data available", operation="validate")

    signals: list[dict[str, Any]] = []
    buy_count = 0
    sell_count = 0
    hold_count = 0

    for symbol, records in raw_data.items():
        if not isinstance(records, list) or not records:
            continue

        # Extract close prices
        closes: list[float] = []
        for r in records:
            if isinstance(r, dict) and "close" in r:
                closes.append(float(r["close"]))

        if len(closes) < 30:
            continue

        asset_signals = generate_signals_for_asset(closes)
        asset_signals["symbol"] = symbol

        combined = asset_signals["combined"]
        if combined == BUY:
            buy_count += 1
        elif combined == SELL:
            sell_count += 1
        else:
            hold_count += 1

        signals.append(asset_signals)

    # Sort by combined signal priority: BUY first, then HOLD, then SELL
    order = {BUY: 0, HOLD: 1, SELL: 2, None: 3}
    signals.sort(key=lambda s: order.get(s.get("combined"), 3))

    result: dict[str, Any] = {
        "signals": signals,
        "summary": {
            "buy_count": buy_count,
            "sell_count": sell_count,
            "hold_count": hold_count,
            "total": len(signals),
        },
        "n_assets": len(signals),
    }

    if save:
        storage.save_output(result, "signals")
        logger.info(
            "Signals generated: %d BUY, %d SELL, %d HOLD",
            buy_count, sell_count, hold_count,
        )

    return result
