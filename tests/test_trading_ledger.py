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
