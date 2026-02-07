"""
Data ingestion module for Binance API.

This module provides functions to fetch historical klines (OHLCV candlesticks)
from Binance public API for portfolio optimization.

Output format (dictionary with symbols as keys):
    {
        "BTCUSDT": [
            {"timestamp": "2024-01-01", "open": 42000.0, "high": 43000.0, ...},
            ...
        ],
        "ETHUSDT": [...],
        ...
    }

Example usage:
    >>> from src.pipeline.ingest import ingest_data
    >>> data = ingest_data()
    >>> btc_data = data["BTCUSDT"]
    >>> print(btc_data[0])
    {'timestamp': '2024-01-01', 'open': 42000.0, 'high': 43000.0, ...}
"""

import time
from datetime import datetime, timedelta
from typing import Any

import logging
import requests

from src.config import load_config

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration (from centralized config)
# =============================================================================

_cfg = load_config()

DEFAULT_SYMBOLS: list[str] = list(_cfg.symbols)
DEFAULT_INTERVAL: str = _cfg.interval
DEFAULT_PERIOD_DAYS: int = _cfg.period_days

BINANCE_API_BASE: str = _cfg.binance_api_base
RATE_LIMIT_DELAY: float = _cfg.rate_limit_delay
MAX_RETRIES: int = _cfg.max_retries

# Retry delay multiplier (exponential backoff)
RETRY_DELAY_MULTIPLIER: float = 2.0


# =============================================================================
# Exceptions
# =============================================================================


