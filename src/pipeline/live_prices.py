"""
Live price fetcher for portfolio symbols.

Fetches current prices from Binance public API for crypto symbols
and optionally from yfinance for traditional assets.

No authentication required — uses Binance public ticker endpoint.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
REQUEST_TIMEOUT = 10


class LivePriceError(Exception):
    """Error fetching live prices."""

    def __init__(self, message: str, *, operation: str = "live_prices") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def fetch_binance_ticker(symbols: list[str]) -> list[dict[str, Any]]:
    """
    Fetch 24h ticker data from Binance for given symbols.

    Args:
        symbols: List of trading pairs (e.g., ["BTCUSDT", "ETHUSDT"]).

    Returns:
        List of ticker dicts with symbol, price, change_24h, volume_24h.

    Raises:
        LivePriceError: If the API request fails.
    """
    if not symbols:
        return []

    try:
        resp = requests.get(BINANCE_TICKER_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        all_tickers = resp.json()
    except requests.RequestException as e:
        raise LivePriceError(
            f"Binance API request failed: {e}", operation="fetch_binance"
        ) from e

    symbol_set = set(symbols)
    results = []
    for t in all_tickers:
        if t["symbol"] in symbol_set:
            results.append({
                "symbol": t["symbol"],
                "price": float(t["lastPrice"]),
                "change_24h": float(t["priceChangePercent"]),
                "volume_24h": float(t["quoteVolume"]),
                "high_24h": float(t["highPrice"]),
                "low_24h": float(t["lowPrice"]),
            })

    return results


def fetch_live_prices(
    crypto_symbols: list[str] | None = None,
    trad_symbols: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fetch live prices for both crypto and traditional symbols.

    Args:
        crypto_symbols: Crypto trading pairs. If None, loads from config.
        trad_symbols: Traditional symbols. If None, loads from config.

    Returns:
        Dictionary with crypto tickers, trad tickers, and timestamp.
    """
    if crypto_symbols is None:
        from src.config import load_config
        crypto_symbols = load_config().symbols

    crypto_tickers = []
    try:
        crypto_tickers = fetch_binance_ticker(crypto_symbols)
    except LivePriceError:
        logger.warning("Failed to fetch Binance prices")

    trad_tickers: list[dict[str, Any]] = []
    if trad_symbols:
        try:
            import yfinance as yf
            for symbol in trad_symbols:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                trad_tickers.append({
                    "symbol": symbol,
                    "price": float(info.last_price),
                    "change_24h": round(
                        (info.last_price / info.previous_close - 1) * 100, 2
                    ) if info.previous_close else 0.0,
                    "volume_24h": float(info.last_volume) if info.last_volume else 0.0,
                    "high_24h": 0.0,
                    "low_24h": 0.0,
                })
        except Exception:
            logger.warning("Failed to fetch yfinance prices for trad symbols")

    return {
        "crypto": crypto_tickers,
        "trad": trad_tickers,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "n_crypto": len(crypto_tickers),
        "n_trad": len(trad_tickers),
    }
