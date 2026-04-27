"""
Theory vs Reality page — side-by-side of the Markowitz optimizer's target
allocation and what the automated bot is actually holding on testnet.

**This page is diagnostic only.** The bot does not consume the optimizer's
weights (see ``src/trading/tick.py``); any gap is expected, not a signal
to intervene. The banner at the top of the page restates this for anyone
opening the dashboard cold.

Data sources:
- FastAPI ``/portfolio/summary`` → optimizer weights + expected return /
  volatility / Sharpe.
- ``data/trading/ledger.duckdb`` (read-only, via ``TradeLedger``) → open
  positions + last tick's equity snapshot + 30d realized PnL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from src.trading.config import load_trading_config
from src.trading.ledger import OpenPosition, TradeLedger


_API_URL = os.getenv("API_URL", "http://localhost:8000")

# Below this magnitude a weight is treated as "zero" for alignment
# classification — avoids false "held-not-in-model" rows from float noise in
# the optimizer output.
_WEIGHT_EPSILON: float = 1e-4


# --- data access ------------------------------------------------------------


@st.cache_data(ttl=30, show_spinner=False)  # type: ignore[misc]
def _fetch_optimizer_summary() -> dict[str, Any] | None:
    """Call /portfolio/summary. Returns None on any failure — the page
    renders a clear 'optimizer output missing' state in that case."""
    try:
        resp = requests.get(f"{_API_URL}/portfolio/summary", timeout=10)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    except requests.RequestException:
        return None


@st.cache_data(ttl=10, show_spinner=False)  # type: ignore[misc]
def _load_ledger_snapshot(db_path_str: str) -> dict[str, Any]:
    db_path = Path(db_path_str)
    if not db_path.exists():
        return {"available": False}

    with TradeLedger(db_path, read_only=True) as led:
        open_positions = [
            {
                "symbol": p.symbol,
                "side": p.side,
                "filled_qty": p.filled_qty,
                "entry_price": p.entry_price,
            }
            for p in led.get_open_positions()
        ]
        recent_ticks = led.list_recent_ticks(limit=1)
        latest_tick = recent_ticks[0] if recent_ticks else None
        pnl_by_day = [(d.isoformat(), v) for d, v in led.realized_pnl_by_day(days=30)]

    return {
        "available": True,
        "open_positions": open_positions,
        "equity_usdt": latest_tick.equity_usdt if latest_tick else None,
        "last_tick_at": latest_tick.run_at.isoformat() if latest_tick and latest_tick.run_at else None,
        "pnl_by_day": pnl_by_day,
    }


# --- classification ---------------------------------------------------------


@dataclass(frozen=True)
class SymbolComparison:
    """One row of the theory-vs-reality table."""

    symbol: str
    optimizer_weight: float  # fraction of equity (signed)
    bot_weight: float        # fraction of equity (always >= 0 — spot long only)
    alignment: str           # human-readable category
    alignment_class: str     # one of: ok | underweight | extra | short_blocked | short_ignored


def _classify(opt_w: float, bot_w: float) -> tuple[str, str]:
    """Map (optimizer weight, bot weight) to a human label + color class."""
    opt_nonzero = abs(opt_w) > _WEIGHT_EPSILON
    bot_nonzero = bot_w > _WEIGHT_EPSILON

    if not opt_nonzero and not bot_nonzero:
        return ("", "ok")  # shouldn't be included in the table

    if opt_w > _WEIGHT_EPSILON and bot_nonzero:
        return ("✓ aligned (both long)", "ok")

    if opt_w > _WEIGHT_EPSILON and not bot_nonzero:
        return ("◦ model long, not held", "underweight")

    if opt_w < -_WEIGHT_EPSILON and bot_nonzero:
        return ("✗ model short but bot long", "short_blocked")

    if opt_w < -_WEIGHT_EPSILON and not bot_nonzero:
        return ("◦ model short, bot can't", "short_ignored")

    if not opt_nonzero and bot_nonzero:
        return ("◦ held, not in model", "extra")

    return ("", "ok")


_ALIGNMENT_COLORS: dict[str, str] = {
    "ok": "#2ca02c",            # green
    "underweight": "#ff7f0e",   # amber
    "extra": "#ff7f0e",         # amber
    "short_blocked": "#d62728", # red
    "short_ignored": "#7f7f7f", # grey
}


def _build_comparison_rows(
    optimizer_weights: dict[str, float],
    open_positions: list[dict[str, Any]],
    equity_usdt: float | None,
) -> list[SymbolComparison]:
    """Join optimizer weights with bot positions into one row per symbol."""
    # Aggregate bot exposure by symbol — there's normally one open position
    # per symbol, but the join is robust to duplicates.
    bot_notional: dict[str, float] = {}
    for p in open_positions:
        qty = float(p.get("filled_qty") or 0.0)
        price = float(p.get("entry_price") or 0.0)
        bot_notional[p["symbol"]] = bot_notional.get(p["symbol"], 0.0) + qty * price

    bot_weight: dict[str, float] = {}
    if equity_usdt and equity_usdt > 0:
        bot_weight = {s: n / equity_usdt for s, n in bot_notional.items()}

    all_symbols = set(optimizer_weights.keys()) | set(bot_weight.keys())
    rows: list[SymbolComparison] = []
    for sym in sorted(all_symbols):
        opt_w = float(optimizer_weights.get(sym, 0.0) or 0.0)
        bot_w = float(bot_weight.get(sym, 0.0))
        label, klass = _classify(opt_w, bot_w)
        if not label:
            continue
        rows.append(SymbolComparison(
            symbol=sym,
            optimizer_weight=opt_w,
            bot_weight=bot_w,
            alignment=label,
            alignment_class=klass,
        ))
    # Order: mismatches first (most interesting), then alignments,
    # within each group largest absolute optimizer weight first.
    priority = {
        "short_blocked": 0, "underweight": 1, "extra": 2,
        "short_ignored": 3, "ok": 4,
    }
    rows.sort(key=lambda r: (priority[r.alignment_class], -abs(r.optimizer_weight)))
    return rows


# --- widgets ----------------------------------------------------------------


def _render_banner() -> None:
    st.info(
        "**Diagnostic view only.** The automated bot does **not** consume the "
        "optimizer's weights — the two pipelines share only the daily "
        "universe. Gaps below are expected and not a signal to intervene."
    )


def _render_kpis(
    optimizer_weights: dict[str, float],
    rows: list[SymbolComparison],
    equity_usdt: float | None,
    open_positions: list[dict[str, Any]],
) -> None:
    opt_long = sum(1 for w in optimizer_weights.values() if w > _WEIGHT_EPSILON)
    opt_short = sum(1 for w in optimizer_weights.values() if w < -_WEIGHT_EPSILON)
    bot_held = len({p["symbol"] for p in open_positions})
    mismatches = sum(1 for r in rows if r.alignment_class == "short_blocked")

    # Gross exposure = sum(|w|). Optimizer: from weights directly. Bot: from
    # notional summed over open positions, divided by equity.
    opt_gross = sum(abs(w) for w in optimizer_weights.values())
    bot_notional_total = sum(
        float(p.get("filled_qty") or 0.0) * float(p.get("entry_price") or 0.0)
        for p in open_positions
    )
    bot_gross = (bot_notional_total / equity_usdt) if equity_usdt and equity_usdt > 0 else None

    cols = st.columns(4)
    cols[0].metric(
        "Model stance",
        f"{opt_long} long / {opt_short} short",
        help="Optimizer's position count. Shorts are unconstrained Markowitz artifacts.",
    )
    cols[1].metric(
        "Bot holdings",
        f"{bot_held} open",
        delta=f"{bot_held - opt_long:+d} vs model long" if opt_long else None,
        delta_color="off",
    )
    cols[2].metric(
        "Gross exposure",
        f"{bot_gross:.1%}" if bot_gross is not None else "—",
        delta=f"model {opt_gross:.1%}",
        delta_color="off",
        help="Bot's open notional as % of equity, vs optimizer's |weight| sum.",
    )
    cols[3].metric(
        "Direction mismatches",
        mismatches,
        delta="(model short but bot long)" if mismatches else "none",
        delta_color="inverse" if mismatches else "off",
    )


def _render_gap_table(rows: list[SymbolComparison]) -> None:
    st.subheader("Per-symbol allocation gap")
    if not rows:
        st.info("Optimizer has no non-zero weights and the bot holds nothing.")
        return
    df = pd.DataFrame([
        {
            "Symbol": r.symbol,
            "Optimizer": f"{r.optimizer_weight:+.2%}",
            "Bot (of equity)": f"{r.bot_weight:+.2%}" if r.bot_weight else "—",
            "Delta": f"{(r.bot_weight - r.optimizer_weight):+.2%}",
            "Alignment": r.alignment,
            "_class": r.alignment_class,
        }
        for r in rows
    ])

    def _style(row: pd.Series) -> list[str]:
        color = _ALIGNMENT_COLORS.get(str(row["_class"]), "#7f7f7f")
        # Only color the Alignment column — a whole-row tint would overwhelm
        # the neutral columns where the information is just numeric.
        return [
            f"color: {color}; font-weight: 600" if col == "Alignment" else ""
            for col in row.index
        ]

    styled = df.style.apply(_style, axis=1)  # type: ignore[arg-type]
    # Drop the _class helper column from display but keep it for styling.
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        column_order=["Symbol", "Optimizer", "Bot (of equity)", "Delta", "Alignment"],
    )
    st.caption(
        "Bot weight uses entry notional (`filled_qty × entry_price`), not live "
        "mark price, so it reflects capital *committed*, not current mark-to-market."
    )


def _render_pnl_overlay(
    pnl_by_day: list[tuple[str, float]],
    expected_annual_return: float | None,
    equity_usdt: float | None,
) -> None:
    st.subheader("30-day realized vs expected PnL")
    if not pnl_by_day:
        st.info(
            "No closed trades in the last 30 days — realized PnL series is "
            "empty. Optimizer's expected return line is shown as a dashed reference."
        )

    # Build a dense 30d calendar so the expected line has a continuous domain
    # even when the bot has sparse closed trades.
    today = datetime.now(UTC).date()
    window = [today - timedelta(days=i) for i in range(29, -1, -1)]
    realized_map = {d: v for d, v in pnl_by_day}
    # Guard — in case the ISO dates don't match the `date` keys.
    realized_map_date: dict[date, float] = {}
    for d_str, v in pnl_by_day:
        try:
            realized_map_date[date.fromisoformat(d_str)] = v
        except ValueError:
            continue

    realized_cum: list[float] = []
    running = 0.0
    for d in window:
        running += realized_map_date.get(d, 0.0)
        realized_cum.append(running)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=window, y=realized_cum,
        mode="lines+markers", name="Realized (bot)",
        line={"color": "#2ca02c", "width": 2},
    ))

    if (
        expected_annual_return is not None
        and equity_usdt is not None and equity_usdt > 0
    ):
        # Daily USDT drift implied by the optimizer's *annualized* expected
        # return applied to current equity. Anchored at 0 on day 0 so the
        # line is comparable to the cumulative realized series.
        daily_drift = float(expected_annual_return) * float(equity_usdt) / 365.0
        expected = [daily_drift * i for i in range(len(window))]
        fig.add_trace(go.Scatter(
            x=window, y=expected,
            mode="lines", name=f"Expected ({expected_annual_return:.1%}/yr × equity)",
            line={"color": "#1f77b4", "width": 2, "dash": "dash"},
        ))

    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 40, "r": 20, "t": 10, "b": 40},
        xaxis={"title": "Date (UTC)", "gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"title": "Cumulative PnL (USDT)", "gridcolor": "rgba(128,128,128,0.15)"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Expected line is a naive projection: `equity × expected_annual_return × (days/365)`. "
        "It assumes the optimizer's allocation is actually being traded — which this bot does not do. "
        "Use it as a calibration reference, not a performance benchmark."
    )


def _render_optimizer_context(opt_summary: dict[str, Any]) -> None:
    """Small context row so you know *which* optimizer output you're comparing against."""
    cols = st.columns(3)
    exp = opt_summary.get("expected_return")
    vol = opt_summary.get("volatility")
    sr = opt_summary.get("sharpe_ratio")
    cols[0].metric("Model expected return", f"{exp:.2%}" if exp is not None else "—")
    cols[1].metric("Model volatility", f"{vol:.2%}" if vol is not None else "—")
    cols[2].metric("Model Sharpe", f"{sr:.2f}" if sr is not None else "—")


