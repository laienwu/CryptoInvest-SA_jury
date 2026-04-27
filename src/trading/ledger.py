"""
DuckDB-backed trade ledger.

One row per *entry* trade. The entry row is updated in place as the trade
progresses (intent → placed → filled → closed / canceled / failed), which
gives us a single, easy-to-reconcile row per round-trip.

The ledger is the tick's memory across restarts. It is intentionally
orthogonal to the analytics warehouse (``data/trading/ledger.duckdb`` vs.
``data/`` Parquet), since the two have different lifecycles and SLAs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:  # pragma: no cover - duckdb is a hard dep in this project
    DUCKDB_AVAILABLE = False

from src.trading.errors import LedgerError

# Lifecycle states
STATUS_INTENT = "intent"
STATUS_PLACED = "placed"
STATUS_FILLED = "filled"      # entry filled, position open
STATUS_CLOSED = "closed"      # exit filled, P&L realized
STATUS_CANCELED = "canceled"
STATUS_FAILED = "failed"

OPEN_STATUSES: tuple[str, ...] = (STATUS_PLACED, STATUS_FILLED)


def _to_naive_utc(ts: datetime) -> datetime:
    """Convert a tz-aware datetime to naive UTC; leave naive inputs untouched."""
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class OpenPosition:
    """A snapshot of an open position the tick needs to manage."""

    client_order_id: str
    exchange_order_id: str | None
    symbol: str
    side: str
    filled_qty: float
    entry_price: float
    stop_price: float | None
    stop_order_id: str | None
    filled_at: datetime | None
    entry_tag: str | None = None


@dataclass(frozen=True)
class ClosedTradeRow:
    """Read-only row for dashboard order/trade listings."""

    client_order_id: str
    symbol: str
    side: str
    status: str
    strategy: str | None
    entry_tag: str | None
    intended_qty: float | None
    filled_qty: float | None
    entry_price: float | None
    exit_price: float | None
    realized_pnl: float | None
    opened_at: datetime | None
    filled_at: datetime | None
    closed_at: datetime | None
    notes: str | None


@dataclass(frozen=True)
class ActiveLock:
    """An active per-symbol cooldown."""

    symbol: str
    locked_until: datetime
    reason: str | None


@dataclass(frozen=True)
class TickRun:
    """One row of tick history, as persisted by run_tick()."""

    run_at: datetime
    dry_run: bool
    universe_size: int | None
    equity_usdt: float | None
    signals_buy: int
    signals_sell: int
    signals_hold: int
    orders_placed: int
    orders_skipped: int
    positions_closed: int
    reconciled: int
    kill_switch: bool
    error_count: int
    errors_json: str | None


class TradeLedger:
    """Thin DuckDB wrapper around the ``trades`` table."""

    def __init__(self, db_path: str | Path, *, read_only: bool = False):
        if not DUCKDB_AVAILABLE:
            raise LedgerError("DuckDB not installed. Run: uv add duckdb", operation="ledger_init")

        self.db_path = Path(db_path)
        self.read_only = read_only
        if not read_only:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.conn = duckdb.connect(str(self.db_path), read_only=read_only)
        except Exception as e:  # pragma: no cover - defensive
            raise LedgerError(f"Failed to open ledger at {self.db_path}: {e}",
                              operation="ledger_init") from e
        if not read_only:
            self._create_schema()

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> TradeLedger:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _create_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                client_order_id      TEXT PRIMARY KEY,
                exchange_order_id    TEXT,
                symbol               TEXT NOT NULL,
                side                 TEXT NOT NULL,
                strategy             TEXT,
                entry_tag            TEXT,
                status               TEXT NOT NULL,
                intended_qty         DOUBLE,
                filled_qty           DOUBLE,
                entry_price          DOUBLE,
                stop_price           DOUBLE,
                stop_order_id        TEXT,
                exit_price           DOUBLE,
                exit_client_order_id TEXT,
                realized_pnl         DOUBLE,
                fees                 DOUBLE,
                opened_at            TIMESTAMP,
                filled_at            TIMESTAMP,
                closed_at            TIMESTAMP,
                notes                TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS symbol_locks (
                symbol       TEXT PRIMARY KEY,
                locked_until TIMESTAMP NOT NULL,
                reason       TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tick_runs (
                run_at            TIMESTAMP NOT NULL,
                dry_run           BOOLEAN,
                universe_size     INTEGER,
                equity_usdt       DOUBLE,
                signals_buy       INTEGER,
                signals_sell      INTEGER,
                signals_hold      INTEGER,
                orders_placed     INTEGER,
                orders_skipped    INTEGER,
                positions_closed  INTEGER,
                reconciled        INTEGER,
                kill_switch       BOOLEAN,
                error_count       INTEGER,
                errors_json       TEXT
            )
            """
        )
        # Backfill for ledgers created before entry_tag landed.
        self._ensure_column("trades", "entry_tag", "TEXT")

    def _ensure_column(self, table: str, column: str, col_type: str) -> None:
        rows = self.conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            [table],
        ).fetchall()
        if not any(r[0] == column for r in rows):
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")  # noqa: S608

    # -- writes --------------------------------------------------------------

    def record_intent(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        intended_qty: float,
        entry_price: float,
        stop_price: float | None,
        strategy: str,
        entry_tag: str | None = None,
        now_utc: datetime | None = None,
    ) -> None:
        """Insert a new entry trade in the ``intent`` state."""
        now = now_utc or datetime.now(UTC)
        logger.debug(
            "ledger record_intent coid=%s sym=%s side=%s qty=%s entry=%s stop=%s",
            client_order_id, symbol, side, intended_qty, entry_price, stop_price,
        )
        try:
            self.conn.execute(
                """
                INSERT INTO trades (
                    client_order_id, symbol, side, strategy, entry_tag, status,
                    intended_qty, entry_price, stop_price, opened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [client_order_id, symbol, side, strategy, entry_tag, STATUS_INTENT,
                 intended_qty, entry_price, stop_price, now],
            )
        except Exception as e:
            raise LedgerError(
                f"Failed to record intent for {client_order_id}: {e}",
                operation="record_intent",
            ) from e

    def mark_placed(self, client_order_id: str, exchange_order_id: str) -> None:
        self._update(
            "UPDATE trades SET status = ?, exchange_order_id = ? WHERE client_order_id = ?",
            [STATUS_PLACED, exchange_order_id, client_order_id],
            operation="mark_placed",
        )

    def mark_filled(
        self,
        client_order_id: str,
        filled_qty: float,
        avg_fill_price: float,
        filled_at: datetime | None = None,
    ) -> None:
        ts = filled_at or datetime.now(UTC)
        self._update(
            """
            UPDATE trades
               SET status = ?, filled_qty = ?, entry_price = ?, filled_at = ?
             WHERE client_order_id = ?
            """,
            [STATUS_FILLED, filled_qty, avg_fill_price, ts, client_order_id],
            operation="mark_filled",
        )

    def attach_stop(self, client_order_id: str, stop_order_id: str, stop_price: float) -> None:
        self._update(
            "UPDATE trades SET stop_order_id = ?, stop_price = ? WHERE client_order_id = ?",
            [stop_order_id, stop_price, client_order_id],
            operation="attach_stop",
        )

    def mark_closed(
        self,
        client_order_id: str,
        exit_price: float,
        exit_client_order_id: str,
        realized_pnl: float,
        fees: float = 0.0,
        closed_at: datetime | None = None,
    ) -> None:
        ts = closed_at or datetime.now(UTC)
        self._update(
            """
            UPDATE trades
               SET status = ?, exit_price = ?, exit_client_order_id = ?,
                   realized_pnl = ?, fees = ?, closed_at = ?
             WHERE client_order_id = ?
            """,
            [STATUS_CLOSED, exit_price, exit_client_order_id,
             realized_pnl, fees, ts, client_order_id],
            operation="mark_closed",
        )

    def mark_canceled(self, client_order_id: str, note: str | None = None) -> None:
        self._update(
            """
            UPDATE trades
               SET status = ?, closed_at = ?, notes = COALESCE(?, notes)
             WHERE client_order_id = ?
            """,
            [STATUS_CANCELED, datetime.now(UTC), note, client_order_id],
            operation="mark_canceled",
        )

    def mark_failed(self, client_order_id: str, note: str) -> None:
        self._update(
            """
            UPDATE trades
               SET status = ?, closed_at = ?, notes = ?
             WHERE client_order_id = ?
            """,
            [STATUS_FAILED, datetime.now(UTC), note, client_order_id],
            operation="mark_failed",
        )

    def _update(self, sql: str, params: list[Any], operation: str) -> None:
        logger.debug("ledger %s params=%s", operation, params)
        try:
            self.conn.execute(sql, params)
        except Exception as e:
            raise LedgerError(f"{operation} failed: {e}", operation=operation) from e

    # -- reads ---------------------------------------------------------------

    def has_client_order_id(self, client_order_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM trades WHERE client_order_id = ? LIMIT 1",
            [client_order_id],
        ).fetchone()
        return row is not None

    def get_open_positions(self) -> list[OpenPosition]:
        """Positions whose entry has been placed or filled but not yet closed."""
        rows = self.conn.execute(
            """
            SELECT client_order_id, exchange_order_id, symbol, side,
                   filled_qty, entry_price, stop_price, stop_order_id,
                   filled_at, entry_tag
              FROM trades
             WHERE status IN (?, ?)
             ORDER BY opened_at
            """,
            [STATUS_PLACED, STATUS_FILLED],
        ).fetchall()
        return [
            OpenPosition(
                client_order_id=r[0],
                exchange_order_id=r[1],
                symbol=r[2],
                side=r[3],
                filled_qty=float(r[4] or 0.0),
                entry_price=float(r[5] or 0.0),
                stop_price=float(r[6]) if r[6] is not None else None,
                stop_order_id=r[7],
                filled_at=r[8],
                entry_tag=r[9],
            )
            for r in rows
        ]

    # -- symbol locks --------------------------------------------------------

    def lock_pair(self, symbol: str, locked_until: datetime, reason: str | None = None) -> None:
        """Prevent new entries on ``symbol`` until ``locked_until`` (UTC)."""
        # DuckDB TIMESTAMP is naive and would otherwise coerce tz-aware inputs
        # to local time. Normalize to naive UTC so the round-trip is lossless.
        stored = _to_naive_utc(locked_until)
        try:
            self.conn.execute(
                """
                INSERT INTO symbol_locks (symbol, locked_until, reason)
                     VALUES (?, ?, ?)
                ON CONFLICT (symbol) DO UPDATE
                        SET locked_until = excluded.locked_until,
                            reason       = excluded.reason
                """,
                [symbol, stored, reason],
            )
        except Exception as e:
            raise LedgerError(f"lock_pair({symbol}) failed: {e}",
                              operation="lock_pair") from e

    def unlock_pair(self, symbol: str) -> None:
        self._update(
            "DELETE FROM symbol_locks WHERE symbol = ?",
            [symbol],
            operation="unlock_pair",
        )

    def is_pair_locked(self, symbol: str, now_utc: datetime | None = None) -> bool:
        now = now_utc or datetime.now(UTC)
        row = self.conn.execute(
            "SELECT locked_until FROM symbol_locks WHERE symbol = ?",
            [symbol],
        ).fetchone()
        if not row:
            return False
        locked_until = row[0]
        # DuckDB TIMESTAMP columns come back tz-naive; we always store UTC.
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=UTC)
        # Lazy GC: auto-clear expired locks so they don't accumulate forever.
        if locked_until <= now:
            self.conn.execute("DELETE FROM symbol_locks WHERE symbol = ?", [symbol])
            return False
        return True

    def get_open_position_count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM trades WHERE status IN (?, ?)",
            [STATUS_PLACED, STATUS_FILLED],
        ).fetchone()
        return int(row[0]) if row else 0

    def get_open_symbols(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT symbol FROM trades WHERE status IN (?, ?)",
            [STATUS_PLACED, STATUS_FILLED],
        ).fetchall()
        return {r[0] for r in rows}

    def get_realized_pnl_today(self, now_utc: datetime | None = None) -> float:
        """Sum of realized P&L for positions closed since 00:00 UTC of ``now_utc``."""
        now = now_utc or datetime.now(UTC)
        day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(realized_pnl), 0.0)
              FROM trades
             WHERE status = ? AND closed_at >= ? AND closed_at < ?
            """,
            [STATUS_CLOSED, day_start, day_end],
        ).fetchone()
        return float(row[0]) if row else 0.0

    # -- tick history --------------------------------------------------------

    def record_tick_run(self, summary: dict[str, Any]) -> None:
        """Append the summary dict returned by ``run_tick`` to ``tick_runs``.

        Schema is permissive: missing keys default to None/0 so older callers
        can't break the write. Errors during recording are swallowed with a
        ``LedgerError`` since a failed audit write should never mask the tick
        result itself — the caller decides how loud to be.
        """
        signals = summary.get("signals") or {}
        errors = summary.get("errors") or []
        run_at_raw = summary.get("now_utc")
        if isinstance(run_at_raw, str):
            try:
                run_at = datetime.fromisoformat(run_at_raw)
            except ValueError:
                run_at = datetime.now(UTC)
        elif isinstance(run_at_raw, datetime):
            run_at = run_at_raw
        else:
            run_at = datetime.now(UTC)

        logger.debug(
            "ledger record_tick_run run_at=%s placed=%s skipped=%s closed=%s errors=%d",
            run_at, summary.get("orders_placed"), summary.get("orders_skipped"),
            summary.get("positions_closed"), len(errors),
        )
        try:
            self.conn.execute(
                """
                INSERT INTO tick_runs (
                    run_at, dry_run, universe_size, equity_usdt,
                    signals_buy, signals_sell, signals_hold,
                    orders_placed, orders_skipped, positions_closed,
                    reconciled, kill_switch, error_count, errors_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    _to_naive_utc(run_at),
                    bool(summary.get("dry_run", False)),
                    summary.get("universe_size"),
                    summary.get("equity_usdt"),
                    int(signals.get("BUY", 0) or 0),
                    int(signals.get("SELL", 0) or 0),
                    int(signals.get("HOLD", 0) or 0),
                    int(summary.get("orders_placed", 0) or 0),
                    int(summary.get("orders_skipped", 0) or 0),
                    int(summary.get("positions_closed", 0) or 0),
                    int(summary.get("reconciled", 0) or 0),
                    bool(summary.get("kill_switch", False)),
                    len(errors),
                    json.dumps(errors) if errors else None,
                ],
            )
        except Exception as e:
            raise LedgerError(f"record_tick_run failed: {e}",
                              operation="record_tick_run") from e

    # -- dashboard reads -----------------------------------------------------

    def list_closed_trades(self, limit: int = 50) -> list[ClosedTradeRow]:
        """Recent trade rows ordered by most-recently-touched first.

        Includes all statuses (intent/placed/filled/closed/canceled/failed) so
        the dashboard's "recent orders" view covers the full lifecycle.
        """
        rows = self.conn.execute(
            """
            SELECT client_order_id, symbol, side, status, strategy, entry_tag,
                   intended_qty, filled_qty, entry_price, exit_price,
                   realized_pnl, opened_at, filled_at, closed_at, notes
              FROM trades
             ORDER BY COALESCE(closed_at, filled_at, opened_at) DESC NULLS LAST
             LIMIT ?
            """,
            [int(limit)],
        ).fetchall()
        return [
            ClosedTradeRow(
                client_order_id=r[0],
                symbol=r[1],
                side=r[2],
                status=r[3],
                strategy=r[4],
                entry_tag=r[5],
                intended_qty=float(r[6]) if r[6] is not None else None,
                filled_qty=float(r[7]) if r[7] is not None else None,
                entry_price=float(r[8]) if r[8] is not None else None,
                exit_price=float(r[9]) if r[9] is not None else None,
                realized_pnl=float(r[10]) if r[10] is not None else None,
                opened_at=r[11],
                filled_at=r[12],
                closed_at=r[13],
                notes=r[14],
            )
            for r in rows
        ]

    def realized_pnl_by_day(self, days: int = 30) -> list[tuple[date, float]]:
        """Daily realized P&L for the last ``days`` days, oldest first.

        Only closed trades contribute. Days with no closed trades are omitted
        — the caller is responsible for filling gaps if it wants a continuous
        axis. Day keys are UTC ``date`` objects.
        """
        cutoff = datetime.now(UTC) - timedelta(days=int(days))
        rows = self.conn.execute(
            """
            SELECT CAST(date_trunc('day', closed_at) AS DATE) AS day,
                   SUM(realized_pnl)                          AS pnl
              FROM trades
             WHERE status = ? AND closed_at >= ?
             GROUP BY day
             ORDER BY day ASC
            """,
            [STATUS_CLOSED, _to_naive_utc(cutoff)],
        ).fetchall()
        return [(r[0], float(r[1] or 0.0)) for r in rows]

    def list_active_locks(self, now_utc: datetime | None = None) -> list[ActiveLock]:
        """Per-symbol cooldowns that have not yet expired."""
        now = now_utc or datetime.now(UTC)
        # Read-only connections can't DELETE, so we filter in SQL instead of
        # relying on ``is_pair_locked``'s lazy GC.
        rows = self.conn.execute(
            """
            SELECT symbol, locked_until, reason
              FROM symbol_locks
             WHERE locked_until > ?
             ORDER BY locked_until ASC
            """,
            [_to_naive_utc(now)],
        ).fetchall()
        out: list[ActiveLock] = []
        for sym, locked_until, reason in rows:
            if locked_until is not None and locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=UTC)
            out.append(ActiveLock(symbol=sym, locked_until=locked_until, reason=reason))
        return out

    def list_recent_ticks(self, limit: int = 50) -> list[TickRun]:
        """Most recent tick summaries, newest first."""
        rows = self.conn.execute(
            """
            SELECT run_at, dry_run, universe_size, equity_usdt,
                   signals_buy, signals_sell, signals_hold,
                   orders_placed, orders_skipped, positions_closed,
                   reconciled, kill_switch, error_count, errors_json
              FROM tick_runs
             ORDER BY run_at DESC
             LIMIT ?
            """,
            [int(limit)],
        ).fetchall()
        out: list[TickRun] = []
        for r in rows:
            run_at = r[0]
            if run_at is not None and run_at.tzinfo is None:
                run_at = run_at.replace(tzinfo=UTC)
            out.append(
                TickRun(
                    run_at=run_at,
                    dry_run=bool(r[1]) if r[1] is not None else False,
                    universe_size=int(r[2]) if r[2] is not None else None,
                    equity_usdt=float(r[3]) if r[3] is not None else None,
                    signals_buy=int(r[4] or 0),
                    signals_sell=int(r[5] or 0),
                    signals_hold=int(r[6] or 0),
                    orders_placed=int(r[7] or 0),
                    orders_skipped=int(r[8] or 0),
                    positions_closed=int(r[9] or 0),
                    reconciled=int(r[10] or 0),
                    kill_switch=bool(r[11]) if r[11] is not None else False,
                    error_count=int(r[12] or 0),
                    errors_json=r[13],
                )
            )
        return out
