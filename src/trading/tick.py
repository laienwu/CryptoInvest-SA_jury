"""
Tick orchestrator — invoked by Airflow every 5 minutes.

One tick does, in order:

1. Load config + universe (``universe_latest``).
2. Open the testnet client and the ledger.
3. **Reconcile** open ledger positions against the exchange (trust exchange).
4. Check kill switches: daily loss, equity floor, position cap.
5. For each universe symbol: fetch closed 5m bars, run the strategy, and
   open entries with a protective stop-loss — all gated by risk + filters.
6. Close positions whose strategy signal has flipped to SELL.

Idempotency comes from deterministic ``client_order_id``s. Safety comes from
the mainnet block in ``binance_client.py`` and ``dry_run=True`` by default.
"""

from __future__ import annotations

import contextlib
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from src.pipeline.ingest import BinanceAPIError, fetch_klines
from src.storage import get_storage
from src.storage.base import Storage, StorageError
from src.trading.binance_client import BinanceClient, new_client_order_id
from src.trading.config import TradingConfig, load_trading_config
from src.trading.errors import FilterViolationError, LedgerError, TradingError
from src.trading.filters import (
    SymbolFilters,
    ensure_order_valid,
    parse_symbol_filters,
    quantize_price,
    quantize_qty,
)
from src.trading.ledger import OpenPosition, TradeLedger
from src.trading.risk import (
    can_open_new_position,
    compute_position_qty,
    cost_within_budget,
    kill_switch_tripped,
)
from src.trading.strategy import SmaCrossoverStrategy, Strategy

logger = logging.getLogger(__name__)

# Safety margin for the stop-limit price so it actually fills once triggered.
_STOP_LIMIT_SLIPPAGE: float = 0.002  # 0.2% below the stop trigger on a sell stop

# Binance's "Order does not exist." — returned by /api/v3/order when the
# orderId / origClientOrderId we're asking about is gone from exchange
# history. On testnet this happens routinely (periodic resets wipe order
# history); on mainnet it means someone manually canceled the order outside
# our code. Either way, the ledger row is unreconcilable and should be retired
# so it stops blocking re-entry on the symbol and stops spamming tick errors.
_BINANCE_CODE_ORDER_NOT_FOUND: int = -2013

# Modules whose loggers should follow ``TRADING_LOG_LEVEL`` — everything the
# tick touches end-to-end.
_TRADING_LOG_TREES: tuple[str, ...] = ("src.trading", "src.pipeline")


def _apply_log_level() -> None:
    """Honor ``TRADING_LOG_LEVEL`` on the trading/pipeline logger trees.

    Airflow already installs a root handler, so setting just the level is
    enough — we don't touch handlers. Missing / unknown values leave levels
    alone so the DAG's default logging isn't disturbed.
    """
    raw = os.getenv("TRADING_LOG_LEVEL")
    if not raw:
        return
    level = logging.getLevelName(raw.strip().upper())
    if not isinstance(level, int):
        logger.warning("TRADING_LOG_LEVEL=%r is not a valid level", raw)
        return
    for name in _TRADING_LOG_TREES:
        logging.getLogger(name).setLevel(level)


