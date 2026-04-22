"""Tests for src/trading/tick.py — integration with fake client/ledger/storage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.trading.config import TradingConfig
from src.trading.ledger import TradeLedger
from src.trading.strategy import SmaCrossoverStrategy
from src.trading.tick import run_tick


# --- fakes ------------------------------------------------------------------


class FakeStorage:
    def __init__(self, universe: list[str]) -> None:
        self.universe = universe

    def load_output(self, name: str) -> dict[str, Any]:
        return {"symbols": self.universe, "universe_size": len(self.universe)}


class FakeClient:
    """In-memory stand-in for BinanceClient. Records every write call."""

    def __init__(self, equity: float = 10_000.0, last_price: float = 100.0) -> None:
        self.equity = equity
        self.last_price = last_price
        self.market_orders: list[dict[str, Any]] = []
        self.stop_orders: list[dict[str, Any]] = []
        self.canceled: list[dict[str, Any]] = []

    def get_account(self) -> dict[str, Any]:
        return {"balances": [{"asset": "USDT", "free": str(self.equity), "locked": "0"}]}

    def get_exchange_info(self, symbols: list[str] | None = None) -> dict[str, Any]:
        # The real client is now called without symbols so the tick can drop
        # universe entries testnet doesn't list; return filters for whatever
        # the current test set uses (BTCUSDT/ETHUSDT cover every existing test).
        supported = symbols if symbols is not None else ["BTCUSDT", "ETHUSDT"]
        return {
            "symbols": [
                {
                    "symbol": s,
                    "filters": [
                        {"filterType": "LOT_SIZE", "stepSize": "0.0001",
                         "minQty": "0.0001", "maxQty": "1000"},
                        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                        {"filterType": "MIN_NOTIONAL", "minNotional": "1"},
                    ],
                }
                for s in supported
            ],
        }

    def place_market_order(self, symbol: str, side: str, qty: float,
                           client_order_id: str) -> dict[str, Any]:
        self.market_orders.append(
            {"symbol": symbol, "side": side, "qty": qty, "coid": client_order_id}
        )
        return {
            "symbol": symbol, "orderId": f"exch-{len(self.market_orders)}",
            "clientOrderId": client_order_id, "status": "FILLED",
            "executedQty": str(qty),
            "cummulativeQuoteQty": str(qty * self.last_price),
        }

    def place_stop_loss_limit(self, symbol: str, side: str, qty: float,
                              stop_price: float, limit_price: float,
                              client_order_id: str) -> dict[str, Any]:
        self.stop_orders.append({"symbol": symbol, "coid": client_order_id,
                                 "stop": stop_price})
        return {"symbol": symbol, "status": "NEW", "clientOrderId": client_order_id}

    def cancel_order(self, symbol: str, order_id: str | None = None,
                     orig_client_order_id: str | None = None) -> dict[str, Any]:
        self.canceled.append({"symbol": symbol, "coid": orig_client_order_id})
        return {"status": "CANCELED"}

    def get_order(self, symbol: str, order_id: str | None = None,
                  orig_client_order_id: str | None = None) -> dict[str, Any]:
        return {"status": "NEW", "executedQty": "0"}


# --- helpers ----------------------------------------------------------------


def _cfg(tmp_path: Path, **overrides: Any) -> TradingConfig:
    base: dict[str, Any] = dict(
        api_key="k", api_secret="s",
        dry_run=True, testnet_base_url="https://testnet.binance.vision",
        candle_interval="5m", candle_lookback=60,
        sma_short=3, sma_long=5,
        risk_per_trade=0.01, stop_loss_pct=0.03,
        max_open_positions=5, max_daily_loss_pct=0.05,
        min_equity_floor_usdt=100.0, max_cost_fraction_of_risk=0.5,
        post_stop_cooldown_minutes=60,
        ledger_path=tmp_path / "ledger.duckdb",
    )
    base.update(overrides)
    return TradingConfig(**base)


def _ramp_up_closes(last: float = 100.0) -> list[dict[str, Any]]:
    # Long flat + rising ramp at the end → BUY signal on short=3/long=5
    closes = [10.0] * 10 + [20.0, 22.0, 24.0, 26.0, 28.0, last]
    return [{"close": c, "timestamp": "t"} for c in closes]


def _flat_closes() -> list[dict[str, Any]]:
    return [{"close": 10.0, "timestamp": "t"} for _ in range(20)]


# --- tests ------------------------------------------------------------------


def test_tick_returns_summary_shape(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    client = FakeClient()
    storage = FakeStorage(["BTCUSDT"])
    with TradeLedger(cfg.ledger_path) as ledger, \
         patch("src.trading.tick.fetch_klines", return_value=_flat_closes()):
        summary = run_tick(cfg=cfg, storage=storage, client=client, ledger=ledger,
                           strategy=SmaCrossoverStrategy(3, 5))
    assert summary["dry_run"] is True
    assert summary["orders_placed"] == 0
    assert "BUY" in summary["signals"]


def test_tick_places_order_on_buy_signal(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    client = FakeClient(last_price=100.0)
    storage = FakeStorage(["BTCUSDT"])
    with TradeLedger(cfg.ledger_path) as ledger, \
         patch("src.trading.tick.fetch_klines", return_value=_ramp_up_closes(last=100.0)):
        summary = run_tick(cfg=cfg, storage=storage, client=client, ledger=ledger,
                           strategy=SmaCrossoverStrategy(3, 5))

    assert summary["orders_placed"] == 1
    assert len(client.market_orders) == 1
    assert client.market_orders[0]["side"] == "BUY"
    # A protective stop should have followed the fill.
    assert len(client.stop_orders) == 1
    assert client.stop_orders[0]["stop"] < client.market_orders[0]["qty"] * 100.0


def test_tick_skips_symbols_with_existing_position(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    client = FakeClient()
    storage = FakeStorage(["BTCUSDT"])
    with TradeLedger(cfg.ledger_path) as ledger:
        ledger.record_intent("c-existing", "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma")
        ledger.mark_placed("c-existing", "exch-pre")
        ledger.mark_filled("c-existing", 1.0, 100.0)

        with patch("src.trading.tick.fetch_klines", return_value=_ramp_up_closes()):
            summary = run_tick(cfg=cfg, storage=storage, client=client, ledger=ledger,
                               strategy=SmaCrossoverStrategy(3, 5))

    # No new market orders — held position blocks re-entry.
    assert not any(o["coid"] != "c-existing" for o in client.market_orders)
    assert summary["orders_placed"] == 0


def test_tick_aborts_on_equity_floor(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, min_equity_floor_usdt=1_000_000.0)
    client = FakeClient(equity=100.0)
    storage = FakeStorage(["BTCUSDT"])
    with TradeLedger(cfg.ledger_path) as ledger:
        summary = run_tick(cfg=cfg, storage=storage, client=client, ledger=ledger,
                           strategy=SmaCrossoverStrategy(3, 5))
    assert summary["kill_switch"] is True
    assert summary["orders_placed"] == 0


def test_tick_aborts_on_daily_loss_kill_switch(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, max_daily_loss_pct=0.01)  # $100 loss on $10k
    client = FakeClient(equity=10_000.0)
    storage = FakeStorage(["BTCUSDT"])
    now = datetime.now(UTC)
    with TradeLedger(cfg.ledger_path) as ledger:
        ledger.record_intent("loss-c1", "BTCUSDT", "BUY", 1.0, 100.0, 97.0, "sma")
        ledger.mark_filled("loss-c1", 1.0, 100.0)
        ledger.mark_closed("loss-c1", exit_price=50.0, exit_client_order_id="x",
                           realized_pnl=-200.0, closed_at=now)
        summary = run_tick(cfg=cfg, storage=storage, client=client, ledger=ledger,
                           now_utc=now, strategy=SmaCrossoverStrategy(3, 5))
    assert summary["kill_switch"] is True
    assert summary["orders_placed"] == 0


def test_tick_reconciles_filled_stop(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    client = FakeClient()
    storage = FakeStorage(["BTCUSDT"])
    # Return a FILLED stop when reconcile queries it.
    def fake_get_order(**kwargs: Any) -> dict[str, Any]:
        return {
            "status": "FILLED",
            "executedQty": "1.0",
            "cummulativeQuoteQty": "95.0",
        }
    client.get_order = fake_get_order  # type: ignore[assignment]

    with TradeLedger(cfg.ledger_path) as ledger:
        ledger.record_intent("c1", "BTCUSDT", "BUY", 1.0, 100.0, 95.0, "sma")
        ledger.mark_filled("c1", 1.0, 100.0)
        ledger.attach_stop("c1", stop_order_id="stop-1", stop_price=95.0)

        with patch("src.trading.tick.fetch_klines", return_value=_flat_closes()):
            summary = run_tick(cfg=cfg, storage=storage, client=client, ledger=ledger,
                               strategy=SmaCrossoverStrategy(3, 5))
        assert summary["reconciled"] == 1
        # After reconciliation the position is closed → no open positions.
        assert ledger.get_open_position_count() == 0


def test_tick_tags_entry_with_signal_reason(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    client = FakeClient(last_price=100.0)
    storage = FakeStorage(["BTCUSDT"])
    with TradeLedger(cfg.ledger_path) as ledger, \
         patch("src.trading.tick.fetch_klines", return_value=_ramp_up_closes(last=100.0)):
        run_tick(cfg=cfg, storage=storage, client=client, ledger=ledger,
                 strategy=SmaCrossoverStrategy(3, 5))
        opens = ledger.get_open_positions()
    assert len(opens) == 1
    assert opens[0].entry_tag == "sma_cross_up"


def test_tick_skips_locked_pair(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    client = FakeClient(last_price=100.0)
    storage = FakeStorage(["BTCUSDT"])
    now = datetime.now(UTC)
    with TradeLedger(cfg.ledger_path) as ledger:
        ledger.lock_pair("BTCUSDT", now + timedelta(minutes=30), reason="cooldown")
        with patch("src.trading.tick.fetch_klines", return_value=_ramp_up_closes(last=100.0)):
            summary = run_tick(cfg=cfg, storage=storage, client=client, ledger=ledger,
                               now_utc=now, strategy=SmaCrossoverStrategy(3, 5))
    assert summary["orders_placed"] == 0
    assert len(client.market_orders) == 0


def test_tick_locks_pair_after_stop_fill_reconcile(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, post_stop_cooldown_minutes=90)
    client = FakeClient()
    storage = FakeStorage(["BTCUSDT"])

    def fake_get_order(**kwargs: Any) -> dict[str, Any]:
        return {"status": "FILLED", "executedQty": "1.0", "cummulativeQuoteQty": "95.0"}
    client.get_order = fake_get_order  # type: ignore[assignment]

    now = datetime.now(UTC)
    with TradeLedger(cfg.ledger_path) as ledger:
        ledger.record_intent("c1", "BTCUSDT", "BUY", 1.0, 100.0, 95.0, "sma")
        ledger.mark_filled("c1", 1.0, 100.0)
        ledger.attach_stop("c1", stop_order_id="stop-1", stop_price=95.0)

        with patch("src.trading.tick.fetch_klines", return_value=_flat_closes()):
            run_tick(cfg=cfg, storage=storage, client=client, ledger=ledger,
                     now_utc=now, strategy=SmaCrossoverStrategy(3, 5))

        # The reconcile path set a cooldown that still applies moments later.
        assert ledger.is_pair_locked("BTCUSDT", now + timedelta(minutes=10)) is True
        # And it expires after the cooldown window.
        assert ledger.is_pair_locked("BTCUSDT", now + timedelta(minutes=120)) is False


def test_tick_errors_when_universe_missing(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)

    class MissingStorage:
        def load_output(self, name: str) -> dict[str, Any]:
            from src.storage.base import StorageError
            raise StorageError("not found", operation="load_output")

    client = FakeClient()
    with TradeLedger(cfg.ledger_path) as ledger:
        summary = run_tick(cfg=cfg, storage=MissingStorage(), client=client, ledger=ledger,
                           strategy=SmaCrossoverStrategy(3, 5))
    assert summary["orders_placed"] == 0
    assert any("universe_missing" in e for e in summary["errors"])
