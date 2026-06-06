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

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from src.config import load_config

logger = logging.getLogger(__name__)

# Retry delay multiplier (exponential backoff)
RETRY_DELAY_MULTIPLIER: float = 2.0


# =============================================================================
# Exceptions
# =============================================================================


class BinanceAPIError(Exception):
    """Custom exception for Binance API errors.

    ``binance_code`` is Binance's in-body error code (e.g. ``-2013`` for
    "Order does not exist"), extracted from the JSON response body when
    present. This is what callers should key off for error classification
    — HTTP ``status_code`` alone can't distinguish a missing order from a
    bad signature.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        binance_code: int | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.binance_code = binance_code
        super().__init__(self.message)

    def __str__(self) -> str:
        parts = [self.message]
        if self.binance_code is not None:
            parts.append(f"[binance_code={self.binance_code}]")
        if self.status_code is not None:
            parts.append(f"[http={self.status_code}]")
        return " ".join(parts)


# =============================================================================
# API Functions
# =============================================================================


def make_binance_request(
    url: str,
    params: dict[str, Any],
    rate_limit_delay: float = 0.5,
    max_retries: int = 3,
) -> Any:
    """
    Make a GET request to Binance API with retry logic.

    Args:
        url: Full API endpoint URL.
        params: Query parameters for the request.
        rate_limit_delay: Base delay between retries in seconds.
        max_retries: Maximum number of retry attempts.

    Returns:
        JSON response as a list of kline data.

    Raises:
        BinanceAPIError: If the request fails after all retries.
    """
    last_exception: Exception | None = None
    delay = rate_limit_delay

    for attempt in range(max_retries):
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
                binance_code: int | None = None
                try:
                    body = response.json()
                    error_msg = body.get("msg", "Unknown error")
                    raw_code = body.get("code")
                    if isinstance(raw_code, int):
                        binance_code = raw_code
                except (ValueError, KeyError):
                    error_msg = response.text[:200]
                raise BinanceAPIError(
                    f"API error: {error_msg}",
                    status_code=response.status_code,
                    binance_code=binance_code,
                )

            return response.json()

        except requests.exceptions.Timeout:
            last_exception = BinanceAPIError("Request timed out")
            logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")

        except requests.exceptions.ConnectionError as e:
            last_exception = BinanceAPIError(f"Connection error: {e}")
            logger.warning(f"Connection error on attempt {attempt + 1}/{max_retries}")

        except requests.exceptions.RequestException as e:
            last_exception = BinanceAPIError(f"Request error: {e}")
            logger.warning(f"Request error on attempt {attempt + 1}/{max_retries}")

        # Exponential backoff
        if attempt < max_retries - 1:
            time.sleep(delay)
            delay *= RETRY_DELAY_MULTIPLIER

    raise last_exception or BinanceAPIError("Unknown error after retries")


def _timestamp_format(interval: str) -> str:
    """Return the timestamp format string for the given kline interval."""
    if interval in ("1d", "3d", "1w", "1M"):
        return "%Y-%m-%d"
    return "%Y-%m-%dT%H:%M:%S"


def fetch_klines(
    symbol: str,
    interval: str = "1m",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 1000,
    api_base: str = "https://api.binance.com",
    rate_limit_delay: float = 0.5,
    max_retries: int = 3,
    period_days: int = 30,
) -> list[dict[str, Any]]:
    """
    Fetch klines (candlestick data) for a single symbol from Binance API.

    Automatically paginates through results when the requested date range
    contains more than 1000 candles (Binance API limit per call).

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT").
        interval: Kline interval (e.g., "1m", "5m", "1h", "1d").
        start_time: Start datetime for data. Defaults to period_days ago.
        end_time: End datetime for data. Defaults to now.
        limit: Records per page (max 1000).
        api_base: Binance API base URL.
        rate_limit_delay: Base delay for retries in seconds.
        max_retries: Maximum number of retry attempts.
        period_days: Default number of days to fetch when start_time is None.

    Returns:
        List of dictionaries with kline data.
        Each dict contains: timestamp (str), open, high, low, close, volume.

    Raises:
        BinanceAPIError: If API request fails.
    """
    if end_time is None:
        end_time = datetime.now(UTC)
    if start_time is None:
        start_time = end_time - timedelta(days=period_days)

    current_start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)
    url = f"{api_base}/api/v3/klines"
    page_size = min(limit, 1000)
    ts_fmt = _timestamp_format(interval)

    logger.info(
        "Fetching %s klines (%s) from %s to %s...",
        symbol, interval, start_time.date(), end_time.date(),
    )

    all_klines: list[dict[str, Any]] = []
    page = 0

    while current_start_ms < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start_ms,
            "endTime": end_ms,
            "limit": page_size,
        }

        raw_klines = make_binance_request(url, params, rate_limit_delay, max_retries)

        if not raw_klines:
            break

        for kline in raw_klines:
            timestamp_dt = datetime.fromtimestamp(kline[0] / 1000, tz=UTC)
            all_klines.append({
                "timestamp": timestamp_dt.strftime(ts_fmt),
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": float(kline[4]),
                "volume": float(kline[5]),
            })

        # Advance past the last returned kline's close time
        last_close_ms = int(raw_klines[-1][6])
        current_start_ms = last_close_ms + 1
        page += 1

        # Stop if we got fewer than a full page (no more data)
        if len(raw_klines) < page_size:
            break

        # Rate limit between pages
        if current_start_ms < end_ms:
            time.sleep(rate_limit_delay)

    logger.info("Retrieved %d klines for %s (%d pages)", len(all_klines), symbol, page)
    return all_klines


def fetch_all_symbols(
    symbols: list[str] | None = None,
    interval: str | None = None,
    period_days: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Fetch klines for multiple symbols and return as a dictionary.

    Args:
        symbols: List of trading pair symbols. Defaults to config symbols.
        interval: Kline interval (e.g., "1d", "1h"). Defaults to config interval.
        period_days: Number of days of historical data to fetch. Defaults to config.

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
    cfg = load_config()
    if symbols is None:
        symbols = list(cfg.symbols)
    if interval is None:
        interval = cfg.interval
    if period_days is None:
        period_days = cfg.period_days

    end_time = datetime.now(UTC)
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
                api_base=cfg.binance_api_base,
                rate_limit_delay=cfg.rate_limit_delay,
                max_retries=cfg.max_retries,
                period_days=period_days,
            )
            result[symbol] = klines

            # Rate limit delay between symbols
            if i < len(symbols) - 1:
                time.sleep(cfg.rate_limit_delay)

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
    interval: str | None = None,
    period_days: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Main entry point for data ingestion (full refresh).

    This is the primary function to call for the INGEST pipeline step.
    Fetches historical OHLCV data for multiple cryptocurrency pairs.

    Args:
        symbols: List of trading pair symbols. Defaults to config symbols.
        interval: Kline interval (e.g., "1d", "1h"). Defaults to config interval.
        period_days: Number of days of historical data to fetch. Defaults to config.

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
    interval: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Incremental data ingestion - only fetch new data since last ingest.

    Loads existing data, finds the last date, fetches only new records,
    and returns merged data ready to save.

    Args:
        symbols: List of trading pair symbols. Defaults to config symbols.
        interval: Kline interval (e.g., "1d", "1h"). Defaults to config interval.

    Returns:
        Dictionary with merged old + new data for each symbol.

    Example:
        >>> data = ingest_incremental()
        >>> storage.save_raw(data)  # Overwrites with merged data
    """
    from src.storage import get_storage

    cfg = load_config()
    if symbols is None:
        symbols = list(cfg.symbols)
    if interval is None:
        interval = cfg.interval

    storage = get_storage(cfg.storage_backend)
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
            # Find last timestamp (supports both daily and intraday formats)
            last_date_str = max(r["timestamp"] for r in existing_records)
            try:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
                start_time = last_date + timedelta(minutes=1)
            except ValueError:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=UTC)
                start_time = last_date + timedelta(days=1)
            logger.info(f"{symbol}: Last data {last_date_str}, fetching from {start_time}")
        else:
            # No existing data, fetch full period
            start_time = datetime.now(UTC) - timedelta(days=cfg.period_days)
            logger.info(f"{symbol}: No existing data, fetching {cfg.period_days} days")

        # Fetch new data
        end_time = datetime.now(UTC)
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
                api_base=cfg.binance_api_base,
                rate_limit_delay=cfg.rate_limit_delay,
                max_retries=cfg.max_retries,
                period_days=cfg.period_days,
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

        time.sleep(cfg.rate_limit_delay)

    total = sum(len(v) for v in result.values())
    logger.info(f"Incremental ingestion complete: {total} total records")

    return result


def fetch_current_prices(symbols: list[str] | None = None) -> dict[str, float]:
    """
    Fetch current spot prices for multiple symbols.

    Args:
        symbols: List of trading pair symbols. Defaults to config symbols.

    Returns:
        Dictionary mapping symbol to current price.

    Raises:
        BinanceAPIError: If API request fails.

    Example:
        >>> prices = fetch_current_prices(["BTCUSDT", "ETHUSDT"])
        >>> print(prices)
        {'BTCUSDT': 45000.0, 'ETHUSDT': 3000.0}
    """
    cfg = load_config()
    if symbols is None:
        symbols = list(cfg.symbols)

    url = f"{cfg.binance_api_base}/api/v3/ticker/price"
    prices: dict[str, float] = {}

    for symbol in symbols:
        params = {"symbol": symbol}
        try:
            response = make_binance_request(url, params, cfg.rate_limit_delay, cfg.max_retries)
            prices[symbol] = float(response["price"])
            time.sleep(cfg.rate_limit_delay)
        except BinanceAPIError as e:
            logger.error(f"Failed to fetch price for {symbol}: {e.message}")
            continue

    return prices