def run_tick(
    cfg: TradingConfig | None = None,
    storage: Storage | None = None,
    client: BinanceClient | None = None,
    ledger: TradeLedger | None = None,
    strategy: Strategy | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """
    Execute one trading tick. Returns a summary dict for the DAG log.

    All collaborators are injectable so the tick is fully unit-testable
    without reaching the network or disk.
    """
    if cfg is None:
        cfg = load_trading_config()
    _apply_log_level()
    now = now_utc or datetime.now(UTC)
    logger.info(
        "Tick start: dry_run=%s base=%s ledger=%s interval=%s",
        cfg.dry_run, cfg.testnet_base_url, cfg.ledger_path, cfg.candle_interval,
    )

    summary: dict[str, Any] = {
        "now_utc": now.isoformat(),
        "dry_run": cfg.dry_run,
        "reconciled": 0,
        "signals": {"BUY": 0, "SELL": 0, "HOLD": 0},
        "orders_placed": 0,
        "orders_skipped": 0,
        "positions_closed": 0,
        "kill_switch": False,
        "errors": [],
    }

    owns_client = client is None
    owns_ledger = ledger is None

    if storage is None:
        storage = get_storage()
    if client is None:
        client = BinanceClient(
            api_key=cfg.api_key,
            api_secret=cfg.api_secret,
            base_url=cfg.testnet_base_url,
            dry_run=cfg.dry_run,
            rate_limit_delay=cfg.rate_limit_delay,
            max_retries=cfg.max_retries,
            recv_window_ms=cfg.recv_window_ms,
        )
        client.sync_time()
    if ledger is None:
        ledger = TradeLedger(cfg.ledger_path)
    strategy_impl: Strategy
    if strategy is not None:
        strategy_impl = strategy
    else:
        strategy_impl = SmaCrossoverStrategy(
            short_window=cfg.sma_short, long_window=cfg.sma_long,
        )

    try:
        universe = _load_universe(storage, summary)
        if not universe:
            return summary

        equity_usdt = _query_equity(client, summary)
        if equity_usdt is None or equity_usdt < cfg.min_equity_floor_usdt:
            summary["kill_switch"] = True
            summary["errors"].append(
                f"equity_floor: {equity_usdt} < {cfg.min_equity_floor_usdt}"
            )
            logger.warning("Equity floor breached — no new entries this tick")
            return summary

        if kill_switch_tripped(ledger, equity_usdt, cfg.max_daily_loss_pct, now):
            summary["kill_switch"] = True
            logger.warning("Daily-loss kill switch tripped — no new entries this tick")
            return summary

        _reconcile(client, ledger, cfg, summary, now)

        exchange_info = _load_exchange_info(client, universe, summary)
        _close_on_sell_signals(client, ledger, strategy_impl, cfg, exchange_info, summary, now)
        _open_on_buy_signals(
            client, ledger, strategy_impl, cfg, universe, exchange_info,
            equity_usdt, summary, now,
        )

    except (BinanceAPIError, TradingError, StorageError) as exc:
        summary["errors"].append(f"{type(exc).__name__}: {exc}")
        logger.exception("Tick aborted: %s", exc)
    finally:
        # Persist the summary for the dashboard's tick-history view. Swallow
        # any audit-write failure — a failed audit must not mask the tick
        # result the caller is about to act on.
        try:
            ledger.record_tick_run(summary)
        except LedgerError as exc:
            logger.warning("Failed to persist tick_run summary: %s", exc)
        if owns_ledger:
            ledger.close()
        # BinanceClient holds no resources; nothing to release.
        _ = owns_client

    logger.info(
        "Tick done: placed=%d skipped=%d closed=%d reconciled=%d "
        "signals=%s kill=%s errors=%d",
        summary["orders_placed"], summary["orders_skipped"],
        summary["positions_closed"], summary["reconciled"],
        summary["signals"], summary["kill_switch"], len(summary["errors"]),
    )
    return summary


# -- stages ------------------------------------------------------------------


def _load_universe(storage: Storage, summary: dict[str, Any]) -> list[str]:
    try:
        payload = storage.load_output("universe_latest")
    except StorageError as exc:
        summary["errors"].append(f"universe_missing: {exc}")
        logger.error("No universe_latest — run symbol_selector first")
        return []
    universe = payload.get("symbols") or []
    summary["universe_size"] = len(universe)
    return list(universe)


def _query_equity(client: BinanceClient, summary: dict[str, Any]) -> float | None:
    """USDT-equivalent equity. Conservative: sum of free+locked USDT balance."""
    try:
        account = client.get_account()
    except BinanceAPIError as exc:
        summary["errors"].append(f"get_account: {exc}")
        return None
    balances = account.get("balances", [])
    for b in balances:
        if b.get("asset") == "USDT":
            try:
                equity = float(b.get("free", 0.0)) + float(b.get("locked", 0.0))
            except (TypeError, ValueError):
                equity = 0.0
            summary["equity_usdt"] = equity
            return equity
    summary["equity_usdt"] = 0.0
    return 0.0


def _load_exchange_info(
    client: BinanceClient,
    universe: list[str],
    summary: dict[str, Any],
) -> dict[str, SymbolFilters]:
    # Universe is ranked on mainnet but we trade on testnet, so some entries
    # may not exist here. Binance fails the whole batched ``symbols=[...]``
    # call on any invalid symbol, so fetch the full exchangeInfo and let the
    # caller's ``.get(symbol) is None`` path drop anything testnet can't trade.
    universe_set = set(universe)
    try:
        info = client.get_exchange_info()
    except BinanceAPIError as exc:
        summary["errors"].append(f"exchange_info: {exc}")
        return {}
    out: dict[str, SymbolFilters] = {}
    for entry in info.get("symbols", []):
        sym = entry.get("symbol")
        if sym not in universe_set:
            continue
        filters = entry.get("filters", [])
        if not isinstance(filters, list):
            continue
        try:
            out[sym] = parse_symbol_filters(sym, filters)
        except FilterViolationError as exc:
            logger.warning("Skipping %s: %s", sym, exc)
    return out


def _reconcile(
    client: BinanceClient,
    ledger: TradeLedger,
    cfg: TradingConfig,
    summary: dict[str, Any],
    now: datetime,
) -> None:
    """Align the ledger with exchange state for every open position.

    Exchange is the source of truth. If the stop was triggered while we
    slept, mark the position closed with the realized P&L.
    """
    open_positions = ledger.get_open_positions()
    logger.info("Reconcile: %d open position(s) to check", len(open_positions))
    for pos in open_positions:
        logger.debug(
            "Reconcile %s coid=%s stop=%s exchange_order_id=%s",
            pos.symbol, pos.client_order_id, pos.stop_order_id,
            pos.exchange_order_id,
        )
        if not pos.stop_order_id:
            # Orphaned ``placed`` row — the entry reached the exchange (we have
            # an exchange_order_id) but the tick never advanced to ``filled``
            # (process killed mid-entry, or a pre-fix tick left it behind).
            # Check the entry on exchange: if it's in a terminal non-fill state,
            # retire the ledger row so it stops blocking re-entry on the symbol.
            if pos.exchange_order_id:
                _reconcile_orphan_placed(client, ledger, pos, summary)
            continue
        try:
            order = client.get_order(
                symbol=pos.symbol,
                orig_client_order_id=pos.stop_order_id,
            )
        except BinanceAPIError as exc:
            if exc.binance_code == _BINANCE_CODE_ORDER_NOT_FOUND:
                _retire_missing_stop(ledger, pos, summary)
                continue
            summary["errors"].append(f"reconcile({pos.symbol}): {exc}")
            continue

        status = str(order.get("status", ""))
        if status == "FILLED":
            executed_qty = float(order.get("executedQty", pos.filled_qty) or 0.0)
            # Binance returns cummulativeQuoteQty = price*qty executed
            quote_qty = float(order.get("cummulativeQuoteQty", 0.0) or 0.0)
            exit_price = (quote_qty / executed_qty) if executed_qty > 0 else pos.entry_price
            pnl = (exit_price - pos.entry_price) * executed_qty
            ledger.mark_closed(
                client_order_id=pos.client_order_id,
                exit_price=exit_price,
                exit_client_order_id=pos.stop_order_id,
                realized_pnl=pnl,
                closed_at=now,
            )
            if cfg.post_stop_cooldown_minutes > 0:
                ledger.lock_pair(
                    symbol=pos.symbol,
                    locked_until=now + timedelta(minutes=cfg.post_stop_cooldown_minutes),
                    reason="stop_fill_cooldown",
                )
            summary["reconciled"] += 1
            logger.info("Reconciled stop fill for %s: pnl=%.4f USDT", pos.symbol, pnl)


# Binance order statuses that mean "entry will never fill" — safe to retire.
_ENTRY_TERMINAL_FAILURE: frozenset[str] = frozenset(
    {"EXPIRED", "CANCELED", "REJECTED", "EXPIRED_IN_MATCH"}
)


def _retire_missing_stop(
    ledger: TradeLedger,
    pos: OpenPosition,
    summary: dict[str, Any],
) -> None:
    """Retire a filled-position ledger row whose stop order is gone from the exchange.

    No P&L is booked: we can't infer an exit price without an execution on
    the exchange. The position is marked ``failed`` (not ``closed``) to signal
    that realized P&L is unknown — downstream queries that aggregate realized
    P&L will correctly exclude this row. The symbol becomes re-entry-eligible
    on the next tick, and the tick stops logging the recurring -2013.
    """
    note = (
        f"stop order {pos.stop_order_id} not found on exchange (-2013); "
        "likely testnet reset or manual cancel — retiring without realized P&L"
    )
    with contextlib.suppress(LedgerError):
        ledger.mark_failed(pos.client_order_id, note)
    summary["reconciled"] += 1
    logger.warning("Retired unreconcilable position %s: %s", pos.symbol, note)


def _reconcile_orphan_placed(
    client: BinanceClient,
    ledger: TradeLedger,
    pos: OpenPosition,
    summary: dict[str, Any],
) -> None:
    """Retire a ``placed`` ledger row whose entry order never advanced to ``filled``."""
    try:
        order = client.get_order(symbol=pos.symbol, order_id=pos.exchange_order_id)
    except BinanceAPIError as exc:
        if exc.binance_code == _BINANCE_CODE_ORDER_NOT_FOUND:
            note = (
                f"orphan placed: entry order_id={pos.exchange_order_id} not found "
                "on exchange (-2013); retiring"
            )
            with contextlib.suppress(LedgerError):
                ledger.mark_failed(pos.client_order_id, note)
            summary["reconciled"] += 1
            logger.info("Retired orphan placed row for %s: %s", pos.symbol, note)
            return
        summary["errors"].append(f"reconcile_orphan({pos.symbol}): {exc}")
        return
    status = str(order.get("status", ""))
    if status in _ENTRY_TERMINAL_FAILURE:
        note = f"orphan placed: entry {status} (exchange_order_id={pos.exchange_order_id})"
        with contextlib.suppress(LedgerError):
            ledger.mark_failed(pos.client_order_id, note)
        logger.info("Retired orphan placed row for %s: %s", pos.symbol, status)
    else:
        # FILLED/PARTIALLY_FILLED/NEW → real position or still pending. Don't
        # auto-advance; the operator needs to see this and attach a stop manually.
        logger.warning(
            "Orphan placed row on %s still has exchange status %s — leaving for ops",
            pos.symbol, status,
        )


def _fetch_closes(symbol: str, cfg: TradingConfig, lookback: int) -> list[float]:
    """Fetch recent closed bars. Drop the last bar — it may still be open."""
    now = datetime.now(UTC)
    # 5m interval × (lookback+1) bars, pad a bit for safety
    minutes_per_bar = _interval_minutes(cfg.candle_interval)
    start = now - timedelta(minutes=minutes_per_bar * (lookback + 2))
    bars = fetch_klines(
        symbol=symbol,
        interval=cfg.candle_interval,
        start_time=start,
        end_time=now,
        api_base=cfg.testnet_base_url,
        rate_limit_delay=cfg.rate_limit_delay,
        max_retries=cfg.max_retries,
    )
    if len(bars) < 2:
        return []
    # Drop the most recent (likely still open) bar
    closes = [float(b["close"]) for b in bars[:-1]]
    return closes


def _interval_minutes(interval: str) -> int:
    mapping = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
    return mapping.get(interval, 5)


def _open_on_buy_signals(
    client: BinanceClient,
    ledger: TradeLedger,
    strategy: Strategy,
    cfg: TradingConfig,
    universe: list[str],
    exchange_info: dict[str, SymbolFilters],
    equity_usdt: float,
    summary: dict[str, Any],
    now: datetime,
) -> None:
    held = ledger.get_open_symbols()
    lookback = max(cfg.candle_lookback, strategy.startup_candle_count)
    logger.info(
        "Open-signals scan: universe=%d held=%d tradable=%d equity=%.2f USDT",
        len(universe), len(held), len(exchange_info), equity_usdt,
    )
    # Track USDT committed within this tick. Each successful entry consumes
    # ``notional = qty * price`` of real balance; without this, sizing keeps
    # using the opening equity as if no money had been spent and the 4th+
    # entry hits Binance with ``insufficient balance``.
    remaining_usdt = equity_usdt

    for symbol in universe:
        if symbol in held:
            continue
        if ledger.is_pair_locked(symbol, now):
            summary["orders_skipped"] += 1
            continue
        if not can_open_new_position(ledger, cfg.max_open_positions):
            logger.info("Max open positions (%d) reached — stopping entries",
                        cfg.max_open_positions)
            break

        filters = exchange_info.get(symbol)
        if filters is None:
            summary["orders_skipped"] += 1
            continue

        try:
            closes = _fetch_closes(symbol, cfg, lookback)
        except BinanceAPIError as exc:
            summary["errors"].append(f"klines({symbol}): {exc}")
            summary["orders_skipped"] += 1
            continue

        if not closes:
            summary["signals"]["HOLD"] += 1
            continue

        signal = strategy.generate_signal(closes)
        summary["signals"][signal] = summary["signals"].get(signal, 0) + 1

        if signal != "BUY":
            continue

        entry_price = closes[-1]
        raw_qty = compute_position_qty(
            equity_usdt=equity_usdt,
            risk_per_trade=cfg.risk_per_trade,
            stop_loss_pct=cfg.stop_loss_pct,
            entry_price=entry_price,
        )
        qty = quantize_qty(raw_qty, filters.step_size)
        price = quantize_price(entry_price, filters.tick_size)
        notional = qty * price

        if qty <= 0 or notional <= 0:
            summary["orders_skipped"] += 1
            continue

        try:
            ensure_order_valid(qty, price, filters)
        except FilterViolationError as exc:
            logger.info("Skip %s: %s", symbol, exc)
            summary["orders_skipped"] += 1
            continue

        if not cost_within_budget(
            notional_usdt=notional,
            equity_usdt=equity_usdt,
            risk_per_trade=cfg.risk_per_trade,
            max_cost_fraction_of_risk=cfg.max_cost_fraction_of_risk,
        ):
            logger.info("Skip %s: cost > %.0f%% of risk budget",
                        symbol, cfg.max_cost_fraction_of_risk * 100)
            summary["orders_skipped"] += 1
            continue

        if notional > remaining_usdt:
            logger.info("Skip %s: notional %.2f > remaining USDT %.2f",
                        symbol, notional, remaining_usdt)
            summary["orders_skipped"] += 1
            continue

        committed = _place_entry(
            client, ledger, cfg, symbol, qty, price, filters, summary, now,
        )
        remaining_usdt -= committed


def _place_entry(
    client: BinanceClient,
    ledger: TradeLedger,
    cfg: TradingConfig,
    symbol: str,
    qty: float,
    price: float,
    filters: SymbolFilters,
    summary: dict[str, Any],
    now: datetime,
) -> float:
    """Place a MARKET entry + protective stop. Returns the notional committed,
    or 0.0 if the entry didn't fill — so the caller can decrement its running
    USDT budget and stop sizing trades it can no longer afford."""
    coid = new_client_order_id(prefix=f"e-{symbol[:6]}")
    if ledger.has_client_order_id(coid):  # vanishingly rare; stay safe
        summary["orders_skipped"] += 1
        return 0.0

    stop_trigger = price * (1.0 - cfg.stop_loss_pct)
    stop_limit = stop_trigger * (1.0 - _STOP_LIMIT_SLIPPAGE)
    stop_trigger = quantize_price(stop_trigger, filters.tick_size)
    stop_limit = quantize_price(stop_limit, filters.tick_size)

    try:
        ledger.record_intent(
            client_order_id=coid,
            symbol=symbol,
            side="BUY",
            intended_qty=qty,
            entry_price=price,
            stop_price=stop_trigger,
            strategy="sma_crossover",
            entry_tag="sma_cross_up",
            now_utc=now,
        )
        order = client.place_market_order(symbol, "BUY", qty, coid)
        ledger.mark_placed(coid, str(order.get("orderId", "")))

        executed_qty = float(order.get("executedQty", qty) or qty)
        # Prefer the exchange's cummulativeQuoteQty to back out avg fill price.
        quote_qty = float(order.get("cummulativeQuoteQty", 0.0) or 0.0)
        avg_fill = (quote_qty / executed_qty) if executed_qty > 0 and quote_qty > 0 else price

        entry_status = str(order.get("status", ""))
        if entry_status in ("FILLED", "PARTIALLY_FILLED"):
            ledger.mark_filled(coid, executed_qty, avg_fill, filled_at=now)

            stop_coid = new_client_order_id(prefix=f"s-{symbol[:6]}")
            stop_order = client.place_stop_loss_limit(
                symbol=symbol,
                side="SELL",
                qty=executed_qty,
                stop_price=stop_trigger,
                limit_price=stop_limit,
                client_order_id=stop_coid,
            )
            ledger.attach_stop(coid, stop_coid, stop_trigger)
            logger.info(
                "Opened %s qty=%s fill=%s stop=%s (coid=%s, stop=%s)",
                symbol, executed_qty, avg_fill, stop_trigger, coid, stop_coid,
            )
            _ = stop_order
            summary["orders_placed"] += 1
            return executed_qty * avg_fill
        # MARKET order landed on the exchange but didn't fill (e.g. EXPIRED
        # due to thin testnet liquidity). Without this branch the ledger row
        # rots at ``placed`` forever — it has no ``stop_order_id`` so
        # reconcile skips it, and ``held`` blocks re-entry on the symbol.
        note = f"entry {entry_status or 'unknown'} with executedQty={executed_qty}"
        with contextlib.suppress(LedgerError):
            ledger.mark_failed(coid, note)
        summary["errors"].append(f"place({symbol}): {note}")
        logger.warning("Entry did not fill on %s: %s", symbol, note)
        return 0.0

    except (BinanceAPIError, LedgerError) as exc:
        summary["errors"].append(f"place({symbol}): {exc}")
        with contextlib.suppress(LedgerError):
            ledger.mark_failed(coid, str(exc))
        return 0.0


def _close_on_sell_signals(
    client: BinanceClient,
    ledger: TradeLedger,
    strategy: Strategy,
    cfg: TradingConfig,
    exchange_info: dict[str, SymbolFilters],
    summary: dict[str, Any],
    now: datetime,
) -> None:
    lookback = max(cfg.candle_lookback, strategy.startup_candle_count)
    open_positions = ledger.get_open_positions()
    logger.info("Close-signals scan: %d open position(s)", len(open_positions))
    for pos in open_positions:
        filters = exchange_info.get(pos.symbol)
        if filters is None:
            continue
        try:
            closes = _fetch_closes(pos.symbol, cfg, lookback)
        except BinanceAPIError as exc:
            summary["errors"].append(f"klines({pos.symbol}): {exc}")
            continue
        if not closes:
            continue

        signal = strategy.generate_signal(closes)
        if signal != "SELL":
            continue

        exit_price = quantize_price(closes[-1], filters.tick_size)
        qty = quantize_qty(pos.filled_qty, filters.step_size)
        if qty <= 0:
            continue

        exit_coid = new_client_order_id(prefix=f"x-{pos.symbol[:6]}")
        try:
            if pos.stop_order_id:
                client.cancel_order(pos.symbol, orig_client_order_id=pos.stop_order_id)
            order = client.place_market_order(pos.symbol, "SELL", qty, exit_coid)
            executed_qty = float(order.get("executedQty", qty) or qty)
            quote_qty = float(order.get("cummulativeQuoteQty", 0.0) or 0.0)
            avg_fill = (quote_qty / executed_qty) if executed_qty > 0 and quote_qty > 0 else exit_price
            pnl = (avg_fill - pos.entry_price) * executed_qty
            ledger.mark_closed(
                client_order_id=pos.client_order_id,
                exit_price=avg_fill,
                exit_client_order_id=exit_coid,
                realized_pnl=pnl,
                closed_at=now,
            )
            summary["positions_closed"] += 1
            logger.info("Closed %s: pnl=%.4f USDT (signal=SELL)", pos.symbol, pnl)
        except (BinanceAPIError, LedgerError) as exc:
            summary["errors"].append(f"close({pos.symbol}): {exc}")
