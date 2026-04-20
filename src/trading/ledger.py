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

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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


class TradeLedger:
    """Thin DuckDB wrapper around the ``trades`` table."""

    def __init__(self, db_path: str | Path):
        if not DUCKDB_AVAILABLE:
            raise LedgerError("DuckDB not installed. Run: uv add duckdb", operation="ledger_init")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.conn = duckdb.connect(str(self.db_path))
        except Exception as e:  # pragma: no cover - defensive
            raise LedgerError(f"Failed to open ledger at {self.db_path}: {e}",
                              operation="ledger_init") from e
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
        now_utc: datetime | None = None,
    ) -> None:
        """Insert a new entry trade in the ``intent`` state."""
        now = now_utc or datetime.now(UTC)
        try:
            self.conn.execute(
                """
                INSERT INTO trades (
                    client_order_id, symbol, side, strategy, status,
                    intended_qty, entry_price, stop_price, opened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [client_order_id, symbol, side, strategy, STATUS_INTENT,
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
                   filled_qty, entry_price, stop_price, stop_order_id, filled_at
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
            )
            for r in rows
        ]

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
