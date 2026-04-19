"""
Daily Binance trading-universe selector.

Fetches 24h ticker data and exchange info from the Binance public API,
applies liquidity / volatility / momentum / status filters, ranks by
``quoteVolume × daily_range``, and persists the top-N symbols as a
durable artifact that downstream trading code can read via
``storage.load_output("universe_latest")`` or ``universe_YYYYMMDD``.

The module is intentionally self-contained: no pandas, no DataSource
coupling — just a ranking pass over a ticker snapshot.

Example usage:
    >>> from src.pipeline.symbol_selector import select_universe
    >>> payload = select_universe()
    >>> payload["universe_size"]
    30
    >>> payload["symbols"][:3]
    ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.config import SymbolSelectorConfig, load_symbol_selector_config
from src.pipeline.ingest import BinanceAPIError, make_binance_request
from src.storage import get_storage
from src.storage.base import Storage

logger = logging.getLogger(__name__)

_TICKER_24H_ENDPOINT = "/api/v3/ticker/24hr"
_EXCHANGE_INFO_ENDPOINT = "/api/v3/exchangeInfo"


class SymbolSelectorError(Exception):
    """Raised when the daily universe cannot be built."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


# =============================================================================
# Binance fetchers
# =============================================================================


def fetch_24h_tickers(
    api_base: str,
    rate_limit_delay: float = 0.5,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """Fetch the 24h ticker snapshot for every symbol on Binance."""
    url = f"{api_base.rstrip('/')}{_TICKER_24H_ENDPOINT}"
    data = make_binance_request(url, params={}, rate_limit_delay=rate_limit_delay, max_retries=max_retries)
    if not isinstance(data, list):
        raise SymbolSelectorError(
            f"Unexpected /ticker/24hr payload type: {type(data).__name__}",
            operation="fetch_24h_tickers",
        )
    return data


def fetch_trading_symbols(
    api_base: str,
    rate_limit_delay: float = 0.5,
    max_retries: int = 3,
) -> set[str]:
    """Return the set of symbols with ``status == "TRADING"`` from exchangeInfo."""
    url = f"{api_base.rstrip('/')}{_EXCHANGE_INFO_ENDPOINT}"
    data = make_binance_request(url, params={}, rate_limit_delay=rate_limit_delay, max_retries=max_retries)
    symbols = data.get("symbols") if isinstance(data, dict) else None
    if not isinstance(symbols, list):
        raise SymbolSelectorError(
            "Unexpected /exchangeInfo payload: missing 'symbols' list",
            operation="fetch_trading_symbols",
        )
    return {
        entry["symbol"]
        for entry in symbols
        if isinstance(entry, dict)
        and entry.get("status") == "TRADING"
        and "symbol" in entry
    }


# =============================================================================
# Filtering & ranking
# =============================================================================


def _safe_float(value: Any) -> float | None:
    """Return value as float, or None if not convertible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_leveraged(base: str, leveraged_suffixes: tuple[str, ...]) -> bool:
    """True if ``base`` ends with any leveraged-token marker (UP, DOWN, BULL, BEAR)."""
    return any(base.endswith(suffix) for suffix in leveraged_suffixes)


def _filter_pairs(
    tickers: list[dict[str, Any]],
    trading_set: set[str],
    cfg: SymbolSelectorConfig,
) -> list[dict[str, Any]]:
    """
    Apply filters in order, logging the survivor count after each gate.

    Gates (in order): quote_asset suffix, leveraged-token, stablecoin blocklist,
    exchange status=TRADING, liquidity, volatility (daily range), momentum.
    Returns annotated ticker dicts with ``daily_range`` and numeric fields coerced.
    """
    initial = len(tickers)
    logger.info("symbol_selector: initial=%d tickers", initial)

    # Gate 1: quote asset suffix
    quote = cfg.quote_asset
    quote_len = len(quote)
    after_quote = [t for t in tickers if isinstance(t.get("symbol"), str) and t["symbol"].endswith(quote)]
    logger.info("symbol_selector: after_quote_asset(%s)=%d", quote, len(after_quote))

    # Gate 2: leveraged-token exclusion (base asset, without quote suffix)
    after_leverage = [
        t for t in after_quote
        if not _is_leveraged(t["symbol"][:-quote_len], cfg.leveraged_suffixes)
    ]
    logger.info("symbol_selector: after_leveraged_exclusion=%d", len(after_leverage))

    # Gate 3: stablecoin blocklist
    blocklist = set(cfg.stablecoin_blocklist)
    after_stable = [t for t in after_leverage if t["symbol"] not in blocklist]
    logger.info("symbol_selector: after_stablecoin_blocklist=%d", len(after_stable))

    # Gate 4: status=TRADING
    after_status = [t for t in after_stable if t["symbol"] in trading_set]
    logger.info("symbol_selector: after_status_trading=%d", len(after_status))

    # Gate 5: liquidity — quoteVolume > threshold
    liquid: list[dict[str, Any]] = []
    for t in after_status:
        qv = _safe_float(t.get("quoteVolume"))
        if qv is None or qv <= cfg.min_quote_volume:
            continue
        t_copy = dict(t)
        t_copy["quoteVolume"] = qv
        liquid.append(t_copy)
    logger.info("symbol_selector: after_liquidity(>%s)=%d", cfg.min_quote_volume, len(liquid))

    # Gate 6: volatility (daily range) — (high - low) / low > threshold
    volatile: list[dict[str, Any]] = []
    for t in liquid:
        high = _safe_float(t.get("highPrice"))
        low = _safe_float(t.get("lowPrice"))
        if high is None or low is None or low <= 0.0:
            continue
        daily_range = (high - low) / low
        if daily_range <= cfg.min_daily_range:
            continue
        t["highPrice"] = high
        t["lowPrice"] = low
        t["daily_range"] = daily_range
        volatile.append(t)
    logger.info("symbol_selector: after_daily_range(>%s)=%d", cfg.min_daily_range, len(volatile))

    # Gate 7: momentum — |priceChangePercent| > threshold (optional)
    if not cfg.momentum_filter_enabled:
        for t in volatile:
            pct = _safe_float(t.get("priceChangePercent"))
            t["priceChangePercent"] = pct if pct is not None else 0.0
        logger.info("symbol_selector: momentum_filter_disabled, final=%d", len(volatile))
        return volatile

    momentum: list[dict[str, Any]] = []
    for t in volatile:
        pct = _safe_float(t.get("priceChangePercent"))
        if pct is None or abs(pct) <= cfg.min_abs_price_change_pct:
            continue
        t["priceChangePercent"] = pct
        momentum.append(t)
    logger.info("symbol_selector: after_momentum(|%%|>%s)=%d", cfg.min_abs_price_change_pct, len(momentum))
    return momentum


def _rank_and_select(filtered: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    """
    Rank filtered tickers by score = quoteVolume * daily_range, descending.
    Deterministic tie-break: symbol alphabetical ascending.
    """
    ranked = sorted(
        filtered,
        key=lambda t: (-(t["quoteVolume"] * t["daily_range"]), t["symbol"]),
    )
    return ranked[:top_n]


def _build_payload(
    selected: list[dict[str, Any]],
    cfg: SymbolSelectorConfig,
    selected_at: datetime,
) -> dict[str, Any]:
    """Wrap the ranked list with reproducibility metadata."""
    universe = [
        {
            "symbol": t["symbol"],
            "score": t["quoteVolume"] * t["daily_range"],
            "quoteVolume": t["quoteVolume"],
            "daily_range": t["daily_range"],
            "priceChangePercent": t["priceChangePercent"],
        }
        for t in selected
    ]
    return {
        "selected_at": selected_at.isoformat(),
        "source_snapshot_url": f"{cfg.binance_api_base.rstrip('/')}{_TICKER_24H_ENDPOINT}",
        "universe_size": len(universe),
        "symbols": [row["symbol"] for row in universe],
        "universe": universe,
        "thresholds": {
            "min_quote_volume": cfg.min_quote_volume,
            "min_daily_range": cfg.min_daily_range,
            "min_abs_price_change_pct": cfg.min_abs_price_change_pct,
            "momentum_filter_enabled": cfg.momentum_filter_enabled,
            "top_n": cfg.top_n,
            "quote_asset": cfg.quote_asset,
            "leveraged_suffixes": list(cfg.leveraged_suffixes),
            "stablecoin_blocklist": list(cfg.stablecoin_blocklist),
        },
    }


# =============================================================================
# Orchestration
# =============================================================================


def select_universe(
    storage: Storage | None = None,
    cfg: SymbolSelectorConfig | None = None,
    selected_at: datetime | None = None,
) -> dict[str, Any]:
    """
    Build today's Binance trading universe and persist it via the Storage ABC.

    Writes two keys:
      - ``universe_YYYYMMDD`` (audit trail, one per day)
      - ``universe_latest``   (stable alias for downstream readers)

    Args:
        storage: Storage backend. Defaults to ``get_storage()``.
        cfg: Selector configuration. Defaults to ``load_symbol_selector_config()``.
        selected_at: Snapshot timestamp. Defaults to ``datetime.now(UTC)``. Injectable for tests.

    Returns:
        The payload dict (same shape persisted under both keys).

    Raises:
        SymbolSelectorError: If the API returns malformed data or fewer than
            ``cfg.min_universe_size`` symbols survive the filter cascade.
        BinanceAPIError: Propagated from the HTTP layer on unrecoverable network errors.
    """
    if cfg is None:
        cfg = load_symbol_selector_config()
    if storage is None:
        storage = get_storage()
    if selected_at is None:
        selected_at = datetime.now(UTC)

    try:
        tickers = fetch_24h_tickers(cfg.binance_api_base, cfg.rate_limit_delay, cfg.max_retries)
        trading_set = fetch_trading_symbols(cfg.binance_api_base, cfg.rate_limit_delay, cfg.max_retries)
    except BinanceAPIError:
        raise
    except Exception as exc:
        raise SymbolSelectorError(
            f"Failed to fetch Binance snapshot: {exc}", operation="fetch"
        ) from exc

    filtered = _filter_pairs(tickers, trading_set, cfg)
    selected = _rank_and_select(filtered, cfg.top_n)

    if len(selected) < cfg.min_universe_size:
        raise SymbolSelectorError(
            f"Universe too small: {len(selected)} survivors < min_universe_size={cfg.min_universe_size}",
            operation="rank_and_select",
        )

    payload = _build_payload(selected, cfg, selected_at)

    dated_key = f"universe_{selected_at.strftime('%Y%m%d')}"
    storage.save_output(payload, dated_key)
    storage.save_output(payload, "universe_latest")
    logger.info(
        "symbol_selector: persisted universe size=%d keys=[%s, universe_latest]",
        payload["universe_size"],
        dated_key,
    )

    return payload


__all__ = [
    "SymbolSelectorError",
    "fetch_24h_tickers",
    "fetch_trading_symbols",
    "select_universe",
]
