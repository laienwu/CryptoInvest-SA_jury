"""
Data ingestion module for traditional assets via yfinance.

Fetches historical OHLCV data for stocks, ETFs, commodities, and indices
from Yahoo Finance. Output format matches the Binance ingest module so
the same transform/optimize pipeline can process both asset classes.

Output format (dictionary with symbols as keys):
    {
        "SPY": [
            {"timestamp": "2024-01-01", "open": 470.0, "high": 475.0, ...},
            ...
        ],
        "GLD": [...],
        ...
    }

Example usage:
    >>> from src.pipeline.ingest_yfinance import ingest_yfinance_data
    >>> data = ingest_yfinance_data()
    >>> spy_data = data["SPY"]
    >>> print(spy_data[0])
    {'timestamp': '2024-01-01', 'open': 470.0, 'high': 475.0, ...}
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from src.config import load_yfinance_config

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class YFinanceError(Exception):
    """Custom exception for yfinance data errors."""

    def __init__(self, message: str, symbol: str | None = None):
        self.message = message
        self.symbol = symbol
        super().__init__(self.message)


# =============================================================================
# API Functions
# =============================================================================


def fetch_yfinance_klines(
    symbol: str,
    period_days: int = 365,
) -> list[dict[str, Any]]:
    """
    Fetch historical OHLCV data for a single symbol from Yahoo Finance.

    Uses yfinance internally; converts the DataFrame to a list of dicts
    matching the Binance kline format. No pandas is exposed outside
    this function (ADR-003 compliance).

    Args:
        symbol: Ticker symbol (e.g., "SPY", "AAPL", "GLD", "MC.PA").
        period_days: Number of days of historical data to fetch.

    Returns:
        List of OHLCV dicts with keys: timestamp, open, high, low, close, volume.

    Raises:
        YFinanceError: If the download fails or returns empty data.
    """
    try:
        import yfinance as yf
    except ImportError:
        raise YFinanceError(
            "yfinance is not installed. Install with: uv sync --extra yfinance",
            symbol=symbol,
        )

    end = datetime.now(UTC)
    start = end - timedelta(days=period_days)

    logger.info(f"Fetching {symbol} from Yahoo Finance ({start.date()} to {end.date()})...")

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
        )
    except Exception as e:
        raise YFinanceError(f"Failed to download {symbol}: {e}", symbol=symbol)

    if df is None or df.empty:
        raise YFinanceError(f"No data returned for {symbol}", symbol=symbol)

    # Convert DataFrame → list of dicts (pandas stays internal to this function)
    klines: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        klines.append({
            "timestamp": idx.strftime("%Y-%m-%d"),  # type: ignore[union-attr]
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]),
        })

    logger.info(f"Retrieved {len(klines)} records for {symbol}")
    return klines


def ingest_yfinance_data(
    symbols: list[str] | None = None,
    period_days: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Main entry point for yfinance data ingestion (full refresh).

    Fetches historical OHLCV data for multiple traditional assets.

    Args:
        symbols: List of ticker symbols. Defaults to yfinance config symbols.
        period_days: Number of days to fetch. Defaults to yfinance config.

    Returns:
        Dictionary with symbol as key and list of OHLCV dicts as value.

    Example:
        >>> data = ingest_yfinance_data()
        >>> print(data["SPY"][0])
        {'timestamp': '2024-01-01', 'open': 470.0, ...}
    """
    cfg = load_yfinance_config()
    if symbols is None:
        symbols = list(cfg.symbols)
    if period_days is None:
        period_days = cfg.period_days

    result: dict[str, list[dict[str, Any]]] = {}
    failed_symbols: list[str] = []

    logger.info(f"Starting yfinance ingestion for {len(symbols)} symbols...")

    for symbol in symbols:
        try:
            klines = fetch_yfinance_klines(symbol, period_days)
            result[symbol] = klines
        except YFinanceError as e:
            logger.error(f"Failed to fetch {symbol}: {e.message}")
            failed_symbols.append(symbol)
            continue

    total_records = sum(len(v) for v in result.values())
    logger.info(
        f"yfinance ingestion complete: {total_records} records for {len(result)} symbols"
    )
    if failed_symbols:
        logger.warning(f"Failed symbols: {failed_symbols}")

    return result


def ingest_yfinance_incremental(
    symbols: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Incremental yfinance ingestion — only fetch new data since last ingest.

    Loads existing data from storage, finds the last date per symbol,
    fetches only new records, and returns merged data.

    Args:
        symbols: List of ticker symbols. Defaults to yfinance config symbols.

    Returns:
        Dictionary with merged old + new data for each symbol.
    """
    from src.config import load_config
    from src.storage import get_storage

    cfg = load_yfinance_config()
    pipeline = load_config()

    if symbols is None:
        symbols = list(cfg.symbols)

    storage = get_storage(pipeline.storage_backend)
    result: dict[str, list[dict[str, Any]]] = {}

    logger.info("Starting incremental yfinance ingestion...")

    for symbol in symbols:
        # Load existing data
        try:
            existing = storage.load_raw([symbol])
            existing_records = existing.get(symbol, [])
        except Exception:
            existing_records = []

        if existing_records:
            last_date_str = max(r["timestamp"] for r in existing_records)
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=UTC)
            days_since = (datetime.now(UTC) - last_date).days
            if days_since <= 1:
                logger.info(f"{symbol}: Already up to date")
                result[symbol] = existing_records
                continue
            logger.info(f"{symbol}: Last data {last_date_str}, fetching {days_since} new days")
        else:
            days_since = cfg.period_days
            logger.info(f"{symbol}: No existing data, fetching {days_since} days")

        # Fetch new data
        try:
            new_records = fetch_yfinance_klines(symbol, days_since + 5)
        except YFinanceError as e:
            logger.error(f"Failed to fetch {symbol}: {e.message}")
            result[symbol] = existing_records
            continue

        # Merge: existing + new (dedupe by timestamp)
        all_records = existing_records + new_records
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for r in all_records:
            if r["timestamp"] not in seen:
                seen.add(r["timestamp"])
                merged.append(r)
        merged.sort(key=lambda x: x["timestamp"])

        result[symbol] = merged
        logger.info(
            f"{symbol}: {len(existing_records)} existing + {len(new_records)} new = {len(merged)} total"
        )

    total = sum(len(v) for v in result.values())
    logger.info(f"Incremental yfinance ingestion complete: {total} total records")
    return result
