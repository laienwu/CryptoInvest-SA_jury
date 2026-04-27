"""Tests for src/trading/ledger.py — DuckDB trade lifecycle + reads."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.trading.ledger import TradeLedger


@pytest.fixture
def ledger(tmp_path: Path) -> Iterator[TradeLedger]:
    led = TradeLedger(tmp_path / "ledger.duckdb")
    yield led
    led.close()


def test_record_intent_inserts_row(ledger: TradeLedger) -> None:
    ledger.record_intent(
        client_order_id="c1", symbol="BTCUSDT", side="BUY",
        intended_qty=1.0, entry_price=100.0, stop_price=97.0,
        strategy="sma",
    )
    assert ledger.has_client_order_id("c1")
    assert ledger.has_client_order_id("c-missing") is False


def test_lifecycle_placed_filled_closed(ledger: TradeLedger) -> None:
    ledger.record_intent(
        client_order_id="c1", symbol="BTCUSDT", side="BUY",
        intended_qty=1.0, entry_price=100.0, stop_price=97.0, strategy="sma",
    )
    ledger.mark_placed("c1", exchange_order_id="exch-1")
    ledger.mark_filled("c1", filled_qty=1.0, avg_fill_price=100.5)

    opens = ledger.get_open_positions()
    assert len(opens) == 1
    assert opens[0].symbol == "BTCUSDT"
    assert opens[0].filled_qty == 1.0
    assert opens[0].entry_price == 100.5

    now = datetime.now(UTC)
    ledger.mark_closed("c1", exit_price=105.0, exit_client_order_id="x1",
                       realized_pnl=4.5, closed_at=now)
    assert ledger.get_open_position_count() == 0
    assert ledger.get_realized_pnl_today(now) == pytest.approx(4.5)


def test_realized_pnl_today_excludes_yesterday(ledger: TradeLedger) -> None:
    yesterday = datetime.now(UTC) - timedelta(days=1)
    today = datetime.now(UTC)

    ledger.record_intent("c1", "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma")
    ledger.mark_filled("c1", 1.0, 100.0)
    ledger.mark_closed("c1", exit_price=90.0, exit_client_order_id="x1",
                       realized_pnl=-10.0, closed_at=yesterday)

    ledger.record_intent("c2", "ETHUSDT", "BUY", 1.0, 50.0, 48.0, "sma")
    ledger.mark_filled("c2", 1.0, 50.0)
    ledger.mark_closed("c2", exit_price=55.0, exit_client_order_id="x2",
                       realized_pnl=5.0, closed_at=today)

    assert ledger.get_realized_pnl_today(today) == pytest.approx(5.0)


def test_get_open_symbols_and_count(ledger: TradeLedger) -> None:
    ledger.record_intent("c1", "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma")
    ledger.mark_placed("c1", "exch-1")
    ledger.record_intent("c2", "ETHUSDT", "BUY", 1.0, 50.0, 48.0, "sma")
    ledger.mark_placed("c2", "exch-2")
    ledger.mark_filled("c2", 1.0, 50.0)

    assert ledger.get_open_position_count() == 2
    assert ledger.get_open_symbols() == {"BTCUSDT", "ETHUSDT"}


def test_mark_failed_and_canceled_remove_from_open(ledger: TradeLedger) -> None:
    ledger.record_intent("c1", "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma")
    ledger.mark_placed("c1", "exch-1")
    ledger.mark_canceled("c1", note="strategy flip")
    assert ledger.get_open_position_count() == 0

    ledger.record_intent("c2", "ETHUSDT", "BUY", 1.0, 50.0, 48.0, "sma")
    ledger.mark_failed("c2", note="filter violation")
    assert ledger.get_open_position_count() == 0


def test_attach_stop_records_stop_metadata(ledger: TradeLedger) -> None:
    ledger.record_intent("c1", "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma")
    ledger.mark_placed("c1", "exch-1")
    ledger.mark_filled("c1", 1.0, 100.0)
    ledger.attach_stop("c1", stop_order_id="stop-coid-1", stop_price=97.0)
    open_pos = ledger.get_open_positions()[0]
    assert open_pos.stop_order_id == "stop-coid-1"
    assert open_pos.stop_price == 97.0


def test_entry_tag_round_trips_through_open_positions(ledger: TradeLedger) -> None:
    ledger.record_intent(
        "c1", "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma",
        entry_tag="sma_cross_up",
    )
    ledger.mark_placed("c1", "exch-1")
    ledger.mark_filled("c1", 1.0, 100.0)
    pos = ledger.get_open_positions()[0]
    assert pos.entry_tag == "sma_cross_up"


def test_lock_pair_blocks_is_pair_locked(ledger: TradeLedger) -> None:
    now = datetime.now(UTC)
    ledger.lock_pair("BTCUSDT", locked_until=now + timedelta(minutes=30),
                     reason="stop_fill_cooldown")
    assert ledger.is_pair_locked("BTCUSDT", now) is True
    assert ledger.is_pair_locked("ETHUSDT", now) is False


def test_is_pair_locked_auto_clears_expired_lock(ledger: TradeLedger) -> None:
    past = datetime.now(UTC) - timedelta(minutes=1)
    ledger.lock_pair("BTCUSDT", locked_until=past, reason="stale")
    # First read auto-GCs the expired lock.
    assert ledger.is_pair_locked("BTCUSDT") is False
    # And a fresh lock takes effect.
    future = datetime.now(UTC) + timedelta(hours=1)
    ledger.lock_pair("BTCUSDT", locked_until=future, reason="fresh")
    assert ledger.is_pair_locked("BTCUSDT") is True


def test_unlock_pair_removes_lock(ledger: TradeLedger) -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    ledger.lock_pair("BTCUSDT", future, "x")
    ledger.unlock_pair("BTCUSDT")
    assert ledger.is_pair_locked("BTCUSDT") is False


def test_lock_pair_upserts_on_conflict(ledger: TradeLedger) -> None:
    t1 = datetime.now(UTC) + timedelta(minutes=10)
    t2 = datetime.now(UTC) + timedelta(hours=2)
    ledger.lock_pair("BTCUSDT", t1, "first")
    ledger.lock_pair("BTCUSDT", t2, "second")  # upsert — no IntegrityError
    assert ledger.is_pair_locked("BTCUSDT") is True


# -- dashboard reads ---------------------------------------------------------


def test_record_tick_run_and_list_recent_ticks(ledger: TradeLedger) -> None:
    summary = {
        "now_utc": datetime(2026, 4, 23, 12, 0, tzinfo=UTC).isoformat(),
        "dry_run": True,
        "universe_size": 12,
        "equity_usdt": 1000.0,
        "signals": {"BUY": 2, "SELL": 1, "HOLD": 9},
        "orders_placed": 2,
        "orders_skipped": 1,
        "positions_closed": 1,
        "reconciled": 0,
        "kill_switch": False,
        "errors": ["klines(BTCUSDT): timeout"],
    }
    ledger.record_tick_run(summary)

    ticks = ledger.list_recent_ticks(10)
    assert len(ticks) == 1
    t = ticks[0]
    assert t.dry_run is True
    assert t.universe_size == 12
    assert t.equity_usdt == 1000.0
    assert t.signals_buy == 2 and t.signals_sell == 1 and t.signals_hold == 9
    assert t.orders_placed == 2 and t.orders_skipped == 1
    assert t.error_count == 1
    assert t.errors_json and "timeout" in t.errors_json


def test_list_recent_ticks_newest_first(ledger: TradeLedger) -> None:
    for i, buy in enumerate([1, 2, 3]):
        ledger.record_tick_run({
            "now_utc": datetime(2026, 4, 23, 12, i, tzinfo=UTC).isoformat(),
            "dry_run": True,
            "signals": {"BUY": buy, "SELL": 0, "HOLD": 0},
            "errors": [],
        })
    ticks = ledger.list_recent_ticks(10)
    assert [t.signals_buy for t in ticks] == [3, 2, 1]


def test_realized_pnl_by_day_groups_and_filters(ledger: TradeLedger) -> None:
    today = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    old = today - timedelta(days=45)

    def _close(coid: str, pnl: float, when: datetime) -> None:
        ledger.record_intent(coid, "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma")
        ledger.mark_filled(coid, 1.0, 100.0)
        ledger.mark_closed(coid, exit_price=100.0 + pnl,
                           exit_client_order_id=f"x-{coid}",
                           realized_pnl=pnl, closed_at=when)

    _close("c1", 5.0, today)
    _close("c2", -2.0, today)
    _close("c3", 7.0, yesterday)
    _close("c4", 999.0, old)  # outside the 30d window

    series = ledger.realized_pnl_by_day(days=30)
    # Two days inside the window; old trade excluded.
    assert len(series) == 2
    days = {d: pnl for d, pnl in series}
    assert days[yesterday.date()] == pytest.approx(7.0)
    assert days[today.date()] == pytest.approx(3.0)


def test_list_closed_trades_orders_by_recent_activity(ledger: TradeLedger) -> None:
    # Three rows at different lifecycle stages.
    ledger.record_intent("c1", "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma")  # intent only
    ledger.record_intent("c2", "ETHUSDT", "BUY", 1.0, 50.0, 48.0, "sma")
    ledger.mark_filled("c2", 1.0, 50.0)
    ledger.record_intent("c3", "BNBUSDT", "BUY", 1.0, 20.0, 19.0, "sma")
    ledger.mark_filled("c3", 1.0, 20.0)
    ledger.mark_closed("c3", exit_price=22.0, exit_client_order_id="x3",
                       realized_pnl=2.0, closed_at=datetime.now(UTC))

    rows = ledger.list_closed_trades(limit=10)
    coids = [r.client_order_id for r in rows]
    # Closed most recent, then filled, then intent.
    assert coids == ["c3", "c2", "c1"]
    assert rows[0].status == "closed"
    assert rows[0].realized_pnl == pytest.approx(2.0)


def test_list_active_locks_excludes_expired(ledger: TradeLedger) -> None:
    now = datetime.now(UTC)
    ledger.lock_pair("BTCUSDT", now + timedelta(hours=1), "fresh")
    ledger.lock_pair("ETHUSDT", now - timedelta(minutes=1), "expired")

    locks = ledger.list_active_locks(now)
    assert [lk.symbol for lk in locks] == ["BTCUSDT"]
    assert locks[0].reason == "fresh"
    assert locks[0].locked_until.tzinfo is not None


def test_read_only_mode_rejects_writes(tmp_path: Path) -> None:
    # Seed the DB in write mode first so the file exists.
    db_path = tmp_path / "ledger.duckdb"
    with TradeLedger(db_path) as writer:
        writer.record_intent("c1", "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma")

    with TradeLedger(db_path, read_only=True) as reader:
        assert reader.has_client_order_id("c1") is True
        with pytest.raises(Exception):
            reader.record_intent("c2", "ETHUSDT", "BUY", 1.0, 50.0, 48.0, "sma")