# --- entry point ------------------------------------------------------------


def page_comparison() -> None:
    """Theory (optimizer) vs reality (bot) diagnostic page."""
    st.header("Theory vs Reality")
    _render_banner()

    opt_summary = _fetch_optimizer_summary()
    cfg = load_trading_config()
    snap = _load_ledger_snapshot(str(cfg.ledger_path))

    if opt_summary is None:
        st.error(
            f"Could not fetch optimizer summary from `{_API_URL}/portfolio/summary`. "
            "Is the API service up and has the optimization pipeline run?"
        )
        return
    if not snap.get("available"):
        st.warning(
            f"Ledger not found at `{cfg.ledger_path}`. The trading DAG hasn't run "
            "yet — the reality side of this comparison will be empty until it does."
        )
        return

    weights: dict[str, float] = opt_summary.get("weights") or {}
    open_positions: list[dict[str, Any]] = snap["open_positions"]
    equity_usdt: float | None = snap.get("equity_usdt")

    rows = _build_comparison_rows(weights, open_positions, equity_usdt)

    _render_optimizer_context(opt_summary)
    st.markdown("---")
    _render_kpis(weights, rows, equity_usdt, open_positions)
    st.markdown("---")
    _render_gap_table(rows)
    st.markdown("---")
    _render_pnl_overlay(
        snap.get("pnl_by_day") or [],
        opt_summary.get("expected_return"),
        equity_usdt,
    )


# Keep OpenPosition import live for type-completeness — the page returns dicts
# but the dataclass is part of the module's logical contract.
_ = OpenPosition
