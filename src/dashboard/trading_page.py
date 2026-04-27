"""
Trading Activity page — surfaces the state of the automated trading bot.

Reads ``data/trading/ledger.duckdb`` directly in **read-only** mode. The
Airflow worker is the sole writer; the dashboard takes a short-lived
connection per render so a tick that runs mid-refresh can't deadlock us.

Widgets:
- Header KPIs (last tick, dry-run flag, kill-switch, open positions, realized
  PnL today, equity snapshot).
- Open positions table.
- Realized PnL per day (last 30 days).
- Recent orders / trade rows (last 50, all lifecycle stages).
- Per-symbol cooldowns.
- Tick history (last 50).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.trading.config import load_trading_config
from src.trading.ledger import ActiveLock, ClosedTradeRow, TickRun, TradeLedger


# --- ledger access ----------------------------------------------------------


def _ledger_path() -> Path:
    """Resolve the ledger path from TradingConfig.

    We re-resolve per render rather than caching because config is cheap and
    the path could change across container restarts.
    """
    return Path(load_trading_config().ledger_path)


@st.cache_data(ttl=10, show_spinner=False)  # type: ignore[misc]
def _load_snapshot(db_path_str: str) -> dict[str, object]:
    """Open the ledger read-only, pull everything the page needs, close.

    Cached for 10s so scrolling the page doesn't hammer DuckDB, but short
    enough that the view feels live when a tick completes.
    """
    db_path = Path(db_path_str)
    if not db_path.exists():
        return {"available": False}

    with TradeLedger(db_path, read_only=True) as led:
        now = datetime.now(UTC)
        open_positions = [asdict(p) for p in led.get_open_positions()]
        closed_trades = [asdict(r) for r in led.list_closed_trades(limit=50)]
        pnl_by_day = [(d.isoformat(), v) for d, v in led.realized_pnl_by_day(days=30)]
        active_locks = [asdict(lk) for lk in led.list_active_locks(now)]
        recent_ticks = [asdict(t) for t in led.list_recent_ticks(limit=50)]
        realized_today = led.get_realized_pnl_today(now)
        open_count = led.get_open_position_count()

    return {
        "available": True,
        "now": now.isoformat(),
        "open_positions": open_positions,
        "closed_trades": closed_trades,
        "pnl_by_day": pnl_by_day,
        "active_locks": active_locks,
        "recent_ticks": recent_ticks,
        "realized_today": realized_today,
        "open_count": open_count,
    }


# --- formatting helpers -----------------------------------------------------


def _fmt_ts(ts: datetime | str | None) -> str:
    if ts is None:
        return "—"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            return ts
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_usdt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+,.2f} USDT"


def _fmt_price(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.6g}"


# --- widgets ----------------------------------------------------------------


def _render_kpis(snap: dict[str, object]) -> None:
    ticks: list[dict[str, object]] = snap.get("recent_ticks") or []  # type: ignore[assignment]
    latest = ticks[0] if ticks else None

    cols = st.columns(5)

    last_run = _fmt_ts(latest["run_at"]) if latest else "No ticks recorded"
    mode = "DRY-RUN" if (latest and latest.get("dry_run")) else "LIVE" if latest else "—"
    cols[0].metric("Last tick", last_run, delta=mode, delta_color="off")

    kill = bool(latest.get("kill_switch")) if latest else False
    cols[1].metric(
        "Kill switch",
        "TRIPPED" if kill else "Clear",
        delta=None,
        delta_color="inverse" if kill else "off",
    )

    cols[2].metric("Open positions", snap.get("open_count", 0))

    realized_today = float(snap.get("realized_today") or 0.0)
    cols[3].metric(
        "Realized PnL today",
        _fmt_usdt(realized_today),
        delta=f"{realized_today:+.2f}",
        delta_color="normal" if realized_today >= 0 else "inverse",
    )

    equity = latest.get("equity_usdt") if latest else None
    cols[4].metric(
        "Equity (last tick)",
        f"{float(equity):,.2f} USDT" if equity is not None else "—",
    )


def _render_open_positions(positions: list[dict[str, object]]) -> None:
    st.subheader("Open positions")
    if not positions:
        st.info("No open positions.")
        return
    df = pd.DataFrame([
        {
            "Symbol": p["symbol"],
            "Side": p["side"],
            "Qty": p["filled_qty"],
            "Entry": _fmt_price(p["entry_price"]),  # type: ignore[arg-type]
            "Stop": _fmt_price(p["stop_price"]),  # type: ignore[arg-type]
            "Filled at": _fmt_ts(p["filled_at"]),  # type: ignore[arg-type]
            "Entry tag": p.get("entry_tag") or "—",
            "client_order_id": p["client_order_id"],
        }
        for p in positions
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_pnl_by_day(series: list[tuple[str, float]]) -> None:
    st.subheader("Realized PnL per day (last 30d)")
    if not series:
        st.info("No closed trades in the last 30 days.")
        return
    days = [d for d, _ in series]
    values = [v for _, v in series]
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in values]
    fig = go.Figure(go.Bar(x=days, y=values, marker_color=colors))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 40, "r": 20, "t": 10, "b": 40},
        xaxis={"title": "Day (UTC)", "gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"title": "Realized PnL (USDT)", "gridcolor": "rgba(128,128,128,0.15)"},
        height=280,
    )
    st.plotly_chart(fig, use_container_width=True)
    total = sum(values)
    st.caption(f"30-day total: {_fmt_usdt(total)} across {len(series)} trading day(s).")


def _render_recent_orders(rows: list[dict[str, object]]) -> None:
    st.subheader("Recent orders (last 50)")
    if not rows:
        st.info("No orders recorded yet.")
        return
    df = pd.DataFrame([
        {
            "Last update": _fmt_ts(
                r["closed_at"] or r["filled_at"] or r["opened_at"]  # type: ignore[operator]
            ),
            "Symbol": r["symbol"],
            "Side": r["side"],
            "Status": r["status"],
            "Qty": r["filled_qty"] if r["filled_qty"] is not None else r["intended_qty"],
            "Entry": _fmt_price(r["entry_price"]),  # type: ignore[arg-type]
            "Exit": _fmt_price(r["exit_price"]),  # type: ignore[arg-type]
            "Realized PnL": _fmt_usdt(r["realized_pnl"]),  # type: ignore[arg-type]
            "Tag": r.get("entry_tag") or "—",
            "Notes": r.get("notes") or "",
        }
        for r in rows
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_cooldowns(locks: list[dict[str, object]]) -> None:
    st.subheader("Active per-symbol cooldowns")
    if not locks:
        st.info("No active cooldowns.")
        return
    now = datetime.now(UTC)
    df = pd.DataFrame([
        {
            "Symbol": lk["symbol"],
            "Locked until": _fmt_ts(lk["locked_until"]),  # type: ignore[arg-type]
            "Minutes remaining": _minutes_until(lk["locked_until"], now),  # type: ignore[arg-type]
            "Reason": lk.get("reason") or "—",
        }
        for lk in locks
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _minutes_until(ts: datetime | str, now: datetime) -> int:
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            return 0
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    delta = (ts - now).total_seconds() / 60.0
    return max(0, int(delta))


def _render_ticks(ticks: list[dict[str, object]]) -> None:
    st.subheader("Tick history (last 50)")
    if not ticks:
        st.info("No ticks recorded yet. The Trading DAG writes here each run.")
        return
    df = pd.DataFrame([
        {
            "Run at": _fmt_ts(t["run_at"]),  # type: ignore[arg-type]
            "Dry-run": "✓" if t.get("dry_run") else "",
            "Universe": t.get("universe_size") or 0,
            "BUY": t["signals_buy"],
            "SELL": t["signals_sell"],
            "HOLD": t["signals_hold"],
            "Placed": t["orders_placed"],
            "Skipped": t["orders_skipped"],
            "Closed": t["positions_closed"],
            "Reconciled": t["reconciled"],
            "Kill": "!" if t.get("kill_switch") else "",
            "Errors": t["error_count"],
        }
        for t in ticks
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    err_ticks = [t for t in ticks if t.get("errors_json")]
    if err_ticks:
        with st.expander(f"Error details ({len(err_ticks)} tick(s))"):
            for t in err_ticks:
                st.markdown(f"**{_fmt_ts(t['run_at'])}**")  # type: ignore[arg-type]
                try:
                    errs = json.loads(t["errors_json"])  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    errs = [str(t["errors_json"])]
                for e in errs:
                    st.code(str(e), language="text")


# --- entry point ------------------------------------------------------------


def page_trading_activity() -> None:
    """Automated-trading dashboard — reads the live ledger directly."""
    st.header("Automated Trading Activity")

    db_path = _ledger_path()
    st.caption(f"Ledger: `{db_path}` (read-only)")

    snap = _load_snapshot(str(db_path))

    if not snap.get("available"):
        st.warning(
            f"Ledger file not found at `{db_path}`. The trading DAG has not "
            "run yet, or the Streamlit container is missing the data volume "
            "mount (`./data:/app/data:ro` in docker-compose.yml).",
        )
        return

    if st.button("Refresh", help="Force-refresh snapshot"):
        _load_snapshot.clear()  # type: ignore[attr-defined]
        st.rerun()

    _render_kpis(snap)
    st.markdown("---")
    _render_open_positions(snap.get("open_positions") or [])  # type: ignore[arg-type]
    st.markdown("---")
    _render_pnl_by_day(snap.get("pnl_by_day") or [])  # type: ignore[arg-type]
    st.markdown("---")
    _render_recent_orders(snap.get("closed_trades") or [])  # type: ignore[arg-type]
    st.markdown("---")
    _render_cooldowns(snap.get("active_locks") or [])  # type: ignore[arg-type]
    st.markdown("---")
    _render_ticks(snap.get("recent_ticks") or [])  # type: ignore[arg-type]


# Suppress "unused import" for dataclass types used only as type hints in
# docstrings; they're part of the module's public contract.
_ = (ActiveLock, ClosedTradeRow, TickRun)