class BinanceAPIError(Exception):
    """Custom exception for Binance API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# =============================================================================
# API Functions
# =============================================================================


def _make_request(url: str, params: dict[str, Any]) -> list[list[Any]]:
    """
    Make a GET request to Binance API with retry logic.

    Args:
        url: Full API endpoint URL.
        params: Query parameters for the request.

    Returns:
        JSON response as a list of kline data.

    Raises:
        BinanceAPIError: If the request fails after all retries.
    """
    last_exception: Exception | None = None
    delay = RATE_LIMIT_DELAY

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, timeout=30)

            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            # Check for other errors
            if response.status_code != 200:
                error_msg = response.json().get("msg", "Unknown error")
                raise BinanceAPIError(
                    f"API error: {error_msg}", status_code=response.status_code
                )

            return response.json()

        except requests.exceptions.Timeout:
            last_exception = BinanceAPIError("Request timed out")
            logger.warning(f"Timeout on attempt {attempt + 1}/{MAX_RETRIES}")

        except requests.exceptions.ConnectionError as e:
            last_exception = BinanceAPIError(f"Connection error: {e}")
            logger.warning(f"Connection error on attempt {attempt + 1}/{MAX_RETRIES}")

        except requests.exceptions.RequestException as e:
            last_exception = BinanceAPIError(f"Request error: {e}")
            logger.warning(f"Request error on attempt {attempt + 1}/{MAX_RETRIES}")

        # Exponential backoff
        if attempt < MAX_RETRIES - 1:
            time.sleep(delay)
            delay *= RETRY_DELAY_MULTIPLIER

    raise last_exception or BinanceAPIError("Unknown error after retries")


def fetch_klines(
    symbol: str,
    interval: str = DEFAULT_INTERVAL,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """
    Fetch klines (candlestick data) for a single symbol from Binance API.

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT").
        interval: Kline interval (e.g., "1d", "1h", "15m").
        start_time: Start datetime for data. Defaults to 90 days ago.
        end_time: End datetime for data. Defaults to now.
        limit: Maximum number of klines to fetch (max 1000).

    Returns:
        List of dictionaries with kline data.
        Each dict contains: timestamp (str), open, high, low, close, volume.

    Raises:
        BinanceAPIError: If API request fails.

    Example:
        >>> klines = fetch_klines("BTCUSDT", interval="1d")
        >>> print(klines[0])
        {'timestamp': '2024-01-01', 'open': 45000.0, ...}
    """
    # Set default time range
    if end_time is None:
        end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(days=DEFAULT_PERIOD_DAYS)

    # Convert to milliseconds timestamp
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    # Build request parameters
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": min(limit, 1000),  # Ensure we don't exceed API limit
    }

    url = f"{BINANCE_API_BASE}/api/v3/klines"
    logger.info(f"Fetching {symbol} klines from {start_time.date()} to {end_time.date()}...")

    # Make API request
    raw_klines = _make_request(url, params)

    # Parse response into structured format
    # Binance kline format:
    # [openTime, open, high, low, close, volume, closeTime,
    #  quoteVolume, trades, takerBuyBase, takerBuyQuote, ignore]
    klines: list[dict[str, Any]] = []
    for kline in raw_klines:
        # Convert timestamp to readable date string (YYYY-MM-DD)
        timestamp_dt = datetime.fromtimestamp(kline[0] / 1000)
        klines.append(
            {
                "timestamp": timestamp_dt.strftime("%Y-%m-%d"),
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": float(kline[4]),
                "volume": float(kline[5]),
            }
        )

    logger.info(f"Retrieved {len(klines)} klines for {symbol}")
    return klines


def fetch_all_symbols(
    symbols: list[str] | None = None,
    interval: str = DEFAULT_INTERVAL,
    period_days: int = DEFAULT_PERIOD_DAYS,
) -> dict[str, list[dict[str, Any]]]:
    """
    Fetch klines for multiple symbols and return as a dictionary.

    Args:
        symbols: List of trading pair symbols. Defaults to DEFAULT_SYMBOLS.
        interval: Kline interval (e.g., "1d", "1h").
        period_days: Number of days of historical data to fetch.

    Returns:
        Dictionary with symbol as key and list of kline dicts as value.
        Example:
        {
            "BTCUSDT": [{"timestamp": "2024-01-01", "open": 42000.0, ...}, ...],
            "ETHUSDT": [{"timestamp": "2024-01-01", "open": 2500.0, ...}, ...],
        }

    Raises:
        BinanceAPIError: If any API request fails.

    Example:
        >>> data = fetch_all_symbols(["BTCUSDT", "ETHUSDT"], period_days=30)
        >>> btc_prices = data["BTCUSDT"]
        >>> print(btc_prices[0]["close"])
    """
    if symbols is None:
        symbols = DEFAULT_SYMBOLS.copy()

    end_time = datetime.now()
    start_time = end_time - timedelta(days=period_days)

    result: dict[str, list[dict[str, Any]]] = {}
    failed_symbols: list[str] = []

    logger.info(f"Starting data ingestion for {len(symbols)} symbols...")
    logger.info(f"Period: {start_time.date()} to {end_time.date()} ({period_days} days)")

    for i, symbol in enumerate(symbols):
        try:
            klines = fetch_klines(
                symbol=symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
            )
            result[symbol] = klines

            # Rate limit delay between symbols
            if i < len(symbols) - 1:
                time.sleep(RATE_LIMIT_DELAY)

        except BinanceAPIError as e:
            logger.error(f"Failed to fetch {symbol}: {e.message}")
            failed_symbols.append(symbol)
            continue

    total_records = sum(len(klines) for klines in result.values())
    logger.info(f"Ingestion complete: {total_records} total records for {len(result)} symbols")
    if failed_symbols:
        logger.warning(f"Failed symbols: {failed_symbols}")

    return result


def ingest_data(
    symbols: list[str] | None = None,
    interval: str = DEFAULT_INTERVAL,
    period_days: int = DEFAULT_PERIOD_DAYS,
) -> dict[str, list[dict[str, Any]]]:
    """
    Main entry point for data ingestion (full refresh).

    This is the primary function to call for the INGEST pipeline step.
    Fetches historical OHLCV data for multiple cryptocurrency pairs.

    Args:
        symbols: List of trading pair symbols. Defaults to DEFAULT_SYMBOLS.
        interval: Kline interval (e.g., "1d", "1h").
        period_days: Number of days of historical data to fetch.

    Returns:
        Dictionary with symbol as key and list of OHLCV dicts as value.
        Each OHLCV dict contains: timestamp, open, high, low, close, volume.

    Example:
        >>> data = ingest_data()
        >>> print(data["BTCUSDT"][0])
        {'timestamp': '2024-01-01', 'open': 42000.0, 'high': 43000.0, ...}
    """
    return fetch_all_symbols(
        symbols=symbols,
        interval=interval,
        period_days=period_days,
    )


def ingest_incremental(
    symbols: list[str] | None = None,
    interval: str = DEFAULT_INTERVAL,
) -> dict[str, list[dict[str, Any]]]:
    """
    Incremental data ingestion - only fetch new data since last ingest.

    Loads existing data, finds the last date, fetches only new records,
    and returns merged data ready to save.

    Args:
        symbols: List of trading pair symbols. Defaults to DEFAULT_SYMBOLS.
        interval: Kline interval (e.g., "1d", "1h").

    Returns:
        Dictionary with merged old + new data for each symbol.

    Example:
        >>> data = ingest_incremental()
        >>> storage.save_raw(data)  # Overwrites with merged data
    """
    from src.storage import get_storage

    if symbols is None:
        symbols = DEFAULT_SYMBOLS.copy()

    storage = get_storage()
    result: dict[str, list[dict[str, Any]]] = {}

    logger.info("Starting incremental ingestion...")

    for symbol in symbols:
        # Load existing data
        try:
            existing = storage.load_raw([symbol])
            existing_records = existing.get(symbol, [])
        except Exception:
            existing_records = []

        if existing_records:
            # Find last date
            last_date_str = max(r["timestamp"] for r in existing_records)
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
            start_time = last_date + timedelta(days=1)  # Start from next day
            logger.info(f"{symbol}: Last data {last_date_str}, fetching from {start_time.date()}")
        else:
            # No existing data, fetch full period
            start_time = datetime.now() - timedelta(days=DEFAULT_PERIOD_DAYS)
            logger.info(f"{symbol}: No existing data, fetching {DEFAULT_PERIOD_DAYS} days")

        # Fetch new data
        end_time = datetime.now()
        if start_time >= end_time:
            logger.info(f"{symbol}: Already up to date")
            result[symbol] = existing_records
            continue

        try:
            new_records = fetch_klines(
                symbol=symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
            )
        except BinanceAPIError as e:
            logger.error(f"Failed to fetch {symbol}: {e.message}")
            result[symbol] = existing_records
            continue

        # Merge: existing + new (dedupe by timestamp)
        all_records = existing_records + new_records
        seen = set()
        merged = []
        for r in all_records:
            if r["timestamp"] not in seen:
                seen.add(r["timestamp"])
                merged.append(r)
        merged.sort(key=lambda x: x["timestamp"])

        result[symbol] = merged
        logger.info(f"{symbol}: {len(existing_records)} existing + {len(new_records)} new = {len(merged)} total")

        time.sleep(RATE_LIMIT_DELAY)

    total = sum(len(v) for v in result.values())
    logger.info(f"Incremental ingestion complete: {total} total records")

    return result


def fetch_current_prices(symbols: list[str] | None = None) -> dict[str, float]:
    """
    Fetch current spot prices for multiple symbols.

    Args:
        symbols: List of trading pair symbols. Defaults to DEFAULT_SYMBOLS.

    Returns:
        Dictionary mapping symbol to current price.

    Raises:
        BinanceAPIError: If API request fails.

    Example:
        >>> prices = fetch_current_prices(["BTCUSDT", "ETHUSDT"])
        >>> print(prices)
        {'BTCUSDT': 45000.0, 'ETHUSDT': 3000.0}
    """
    if symbols is None:
        symbols = DEFAULT_SYMBOLS.copy()

    url = f"{BINANCE_API_BASE}/api/v3/ticker/price"
    prices: dict[str, float] = {}

    for symbol in symbols:
        params = {"symbol": symbol}
        try:
            response = _make_request(url, params)
            prices[symbol] = float(response["price"])
            time.sleep(RATE_LIMIT_DELAY)
        except BinanceAPIError as e:
            logger.error(f"Failed to fetch price for {symbol}: {e.message}")
            continue

    return prices


# =============================================================================
# Main execution (for testing)
# =============================================================================

if __name__ == "__main__":
    # Test the ingestion module
    print("Testing Binance data ingestion...")
    print("=" * 50)

    # Fetch data for default symbols
    data = ingest_data()

    # Display sample data
    if data:
        for symbol, klines in data.items():
            print(f"\n{symbol}: {len(klines)} records")
            if klines:
                print(f"  First record: {klines[0]}")
                print(f"  Last record:  {klines[-1]}")

    # Fetch current prices
    print("\n" + "=" * 50)
    print("Current prices:")
    prices = fetch_current_prices()
    for symbol, price in prices.items():
        print(f"  {symbol}: ${price:,.2f}")
