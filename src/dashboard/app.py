"""
Streamlit dashboard for portfolio optimization visualization.

Connects to FastAPI backend to display:
- KPI cards (return, vol, Sharpe, Sortino, Max DD, HHI concentration)
- Portfolio allocation donut + risk-return scatter
- Normalized price comparison (all symbols rebased to 1.0)
- Rolling average pairwise correlation over time
- Correlation & covariance heatmaps + monthly returns heatmap
- Technical price charts (SMA, Bollinger, RSI, volume) + compare mode
- Efficient frontier with iso-Sharpe curves
- Risk Analysis page: rolling vol, skew/kurtosis, beta, VaR/CVaR, network
- Walk-forward backtest analytics
"""

import math
import os
import time
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# =============================================================================
# Global Styling Constants
# =============================================================================

API_URL = os.getenv("API_URL", "http://localhost:8000")

COLORS = {
    "strategy": "#2ca02c",
    "equal": "#1f77b4",
    "btc": "#ff7f0e",
    "accent": "#9467bd",
    "danger": "#d62728",
    "assets": px.colors.qualitative.Set2,
}

CHART_LAYOUT: dict[str, Any] = {
    "font_family": "Inter, system-ui, sans-serif",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 60, "r": 30, "t": 50, "b": 50},
    "hoverlabel": {"bgcolor": "white", "font_size": 12},
    "xaxis": {"gridcolor": "rgba(128,128,128,0.15)", "zeroline": False},
    "yaxis": {"gridcolor": "rgba(128,128,128,0.15)", "zeroline": False},
}

RANGE_SELECTOR: dict[str, Any] = {
    "buttons": [
        {"count": 1, "label": "1M", "step": "month", "stepmode": "backward"},
        {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
        {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
        {"count": 1, "label": "YTD", "step": "year", "stepmode": "todate"},
        {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"},
        {"step": "all", "label": "All"},
    ],
    "activecolor": "#2ca02c",
    "bgcolor": "rgba(150,150,150,0.2)",
    "font": {"size": 13, "color": "white"},
    "bordercolor": "rgba(150,150,150,0.4)",
    "borderwidth": 1,
    "x": 0,
    "y": 1.13,
}

STRATEGY_LABELS = {
    "strategy": "Optimized",
    "equal_weight": "Equal Weight",
    "btc_only": "BTC Only",
}

STRATEGY_COLORS = {
    "strategy": COLORS["strategy"],
    "equal_weight": COLORS["equal"],
    "btc_only": COLORS["btc"],
}


def fmt_pct(v: float | None) -> str:
    """Format a value as a percentage string."""
    return f"{v:.2%}" if v is not None else "N/A"


def fmt_ratio(v: float | None) -> str:
    """Format a ratio with 2 decimal places."""
    return f"{v:.2f}" if v is not None else "N/A"


def styled_layout(fig: go.Figure, **overrides: Any) -> go.Figure:
    """Apply consistent chart styling and return the figure."""
    merged = {**CHART_LAYOUT, **overrides}
    fig.update_layout(**merged)
    return fig


# =============================================================================
# API Helpers
# =============================================================================


@st.cache_data(ttl=300, show_spinner=False)  # type: ignore[untyped-decorator]
def fetch_api(endpoint: str) -> dict[str, Any] | None:
    """Fetch data from API endpoint, cached for 5 minutes."""
    try:
        response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data
    except requests.RequestException:
        return None


# =============================================================================
# Portfolio Mode Helpers (Crypto vs Traditional toggle)
# =============================================================================


def _is_trad_mode() -> bool:
    """Return True when the sidebar toggle is set to Traditional."""
    return st.session_state.get("portfolio_mode") == "Traditional"


def _portfolio_endpoint() -> str:
    """Return /portfolio or /portfolio/trad based on toggle."""
    return "/portfolio/trad" if _is_trad_mode() else "/portfolio"


def _frontier_endpoint() -> str:
    return "/portfolio/trad/frontier" if _is_trad_mode() else "/portfolio/frontier"


def _backtest_endpoint() -> str:
    return "/portfolio/trad/backtest" if _is_trad_mode() else "/portfolio/backtest"


def _metric_endpoint(name: str) -> str:
    """Return /metrics/{name}_trad or /metrics/{name} based on toggle."""
    return f"/metrics/{name}_trad" if _is_trad_mode() else f"/metrics/{name}"


def _strategy_labels() -> dict[str, str]:
    if _is_trad_mode():
        return {"strategy": "Optimized", "equal_weight": "Equal Weight", "spy_only": "SPY Only"}
    return dict(STRATEGY_LABELS)


def _strategy_colors() -> dict[str, str]:
    if _is_trad_mode():
        return {
            "strategy": COLORS["strategy"],
            "equal_weight": COLORS["equal"],
            "spy_only": COLORS["btc"],
        }
    return dict(STRATEGY_COLORS)


# =============================================================================
# Math Helpers (pure Python, no Streamlit state)
# =============================================================================


def _compute_hhi(weights: dict[str, float]) -> float:
    """Herfindahl-Hirschman Index = sum(w²). 1/n = diversified, 1.0 = concentrated."""
    return sum(w ** 2 for w in weights.values())


def _compute_risk_contribution(
    weights: dict[str, float],
    cov_matrix: list[list[float]],
    symbols: list[str],
) -> dict[str, float]:
    """Percentage risk contribution per asset.

    RC_i = w_i * (Σw)_i / σ²_p  (Euler decomposition, sums to 1.0).
    """
    n = len(symbols)
    w = [weights.get(s, 0.0) for s in symbols]
    # (Σw)_i = dot product of row i with weight vector
    sigma_w = [
        sum(cov_matrix[i][j] * w[j] for j in range(n))
        for i in range(n)
    ]
    port_var = sum(w[i] * sigma_w[i] for i in range(n))
    if port_var < 1e-12:
        return {s: 1 / n for s in symbols}
    return {symbols[i]: w[i] * sigma_w[i] / port_var for i in range(n)}


def _compute_rolling_pair_corr(
    returns_a: list[float],
    returns_b: list[float],
    window: int = 30,
) -> list[float | None]:
    """Rolling correlation between two return series."""
    n = min(len(returns_a), len(returns_b))
    result: list[float | None] = [None] * n
    for t in range(window - 1, n):
        xa = returns_a[t - window + 1:t + 1]
        xb = returns_b[t - window + 1:t + 1]
        mean_a = sum(xa) / window
        mean_b = sum(xb) / window
        cov = sum((xa[k] - mean_a) * (xb[k] - mean_b) for k in range(window)) / window
        var_a = sum((x - mean_a) ** 2 for x in xa) / window
        var_b = sum((x - mean_b) ** 2 for x in xb) / window
        denom = (var_a * var_b) ** 0.5
        result[t] = cov / denom if denom > 1e-10 else 0.0
    return result


def _compute_rolling_avg_corr(
    returns_matrix: list[list[float]],
    window: int = 30,
) -> list[float | None]:
    """Compute rolling average pairwise correlation across all symbol pairs."""
    n_symbols = len(returns_matrix)
    if n_symbols < 2:
        return []
    n_dates = min(len(r) for r in returns_matrix)
    result: list[float | None] = [None] * n_dates
    for t in range(window - 1, n_dates):
        corrs = []
        for i in range(n_symbols):
            for j in range(i + 1, n_symbols):
                xi = returns_matrix[i][t - window + 1:t + 1]
                xj = returns_matrix[j][t - window + 1:t + 1]
                mean_i = sum(xi) / window
                mean_j = sum(xj) / window
                cov = sum((xi[k] - mean_i) * (xj[k] - mean_j) for k in range(window)) / window
                var_i = sum((x - mean_i) ** 2 for x in xi) / window
                var_j = sum((x - mean_j) ** 2 for x in xj) / window
                denom = (var_i * var_j) ** 0.5
                if denom > 1e-10:
                    corrs.append(cov / denom)
        result[t] = sum(corrs) / len(corrs) if corrs else None
    return result


def _compute_rolling_vol(
    returns: list[float],
    window: int = 30,
    trading_days: int = 365,
) -> list[float | None]:
    """Compute rolling annualized volatility."""
    result: list[float | None] = [None] * len(returns)
    for i in range(window - 1, len(returns)):
        seg = returns[i - window + 1:i + 1]
        mean = sum(seg) / window
        var = sum((r - mean) ** 2 for r in seg) / window
        result[i] = (var ** 0.5) * (trading_days ** 0.5)
    return result


def _compute_beta(
    sym_returns: list[float],
    market_returns: list[float],
) -> float:
    """Compute beta = Cov(sym, market) / Var(market)."""
    n = min(len(sym_returns), len(market_returns))
    if n < 2:
        return 1.0
    s = sym_returns[:n]
    m = market_returns[:n]
    mean_s = sum(s) / n
    mean_m = sum(m) / n
    cov = sum((s[i] - mean_s) * (m[i] - mean_m) for i in range(n)) / n
    var_m = sum((r - mean_m) ** 2 for r in m) / n
    return cov / var_m if var_m > 1e-10 else 1.0


def _compute_skewness(returns: list[float]) -> float:
    """Third standardized moment."""
    n = len(returns)
    if n < 3:
        return 0.0
    mean = sum(returns) / n
    std = (sum((r - mean) ** 2 for r in returns) / n) ** 0.5
    if std < 1e-10:
        return 0.0
    return float(sum(((r - mean) / std) ** 3 for r in returns) / n)


def _compute_kurtosis(returns: list[float]) -> float:
    """Excess kurtosis (Fisher): 4th standardized moment − 3."""
    n = len(returns)
    if n < 4:
        return 0.0
    mean = sum(returns) / n
    std = (sum((r - mean) ** 2 for r in returns) / n) ** 0.5
    if std < 1e-10:
        return 0.0
    return float(sum(((r - mean) / std) ** 4 for r in returns) / n - 3.0)


def _compute_var_cvar(
    returns: list[float],
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Compute VaR and CVaR at given confidence from a return series."""
    if len(returns) < 5:
        return 0.0, 0.0
    sorted_r = sorted(returns)
    n = len(sorted_r)
    idx = max(0, int(n * (1 - confidence)) - 1)
    var = sorted_r[idx]
    tail = sorted_r[:idx + 1]
    cvar = sum(tail) / len(tail) if tail else var
    return var, cvar


# =============================================================================
# Shared Render Functions
# =============================================================================


def render_csv_export(df: pd.DataFrame, filename: str, label: str = "Export CSV") -> None:
    """Render a CSV download button for a DataFrame."""
    csv = df.to_csv(index=False)
    st.download_button(label=label, data=csv, file_name=filename, mime="text/csv")


def render_matrix_heatmap(
    symbols: list[str],
    matrix: list[list[float]],
    title: str,
    color_scale: str = "RdBu_r",
    zmin: float | None = None,
    zmax: float | None = None,
    fmt: str = ".2f",
) -> None:
    """Render an annotated heatmap from a symbol × symbol matrix."""
    fig = px.imshow(
        matrix,
        x=symbols,
        y=symbols,
        text_auto=fmt,
        aspect="auto",
        color_continuous_scale=color_scale,
        zmin=zmin,
        zmax=zmax,
    )
    styled_layout(fig, title=title)
    st.plotly_chart(fig, use_container_width=True)


def render_monthly_returns_heatmap(
    dates: list[str],
    values: list[list[float]],
    symbols: list[str],
    title: str = "Monthly Returns Heatmap",
) -> None:
    """Render a calendar-grid monthly returns heatmap."""
    if not dates or not values or not symbols:
        return

    month_returns: dict[str, dict[str, float]] = {}
    for day_idx, date_str in enumerate(dates):
        month_key = date_str[:7]
        if month_key not in month_returns:
            month_returns[month_key] = {s: 0.0 for s in symbols}
        for sym_idx, sym in enumerate(symbols):
            if sym_idx < len(values) and day_idx < len(values[sym_idx]):
                month_returns[month_key][sym] += values[sym_idx][day_idx]

    if not month_returns:
        return

    months = sorted(month_returns.keys())
    z = [[month_returns[m][s] for s in symbols] for m in months]

    fig = px.imshow(
        z,
        x=symbols,
        y=months,
        text_auto=".1%",
        aspect="auto",
        color_continuous_scale="RdYlGn",
    )
    styled_layout(fig, title=title, height=max(300, len(months) * 30 + 100))
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# Dashboard Page
# =============================================================================


def render_kpi_cards(
    portfolio: dict[str, Any],
    backtest_metrics: dict[str, Any] | None = None,
) -> None:
    """Render 6 KPI cards: 5 performance metrics + HHI concentration."""
    cols = st.columns(6)

    expected_return = portfolio.get("expected_return")
    volatility = portfolio.get("volatility")
    sharpe = portfolio.get("sharpe_ratio")
    weights = portfolio.get("weights", {})

    sortino = max_dd = equal_sharpe = equal_sortino = equal_max_dd = None
    if backtest_metrics:
        strat = backtest_metrics.get("strategy", {})
        eq = backtest_metrics.get("equal_weight", {})
        sortino = strat.get("sortino_ratio")
        max_dd = strat.get("max_drawdown")
        equal_sharpe = eq.get("sharpe_ratio")
        equal_sortino = eq.get("sortino_ratio")
        equal_max_dd = eq.get("max_drawdown")

    hhi = _compute_hhi(weights) if weights else None
    n = len(weights)
    hhi_min = 1 / n if n > 0 else None

    with cols[0]:
        st.metric("Expected Return", fmt_pct(expected_return))
    with cols[1]:
        st.metric("Volatility", fmt_pct(volatility))
    with cols[2]:
        delta_sharpe = (
            f"{sharpe - equal_sharpe:+.2f} vs equal"
            if sharpe is not None and equal_sharpe is not None
            else None
        )
        st.metric("Sharpe Ratio", fmt_ratio(sharpe), delta=delta_sharpe)
    with cols[3]:
        delta_sortino = (
            f"{sortino - equal_sortino:+.2f} vs equal"
            if sortino is not None and equal_sortino is not None
            else None
        )
        st.metric("Sortino Ratio", fmt_ratio(sortino), delta=delta_sortino)
    with cols[4]:
        delta_dd = (
            f"{max_dd - equal_max_dd:+.2%} vs equal"
            if max_dd is not None and equal_max_dd is not None
            else None
        )
        st.metric("Max Drawdown", fmt_pct(max_dd), delta=delta_dd, delta_color="inverse")
    with cols[5]:
        hhi_label = f"{hhi:.3f}" if hhi is not None else "N/A"
        hhi_delta = f"min={hhi_min:.3f}" if hhi_min is not None else None
        st.metric(
            "HHI Concentration",
            hhi_label,
            delta=hhi_delta,
            delta_color="off",
            help="Herfindahl index: lower = more diversified. Perfect = 1/n.",
        )


def render_allocation_donut(weights: dict[str, float]) -> None:
    """Render portfolio allocation as a horizontal bar chart (handles short positions)."""
    if not weights:
        st.warning("No allocation data available")
        return

    sorted_w = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    syms = [p[0] for p in sorted_w]
    vals = [p[1] for p in sorted_w]
    colors = [
        COLORS["strategy"] if v >= 0 else COLORS["danger"]
        for v in vals
    ]

    fig = go.Figure(go.Bar(
        x=vals, y=syms, orientation="h",
        marker_color=colors,
        text=[f"{v:.1%}" for v in vals],
        textposition="auto",
        hovertemplate="%{y}: %{x:.4f} (%{x:.2%})<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="gray", line_width=1, opacity=0.5)
    styled_layout(
        fig,
        title="Portfolio Allocation",
        xaxis={"tickformat": ".0%", "gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        height=max(250, len(syms) * 35 + 100),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_risk_contribution(
    weights: dict[str, float],
    cov_data: dict[str, Any],
) -> None:
    """Side-by-side bars: portfolio weight vs risk contribution (handles short positions)."""
    symbols_cov = cov_data.get("symbols", [])
    matrix = cov_data.get("matrix", [])
    if not symbols_cov or not matrix or not weights:
        st.info("No covariance data for risk contribution")
        return

    rc = _compute_risk_contribution(weights, matrix, symbols_cov)

    syms = symbols_cov
    w_vals = [weights.get(s, 0.0) for s in syms]
    rc_vals = [rc.get(s, 0.0) for s in syms]

    # Sort by risk contribution descending
    order = sorted(range(len(syms)), key=lambda i: rc_vals[i], reverse=True)
    sorted_syms = [syms[i] for i in order]
    sorted_w = [w_vals[i] for i in order]
    sorted_rc = [rc_vals[i] for i in order]

    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True,
        subplot_titles=("Portfolio Weight", "Risk Contribution"),
        horizontal_spacing=0.08,
    )
    fig.add_trace(go.Bar(
        x=sorted_w, y=sorted_syms, orientation="h",
        marker_color=[COLORS["strategy"] if v >= 0 else COLORS["danger"] for v in sorted_w],
        text=[f"{v:.1%}" for v in sorted_w],
        textposition="auto",
        hovertemplate="%{y}: %{x:.2%}<extra></extra>",
        showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=sorted_rc, y=sorted_syms, orientation="h",
        marker_color=[COLORS["equal"] if v >= 0 else COLORS["danger"] for v in sorted_rc],
        text=[f"{v:.1%}" for v in sorted_rc],
        textposition="auto",
        hovertemplate="%{y}: %{x:.2%}<extra></extra>",
        showlegend=False,
    ), row=1, col=2)
    fig.add_vline(x=0, line_color="gray", line_width=1, opacity=0.5, row=1, col=1)
    fig.add_vline(x=0, line_color="gray", line_width=1, opacity=0.5, row=1, col=2)
    styled_layout(
        fig,
        title="Weight vs Risk Contribution",
        height=max(300, len(syms) * 30 + 120),
    )
    fig.update_xaxes(tickformat=".0%", row=1, col=1)
    fig.update_xaxes(tickformat=".0%", row=1, col=2)
    st.plotly_chart(fig, use_container_width=True)


def render_risk_return_scatter(
    mean_ret_data: dict[str, Any],
    vol_data: dict[str, Any],
    weights: dict[str, float],
) -> None:
    """Render risk-return bubble scatter: x=vol, y=return, size=weight."""
    symbols = mean_ret_data.get("symbols", [])
    ret_values = mean_ret_data.get("values", [])
    vol_values = vol_data.get("values", [])

    if not symbols or len(ret_values) != len(symbols) or len(vol_values) != len(symbols):
        st.info("Insufficient data for risk-return scatter")
        return

    w = [weights.get(s, 0.0) for s in symbols]
    max_w = max(w) if w else 1.0
    sizes = [max(8, (wi / max_w) * 50) if max_w > 0 else 15 for wi in w]

    fig = go.Figure()
    for i, sym in enumerate(symbols):
        fig.add_trace(go.Scatter(
            x=[vol_values[i]],
            y=[ret_values[i]],
            mode="markers+text",
            name=sym,
            text=[sym],
            textposition="top center",
            marker={
                "size": sizes[i],
                "color": COLORS["assets"][i % len(COLORS["assets"])],
                "line": {"width": 1, "color": "white"},
            },
            hovertemplate=(
                f"<b>{sym}</b><br>"
                f"Vol: %{{x:.2%}}<br>"
                f"Return: %{{y:.2%}}<br>"
                f"Weight: {w[i]:.2%}<extra></extra>"
            ),
        ))

    styled_layout(
        fig,
        title="Risk-Return by Asset",
        xaxis_title="Volatility (annualized)",
        yaxis_title="Expected Return (annualized)",
        xaxis={"tickformat": ".0%", "gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"tickformat": ".0%", "gridcolor": "rgba(128,128,128,0.15)"},
        showlegend=False,
        hovermode="closest",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_normalized_prices(symbols: list[str]) -> None:
    """All symbols rebased to 1.0 on day 1, overlaid line chart."""
    if not symbols:
        return

    fig = go.Figure()
    for i, sym in enumerate(symbols):
        klines = fetch_api(f"/klines/{sym}")
        if not klines or not klines.get("data"):
            continue
        df = pd.DataFrame(klines["data"])
        if "timestamp" in df.columns:
            dates = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d").tolist()
        elif "open_time" in df.columns:
            dates = pd.to_datetime(df["open_time"], unit="ms").dt.strftime("%Y-%m-%d").tolist()
        else:
            dates = [str(i) for i in range(len(df))]

        closes = pd.to_numeric(df["close"], errors="coerce").tolist()
        if not closes or closes[0] == 0:
            continue

        normalized = [c / closes[0] for c in closes]
        fig.add_trace(go.Scatter(
            x=dates,
            y=normalized,
            mode="lines",
            name=sym,
            line={"color": COLORS["assets"][i % len(COLORS["assets"])], "width": 1.5},
            hovertemplate=f"<b>{sym}</b><br>%{{x}}<br>Value: %{{y:.3f}}x<extra></extra>",
        ))

    fig.add_hline(y=1.0, line_dash="dash", line_color="gray", opacity=0.4)
    styled_layout(
        fig,
        title="Normalized Price Performance (rebased to 1.0)",
        xaxis_title="Date",
        yaxis_title="Relative Value",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_rolling_avg_correlation(returns_data: dict[str, Any], window: int = 30) -> None:
    """Rolling average pairwise correlation across all symbol pairs."""
    symbols = returns_data.get("symbols", [])
    dates = returns_data.get("dates", [])
    values = returns_data.get("values", [])

    if len(symbols) < 2 or not dates or not values:
        st.info("Need at least 2 symbols for correlation chart")
        return

    rolling = _compute_rolling_avg_corr(values, window=window)
    valid_pairs = [(dates[i], rolling[i]) for i in range(len(rolling)) if rolling[i] is not None]
    if not valid_pairs:
        return

    valid_dates = [p[0] for p in valid_pairs]
    valid_vals = [p[1] for p in valid_pairs]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=valid_dates,
        y=valid_vals,
        mode="lines",
        name=f"Avg Correlation ({window}d)",
        line={"color": COLORS["accent"], "width": 2},
        fill="tozeroy",
        fillcolor="rgba(148,103,189,0.1)",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4)
    styled_layout(
        fig,
        title=f"Rolling {window}-Day Average Pairwise Correlation",
        xaxis_title="Date",
        yaxis_title="Avg Correlation",
        yaxis={"range": [-1, 1], "gridcolor": "rgba(128,128,128,0.15)"},
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def page_dashboard() -> None:
    """Render the main Dashboard page."""
    mode_label = "Traditional" if _is_trad_mode() else "Crypto"
    st.title(f"Portfolio Optimization Dashboard — {mode_label}")

    portfolio = fetch_api(_portfolio_endpoint())
    if not portfolio:
        st.warning(
            "No portfolio data available. Run the pipeline first: "
            "`docker compose --profile pipeline up pipeline`"
        )
        return

    bt_data = fetch_api(_backtest_endpoint())
    bt_metrics = bt_data.get("metrics") if bt_data else None

    render_kpi_cards(portfolio, bt_metrics)
    st.markdown("---")

    weights = portfolio.get("weights", {})
    long_total = sum(w for w in weights.values() if w > 0)
    short_total = sum(w for w in weights.values() if w < 0)
    n_long = sum(1 for w in weights.values() if w > 0)
    n_short = sum(1 for w in weights.values() if w < 0)
    gross = long_total - short_total

    st.markdown(
        f"**Allocation Strategy** — The portfolio is optimized using the "
        f"**unconstrained Markowitz mean-variance** framework (closed-form analytical "
        f"solution). Weights are not bounded to \\[0, 1\\], allowing **short selling**: "
        f"the optimizer can go short on assets it expects to underperform and use the "
        f"proceeds to overweight assets with better risk-adjusted returns. "
        f"The current allocation holds **{n_long} long** and **{n_short} short** "
        f"positions, with a gross exposure of **{gross:.0%}** "
        f"(+{long_total:.0%} long / {short_total:.0%} short). "
        f"Net exposure is always 100% by construction (weights sum to 1)."
    )

    cov_resp = fetch_api(_metric_endpoint("covariance"))

    col1, col2, col3 = st.columns(3)
    with col1:
        render_allocation_donut(portfolio.get("weights", {}))
    with col2:
        if cov_resp and cov_resp.get("data"):
            render_risk_contribution(portfolio.get("weights", {}), cov_resp["data"])
        else:
            st.info("Run transform pipeline for risk contribution")
    with col3:
        mean_ret = fetch_api(_metric_endpoint("mean_returns"))
        vol = fetch_api(_metric_endpoint("volatility"))
        if mean_ret and vol and mean_ret.get("data") and vol.get("data"):
            render_risk_return_scatter(
                mean_ret["data"], vol["data"], portfolio.get("weights", {})
            )
        else:
            st.info("Run transform pipeline for risk-return scatter")

    st.markdown("---")

    symbols_resp = fetch_api("/symbols")
    all_syms = symbols_resp.get("symbols", []) if symbols_resp else []
    if _is_trad_mode():
        dash_symbols = [s for s in all_syms if not s.endswith(("USDT", "BUSD"))]
    else:
        dash_symbols = [s for s in all_syms if s.endswith(("USDT", "BUSD"))]
    if dash_symbols:
        render_normalized_prices(dash_symbols)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        corr = fetch_api(_metric_endpoint("correlation"))
        if corr and corr.get("data"):
            cd = corr["data"]
            render_matrix_heatmap(
                cd.get("symbols", []),
                cd.get("matrix", []),
                "Correlation Matrix",
                color_scale="RdBu_r",
                zmin=-1,
                zmax=1,
            )
    with col2:
        if cov_resp and cov_resp.get("data"):
            cd = cov_resp["data"]
            render_matrix_heatmap(
                cd.get("symbols", []),
                cd.get("matrix", []),
                "Covariance Matrix",
                color_scale="Viridis",
            )

    st.markdown("---")

    returns_resp_dash = fetch_api(_metric_endpoint("returns"))
    if returns_resp_dash and returns_resp_dash.get("data"):
        rd = returns_resp_dash["data"]
        render_rolling_avg_correlation(rd)
        st.markdown("---")
        render_monthly_returns_heatmap(
            rd.get("dates", []),
            rd.get("values", []),
            rd.get("symbols", []),
            title="Monthly Returns by Asset",
        )


# =============================================================================
# Symbols Page — Technical Indicators
# =============================================================================


def _compute_sma(closes: list[float], window: int) -> list[float | None]:
    """Compute simple moving average."""
    result: list[float | None] = [None] * len(closes)
    for i in range(window - 1, len(closes)):
        result[i] = sum(closes[i - window + 1: i + 1]) / window
    return result


def _compute_bollinger(
    closes: list[float], window: int = 20, num_std: float = 2.0,
) -> tuple[list[float | None], list[float | None]]:
    """Compute Bollinger Bands (upper, lower) from close prices."""
    upper: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)
    for i in range(window - 1, len(closes)):
        segment = closes[i - window + 1: i + 1]
        mean = sum(segment) / window
        variance = sum((x - mean) ** 2 for x in segment) / window
        std = variance ** 0.5
        upper[i] = mean + num_std * std
        lower[i] = mean - num_std * std
    return upper, lower


def _compute_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Compute RSI from close prices."""
    result: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return result

    gains = []
    losses = []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return result


def render_technical_chart(df: pd.DataFrame) -> None:
    """Render price chart with SMA, Bollinger Bands, Volume, and RSI subplots."""
    closes = df["close"].tolist()
    dates = df["date"].tolist()

    sma20 = _compute_sma(closes, 20)
    sma50 = _compute_sma(closes, 50)
    bb_upper, bb_lower = _compute_bollinger(closes, 20)
    rsi = _compute_rsi(closes, 14)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=("Price + Indicators", "Volume", "RSI (14)"),
    )

    if all(c in df.columns for c in ["open", "high", "low"]):
        fig.add_trace(go.Candlestick(
            x=dates, open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="OHLC",
            increasing_line_color=COLORS["strategy"],
            decreasing_line_color=COLORS["danger"],
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=dates, y=closes, mode="lines",
            name="Close", line={"color": COLORS["equal"], "width": 1.5},
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=dates, y=sma20, mode="lines", name="SMA 20",
        line={"color": "#e377c2", "width": 1, "dash": "dot"},
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=sma50, mode="lines", name="SMA 50",
        line={"color": "#17becf", "width": 1, "dash": "dot"},
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=bb_upper, mode="lines", name="BB Upper",
        line={"color": "rgba(150,150,150,0.4)", "width": 1},
        showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=bb_lower, mode="lines", name="BB Lower",
        line={"color": "rgba(150,150,150,0.4)", "width": 1},
        fill="tonexty", fillcolor="rgba(150,150,150,0.08)",
        showlegend=False,
    ), row=1, col=1)

    if "volume" in df.columns:
        vol_colors = [
            COLORS["strategy"] if c >= o else COLORS["danger"]
            for c, o in zip(df["close"], df["open"])
        ]
        fig.add_trace(go.Bar(
            x=dates, y=df["volume"], name="Volume",
            marker_color=vol_colors, opacity=0.6, showlegend=False,
        ), row=2, col=1)
        vol_sma = _compute_sma(df["volume"].tolist(), 20)
        fig.add_trace(go.Scatter(
            x=dates, y=vol_sma, mode="lines", name="Vol SMA 20",
            line={"color": COLORS["btc"], "width": 1},
            showlegend=False,
        ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=dates, y=rsi, mode="lines", name="RSI",
        line={"color": COLORS["accent"], "width": 1.5},
    ), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(214,39,40,0.5)", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(44,160,44,0.5)", row=3, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(128,128,128,0.05)", line_width=0, row=3, col=1)

    styled_layout(
        fig,
        height=700,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    fig.update_xaxes(type="date", rangeselector=RANGE_SELECTOR, row=1, col=1)
    fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)


def render_symbol_stats(df: pd.DataFrame) -> None:
    """Render 5 summary stat cards for a symbol."""
    cols = st.columns(5)
    closes = df["close"]
    with cols[0]:
        st.metric("Min Price", f"${closes.min():,.2f}")
    with cols[1]:
        st.metric("Max Price", f"${closes.max():,.2f}")
    with cols[2]:
        st.metric("Avg Price", f"${closes.mean():,.2f}")
    with cols[3]:
        if len(closes) > 1:
            daily_rets = closes.pct_change().dropna()
            st.metric("Daily Vol", f"{daily_rets.std():.2%}")
        else:
            st.metric("Daily Vol", "N/A")
    with cols[4]:
        if len(closes) > 1:
            total_return = (closes.iloc[-1] / closes.iloc[0]) - 1.0
            st.metric("Total Return", fmt_pct(total_return))
        else:
            st.metric("Total Return", "N/A")


def page_symbols() -> None:
    """Render the Symbols page."""
    mode_label = "Traditional" if _is_trad_mode() else "Crypto"
    st.title(f"Symbol Analysis — {mode_label}")

    symbols_data = fetch_api("/symbols")
    if not symbols_data or not symbols_data.get("symbols"):
        st.warning("No symbols available")
        return

    all_symbols = symbols_data["symbols"]
    # Filter: crypto symbols end with USDT/BUSD, traditional ones don't
    if _is_trad_mode():
        symbols = [s for s in all_symbols if not s.endswith(("USDT", "BUSD"))]
    else:
        symbols = [s for s in all_symbols if s.endswith(("USDT", "BUSD"))]

    if not symbols:
        st.warning(f"No {mode_label.lower()} symbols found. Run the pipeline first.")
        return

    col_sym, col_chart, col_compare = st.columns([2, 2, 1])
    with col_sym:
        selected_symbol = st.selectbox("Select Symbol", symbols)
    with col_chart:
        chart_type = st.selectbox(
            "Chart Type",
            ["Full (SMA + Bollinger + RSI)", "Candlestick + Volume", "Line only"],
        )
    with col_compare:
        compare_mode = st.checkbox("Compare", value=False)

    compare_symbol = None
    if compare_mode:
        other_symbols = [s for s in symbols if s != selected_symbol]
        compare_symbol = st.selectbox("Compare with", other_symbols)

    if not selected_symbol:
        return

    klines_data = fetch_api(f"/klines/{selected_symbol}")
    if not klines_data or not klines_data.get("data"):
        st.warning(f"No price data for {selected_symbol}")
        return

    df = pd.DataFrame(klines_data["data"])
    if "timestamp" in df.columns:
        df["date"] = pd.to_datetime(df["timestamp"])
    elif "open_time" in df.columns:
        df["date"] = pd.to_datetime(df["open_time"], unit="ms")
    else:
        df["date"] = range(len(df))

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Compare mode: normalized overlay
    if compare_mode and compare_symbol:
        klines_b = fetch_api(f"/klines/{compare_symbol}")
        if klines_b and klines_b.get("data"):
            df_b = pd.DataFrame(klines_b["data"])
            if "timestamp" in df_b.columns:
                df_b["date"] = pd.to_datetime(df_b["timestamp"])
            elif "open_time" in df_b.columns:
                df_b["date"] = pd.to_datetime(df_b["open_time"], unit="ms")
            df_b["close"] = pd.to_numeric(df_b["close"], errors="coerce")

            closes_a = df["close"].tolist()
            closes_b = df_b["close"].tolist()
            norm_a = [c / closes_a[0] for c in closes_a] if closes_a[0] else closes_a
            norm_b = [c / closes_b[0] for c in closes_b] if closes_b[0] else closes_b

            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Scatter(
                x=df["date"], y=norm_a, mode="lines",
                name=selected_symbol,
                line={"color": COLORS["strategy"], "width": 2},
            ))
            fig_cmp.add_trace(go.Scatter(
                x=df_b["date"], y=norm_b, mode="lines",
                name=compare_symbol,
                line={"color": COLORS["btc"], "width": 2},
            ))
            fig_cmp.add_hline(y=1.0, line_dash="dash", line_color="gray", opacity=0.4)
            styled_layout(
                fig_cmp,
                title=f"{selected_symbol} vs {compare_symbol} (normalized to 1.0)",
                xaxis_title="Date",
                yaxis_title="Relative Value",
                hovermode="x unified",
            )
            st.plotly_chart(fig_cmp, use_container_width=True)

    # Main chart
    range_sel = RANGE_SELECTOR
    if chart_type.startswith("Full"):
        render_technical_chart(df)
    elif chart_type.startswith("Candlestick") and all(
        c in df.columns for c in ["open", "high", "low", "close"]
    ):
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.03, row_heights=[0.7, 0.3],
        )
        fig.add_trace(go.Candlestick(
            x=df["date"], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="OHLC",
        ), row=1, col=1)
        if "volume" in df.columns:
            colors = [
                COLORS["strategy"] if c >= o else COLORS["danger"]
                for c, o in zip(df["close"], df["open"])
            ]
            fig.add_trace(go.Bar(
                x=df["date"], y=df["volume"], name="Volume",
                marker_color=colors, opacity=0.6,
            ), row=2, col=1)
        styled_layout(fig, title=f"{selected_symbol} OHLCV",
                      xaxis_rangeslider_visible=False, hovermode="x unified")
        fig.update_xaxes(type="date", rangeselector=range_sel, row=1, col=1)
        fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig = go.Figure(go.Scatter(
            x=df["date"], y=df["close"], mode="lines",
            name="Close Price", line={"color": COLORS["equal"]},
        ))
        styled_layout(fig, title=f"{selected_symbol} Price History",
                      xaxis_title="Date", yaxis_title="Price (USDT)",
                      hovermode="x unified")
        fig.update_xaxes(type="date", rangeselector=range_sel)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    render_symbol_stats(df)

    st.markdown("---")
    st.subheader("Raw Data")
    st.dataframe(df.drop(columns=["date"], errors="ignore").tail(30), use_container_width=True)
    render_csv_export(df.drop(columns=["date"], errors="ignore"), f"{selected_symbol}_klines.csv")


# =============================================================================
# Metrics Page
# =============================================================================


def render_cumulative_returns_chart(returns_data: dict[str, Any]) -> None:
    """Render cumulative return lines, one per symbol."""
    symbols = returns_data.get("symbols", [])
    dates = returns_data.get("dates", [])
    values = returns_data.get("values", [])

    if not symbols or not dates or not values:
        return

    fig = go.Figure()
    for i, sym in enumerate(symbols):
        if i >= len(values):
            break
        cum = []
        running = 0.0
        for r in values[i]:
            running += r
            cum.append(math.exp(running) - 1.0)

        fig.add_trace(go.Scatter(
            x=dates[:len(cum)], y=cum, mode="lines", name=sym,
            line={"color": COLORS["assets"][i % len(COLORS["assets"])], "width": 1.5},
            hovertemplate=f"<b>{sym}</b><br>Date: %{{x}}<br>Return: %{{y:.2%}}<extra></extra>",
        ))

    styled_layout(
        fig,
        title="Cumulative Returns by Symbol",
        xaxis_title="Date",
        yaxis_title="Cumulative Return",
        yaxis={"tickformat": ".0%", "gridcolor": "rgba(128,128,128,0.15)"},
        xaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_sorted_bar(symbols: list[str], values: list[float], title: str, fmt: str = ".2%") -> None:
    """Render a horizontal sorted bar chart."""
    if not symbols or not values:
        return

    pairs = sorted(zip(symbols, values), key=lambda x: x[1], reverse=True)
    sorted_sym = [p[0] for p in pairs]
    sorted_val = [p[1] for p in pairs]

    fig = go.Figure(go.Bar(
        x=sorted_val,
        y=sorted_sym,
        orientation="h",
        marker_color=[COLORS["assets"][i % len(COLORS["assets"])] for i in range(len(sorted_sym))],
        text=[f"{v:{fmt[1:]}}" for v in sorted_val],
        textposition="auto",
    ))
    styled_layout(
        fig,
        title=title,
        xaxis={"tickformat": fmt, "gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        height=max(300, len(symbols) * 40 + 100),
    )
    st.plotly_chart(fig, use_container_width=True)


def _metric_to_dataframe(data: Any) -> pd.DataFrame:
    """Safely convert a metric data dict to a displayable DataFrame."""
    if not isinstance(data, dict):
        try:
            return pd.DataFrame(data)
        except Exception:
            return pd.DataFrame({"raw": [str(data)]})

    if "matrix" in data:
        symbols = data.get("symbols", [])
        return pd.DataFrame(data["matrix"], index=symbols, columns=symbols)

    if "values" in data and "symbols" in data:
        symbols = data.get("symbols", [])
        values = data.get("values", [])
        if "dates" in data:
            return pd.DataFrame(
                {sym: values[i] for i, sym in enumerate(symbols) if i < len(values)},
                index=data["dates"],
            )
        return pd.DataFrame({"Symbol": symbols, "Value": values})

    rows = []
    for k, v in data.items():
        rows.append({"Key": k, "Value": str(v) if isinstance(v, list) else v})
    return pd.DataFrame(rows)


def render_risk_return_table(
    mean_ret_data: dict[str, Any], vol_data: dict[str, Any],
) -> None:
    """Render formatted risk-return summary table with per-symbol Sharpe."""
    symbols = mean_ret_data.get("symbols", [])
    ret_vals = mean_ret_data.get("values", [])
    vol_vals = vol_data.get("values", [])

    if not symbols or len(ret_vals) != len(symbols) or len(vol_vals) != len(symbols):
        return

    rows = []
    for i, sym in enumerate(symbols):
        r = ret_vals[i]
        v = vol_vals[i]
        sharpe = r / v if v > 1e-10 else 0.0
        rows.append({
            "Symbol": sym,
            "Ann. Return": f"{r:.2%}",
            "Ann. Volatility": f"{v:.2%}",
            "Sharpe": f"{sharpe:.2f}",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def page_metrics() -> None:
    """Render the Metrics Explorer page."""
    st.title("Metrics Explorer")

    metrics_list = fetch_api("/metrics")
    if not metrics_list or not metrics_list.get("metrics"):
        st.warning("No metrics available")
        return

    metrics = metrics_list["metrics"]
    selected_metric = st.selectbox("Select Metric", metrics)

    if not selected_metric:
        return

    metric_resp = fetch_api(f"/metrics/{selected_metric}")
    if not metric_resp or not metric_resp.get("data"):
        st.warning(f"No data for metric: {selected_metric}")
        return

    data = metric_resp["data"]
    st.subheader(selected_metric.replace("_", " ").title())

    if selected_metric == "returns":
        render_cumulative_returns_chart(data)
    elif selected_metric == "volatility":
        render_sorted_bar(
            data.get("symbols", []), data.get("values", []),
            "Annualized Volatility by Symbol",
        )
    elif selected_metric == "mean_returns":
        render_sorted_bar(
            data.get("symbols", []), data.get("values", []),
            "Annualized Mean Returns by Symbol",
        )
    elif selected_metric == "correlation":
        render_matrix_heatmap(
            data.get("symbols", []), data.get("matrix", []),
            "Correlation Matrix", color_scale="RdBu_r", zmin=-1, zmax=1,
        )
        # Rolling per-pair correlation
        st.markdown("---")
        st.subheader("Rolling Pair Correlation")
        returns_resp2 = fetch_api("/metrics/returns")
        if returns_resp2 and returns_resp2.get("data"):
            rd2 = returns_resp2["data"]
            pair_symbols = rd2.get("symbols", [])
            pair_dates = rd2.get("dates", [])
            pair_values = rd2.get("values", [])
            if len(pair_symbols) >= 2:
                col_a, col_b = st.columns(2)
                with col_a:
                    sym_a = st.selectbox("Symbol A", pair_symbols, key="pair_a")
                with col_b:
                    sym_b = st.selectbox(
                        "Symbol B",
                        [s for s in pair_symbols if s != sym_a],
                        key="pair_b",
                    )
                idx_a = pair_symbols.index(sym_a)
                idx_b = pair_symbols.index(sym_b)
                rolling_corr = _compute_rolling_pair_corr(
                    pair_values[idx_a], pair_values[idx_b], window=30
                )
                valid = [(pair_dates[i], rolling_corr[i])
                         for i in range(len(rolling_corr)) if rolling_corr[i] is not None]
                if valid:
                    fig_rc = go.Figure()
                    fig_rc.add_trace(go.Scatter(
                        x=[v[0] for v in valid],
                        y=[v[1] for v in valid],
                        mode="lines",
                        name=f"{sym_a} / {sym_b}",
                        line={"color": COLORS["accent"], "width": 2},
                        fill="tozeroy",
                        fillcolor="rgba(148,103,189,0.1)",
                    ))
                    fig_rc.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4)
                    styled_layout(
                        fig_rc,
                        title=f"Rolling 30-Day Correlation: {sym_a} / {sym_b}",
                        xaxis_title="Date",
                        yaxis_title="Correlation",
                        yaxis={"range": [-1, 1], "gridcolor": "rgba(128,128,128,0.15)"},
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig_rc, use_container_width=True)
    elif selected_metric == "covariance":
        render_matrix_heatmap(
            data.get("symbols", []), data.get("matrix", []),
            "Covariance Matrix", color_scale="Viridis",
        )

    st.markdown("---")
    st.subheader("Risk-Return Summary")
    mean_ret = fetch_api("/metrics/mean_returns")
    vol = fetch_api("/metrics/volatility")
    if mean_ret and vol and mean_ret.get("data") and vol.get("data"):
        render_risk_return_table(mean_ret["data"], vol["data"])

    st.markdown("---")
    st.subheader("Raw Data")
    df = _metric_to_dataframe(data)
    st.dataframe(df, use_container_width=True)
    render_csv_export(df, f"{selected_metric}.csv")


# =============================================================================
# Frontier Page
# =============================================================================


def page_frontier() -> None:
    """Render the Efficient Frontier page."""
    mode_label = "Traditional" if _is_trad_mode() else "Crypto"
    st.title(f"Efficient Frontier — {mode_label}")

    frontier_data = fetch_api(_frontier_endpoint())
    if not frontier_data:
        st.warning(
            "No frontier data available. Run: "
            "`python -c \"from src.pipeline.optimize import compute_and_save_frontier; compute_and_save_frontier()\"`"
        )
        return

    symbols = frontier_data.get("symbols", [])
    frontier = frontier_data.get("frontier", [])
    max_sharpe = frontier_data.get("max_sharpe", {})
    min_var = frontier_data.get("min_variance", {})
    assets = frontier_data.get("assets", [])
    cml = frontier_data.get("capital_market_line", {})
    rf = frontier_data.get("risk_free_rate", 0.05)

    fig = go.Figure()

    # Determine vol range from frontier + assets for iso-Sharpe lines
    all_vols = [p["volatility"] for p in frontier] + [a["volatility"] for a in assets]
    max_vol = max(all_vols) * 1.15 if all_vols else 1.0

    for sharpe_val in [0.5, 1.0, 1.5, 2.0]:
        n_pts = max(50, int(max_vol * 100))
        iso_vol = [max_vol * i / n_pts for i in range(1, n_pts + 1)]
        iso_ret = [rf + sharpe_val * v for v in iso_vol]
        fig.add_trace(go.Scatter(
            x=iso_vol, y=iso_ret, mode="lines",
            line={"color": "rgba(180,180,180,0.3)", "width": 1, "dash": "dot"},
            showlegend=False,
            hoverinfo="skip",
        ))
        fig.add_annotation(
            x=iso_vol[-1], y=iso_ret[-1],
            text=f"S={sharpe_val}",
            showarrow=False,
            font={"size": 9, "color": "rgba(150,150,150,0.6)"},
        )

    if frontier:
        fig.add_trace(go.Scatter(
            x=[p["volatility"] for p in frontier],
            y=[p["return"] for p in frontier],
            mode="lines",
            name="Efficient Frontier",
            line={"color": COLORS["equal"], "width": 3},
        ))

    if assets:
        asset_labels = [
            symbols[a["symbol_index"]] if a["symbol_index"] < len(symbols) else f"Asset {a['symbol_index']}"
            for a in assets
        ]
        fig.add_trace(go.Scatter(
            x=[a["volatility"] for a in assets],
            y=[a["return"] for a in assets],
            mode="markers+text",
            name="Assets",
            marker={"symbol": "diamond", "size": 12, "color": COLORS["danger"]},
            text=asset_labels,
            textposition="top center",
            textfont={"size": 10},
        ))

    if max_sharpe:
        ms_ret = max_sharpe.get("return", 0)
        ms_vol = max_sharpe.get("volatility", 0)
        ms_sharpe = (ms_ret - rf) / ms_vol if ms_vol > 1e-10 else 0.0
        fig.add_trace(go.Scatter(
            x=[ms_vol], y=[ms_ret],
            mode="markers",
            name=f"Max Sharpe ({ms_sharpe:.2f})",
            marker={"symbol": "star", "size": 18, "color": COLORS["strategy"],
                    "line": {"width": 1, "color": "white"}},
        ))

    if min_var:
        fig.add_trace(go.Scatter(
            x=[min_var["volatility"]], y=[min_var["return"]],
            mode="markers",
            name="Min Variance",
            marker={"symbol": "square", "size": 14, "color": COLORS["btc"],
                    "line": {"width": 1, "color": "white"}},
        ))

    current = fetch_api("/portfolio")
    if current and current.get("volatility") and current.get("expected_return"):
        fig.add_trace(go.Scatter(
            x=[current["volatility"]], y=[current["expected_return"]],
            mode="markers",
            name="Current Portfolio",
            marker={"symbol": "circle", "size": 14, "color": COLORS["accent"],
                    "line": {"width": 2, "color": "white"}},
        ))

    if cml and cml.get("x") and cml.get("y"):
        fig.add_trace(go.Scatter(
            x=cml["x"], y=cml["y"],
            mode="lines",
            name=f"CML (Rf={rf:.1%})",
            line={"color": "gray", "dash": "dash", "width": 1},
        ))

    styled_layout(
        fig,
        title="Efficient Frontier (Markowitz)",
        xaxis_title="Volatility (annualized)",
        yaxis_title="Expected Return (annualized)",
        hovermode="closest",
        xaxis={"tickformat": ".1%", "gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"tickformat": ".1%", "gridcolor": "rgba(128,128,128,0.15)"},
        height=550,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    portfolio_type = st.selectbox("View portfolio weights", ["Max Sharpe", "Min Variance"])
    selected = max_sharpe if portfolio_type == "Max Sharpe" else min_var
    if selected and selected.get("weights"):
        weights_map = {
            symbols[i]: selected["weights"][i]
            for i in range(min(len(symbols), len(selected["weights"])))
        }

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Expected Return", fmt_pct(selected.get("return")))
        with col2:
            st.metric("Volatility", fmt_pct(selected.get("volatility")))

        sorted_weights = sorted(weights_map.items(), key=lambda x: x[1], reverse=True)
        w_symbols = [p[0] for p in sorted_weights]
        w_values = [p[1] for p in sorted_weights]

        fig_w = go.Figure(go.Bar(
            x=w_values, y=w_symbols, orientation="h",
            marker_color=[COLORS["assets"][i % len(COLORS["assets"])] for i in range(len(w_symbols))],
            text=[f"{v:.1%}" for v in w_values],
            textposition="auto",
        ))
        styled_layout(
            fig_w,
            title=f"{portfolio_type} — Weights",
            xaxis={"tickformat": ".0%", "gridcolor": "rgba(128,128,128,0.15)"},
            yaxis={"gridcolor": "rgba(128,128,128,0.15)"},
            height=max(250, len(w_symbols) * 35 + 100),
        )
        st.plotly_chart(fig_w, use_container_width=True)

        df_w = pd.DataFrame({"Symbol": w_symbols, "Weight": w_values})
        render_csv_export(df_w, f"frontier_{portfolio_type.lower().replace(' ', '_')}.csv",
                          "Export weights CSV")


# =============================================================================
# Risk Analysis Page
# =============================================================================


def render_rolling_vol_chart(returns_data: dict[str, Any], window: int = 30) -> None:
    """Rolling annualized volatility per symbol."""
    symbols = returns_data.get("symbols", [])
    dates = returns_data.get("dates", [])
    values = returns_data.get("values", [])

    if not symbols or not dates or not values:
        st.info("No returns data available")
        return

    fig = go.Figure()
    for i, sym in enumerate(symbols):
        if i >= len(values):
            break
        rolling = _compute_rolling_vol(values[i], window=window)
        valid_pairs = [(dates[j], rolling[j]) for j in range(len(rolling)) if rolling[j] is not None]
        if not valid_pairs:
            continue
        vd = [p[0] for p in valid_pairs]
        vv = [p[1] for p in valid_pairs]
        fig.add_trace(go.Scatter(
            x=vd, y=vv, mode="lines", name=sym,
            line={"color": COLORS["assets"][i % len(COLORS["assets"])], "width": 1.5},
            hovertemplate=f"<b>{sym}</b><br>%{{x}}<br>Vol: %{{y:.2%}}<extra></extra>",
        ))

    styled_layout(
        fig,
        title=f"Rolling {window}-Day Annualized Volatility",
        xaxis_title="Date",
        yaxis_title="Ann. Volatility",
        yaxis={"tickformat": ".0%", "gridcolor": "rgba(128,128,128,0.15)"},
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_skew_kurt_table(
    returns_data: dict[str, Any],
    mean_ret_data: dict[str, Any] | None = None,
    vol_data: dict[str, Any] | None = None,
) -> None:
    """Skewness / Kurtosis / VaR table per symbol."""
    symbols = returns_data.get("symbols", [])
    values = returns_data.get("values", [])
    if not symbols or not values:
        return

    mean_ret_map: dict[str, float] = {}
    vol_map: dict[str, float] = {}
    if mean_ret_data and mean_ret_data.get("symbols"):
        for s, v in zip(mean_ret_data["symbols"], mean_ret_data.get("values", [])):
            mean_ret_map[s] = v
    if vol_data and vol_data.get("symbols"):
        for s, v in zip(vol_data["symbols"], vol_data.get("values", [])):
            vol_map[s] = v

    rows = []
    for i, sym in enumerate(symbols):
        if i >= len(values):
            break
        rets = values[i]
        skew = _compute_skewness(rets)
        kurt = _compute_kurtosis(rets)
        var_95, cvar_95 = _compute_var_cvar(rets, confidence=0.95)
        rows.append({
            "Symbol": sym,
            "Ann. Return": fmt_pct(mean_ret_map.get(sym)),
            "Ann. Volatility": fmt_pct(vol_map.get(sym)),
            "Skewness": f"{skew:.3f}",
            "Excess Kurtosis": f"{kurt:.3f}",
            "VaR 95% (daily)": fmt_pct(var_95),
            "CVaR 95% (daily)": fmt_pct(cvar_95),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    render_csv_export(df, "tail_risk_stats.csv")


def render_beta_chart(returns_data: dict[str, Any]) -> None:
    """Beta vs BTC bar chart for each symbol."""
    symbols = returns_data.get("symbols", [])
    values = returns_data.get("values", [])
    if not symbols or not values:
        return

    btc_idx = next((i for i, s in enumerate(symbols) if "BTC" in s.upper()), None)
    if btc_idx is None:
        st.info("BTC not in symbol list — cannot compute beta")
        return

    btc_returns = values[btc_idx]
    betas = []
    for i in range(len(symbols)):
        if i == btc_idx:
            betas.append(1.0)
        else:
            betas.append(_compute_beta(values[i], btc_returns))

    pairs = sorted(zip(symbols, betas), key=lambda x: x[1], reverse=True)
    sorted_sym = [p[0] for p in pairs]
    sorted_beta = [p[1] for p in pairs]
    colors = [COLORS["danger"] if b > 1.0 else COLORS["strategy"] for b in sorted_beta]

    fig = go.Figure(go.Bar(
        x=sorted_beta, y=sorted_sym, orientation="h",
        marker_color=colors,
        text=[f"{b:.2f}" for b in sorted_beta],
        textposition="auto",
    ))
    fig.add_vline(x=1.0, line_dash="dash", line_color="gray", opacity=0.6,
                  annotation_text="β=1 (market)")
    styled_layout(
        fig,
        title="Beta vs BTC (crypto market proxy)",
        xaxis_title="Beta",
        xaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        height=max(300, len(symbols) * 40 + 100),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_var_cvar_chart(returns_data: dict[str, Any]) -> None:
    """VaR and CVaR 95% per symbol, horizontal bar chart."""
    symbols = returns_data.get("symbols", [])
    values = returns_data.get("values", [])
    if not symbols or not values:
        return

    var_vals = []
    cvar_vals = []
    for i in range(len(symbols)):
        if i >= len(values):
            break
        var, cvar = _compute_var_cvar(values[i], confidence=0.95)
        var_vals.append(var)
        cvar_vals.append(cvar)

    pairs = sorted(zip(symbols, var_vals, cvar_vals), key=lambda x: x[1])
    s_syms = [p[0] for p in pairs]
    s_var = [p[1] for p in pairs]
    s_cvar = [p[2] for p in pairs]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=s_var, y=s_syms, orientation="h",
        name="VaR 95%", marker_color=COLORS["danger"], opacity=0.7,
    ))
    fig.add_trace(go.Bar(
        x=s_cvar, y=s_syms, orientation="h",
        name="CVaR 95%", marker_color="darkred", opacity=0.7,
    ))
    styled_layout(
        fig,
        title="Daily VaR & CVaR at 95% Confidence",
        xaxis_title="Daily Return",
        xaxis={"tickformat": ".2%", "gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        barmode="overlay",
        height=max(300, len(symbols) * 40 + 100),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_correlation_network(
    symbols: list[str],
    corr_matrix: list[list[float]],
) -> None:
    """Nodes = symbols in a circle, edges = correlation strength."""
    n = len(symbols)
    if n < 2:
        return

    angles = [2 * math.pi * i / n for i in range(n)]
    x_nodes = [math.cos(a) for a in angles]
    y_nodes = [math.sin(a) for a in angles]

    fig = go.Figure()

    threshold = 0.3
    for i in range(n):
        for j in range(i + 1, n):
            if i >= len(corr_matrix) or j >= len(corr_matrix[i]):
                continue
            corr = corr_matrix[i][j]
            if abs(corr) < threshold:
                continue
            opacity = min(abs(corr), 1.0)
            width = abs(corr) * 6
            color = (
                f"rgba(31,119,180,{opacity:.2f})"
                if corr > 0
                else f"rgba(214,39,40,{opacity:.2f})"
            )
            fig.add_trace(go.Scatter(
                x=[x_nodes[i], x_nodes[j], None],
                y=[y_nodes[i], y_nodes[j], None],
                mode="lines",
                line={"width": width, "color": color},
                showlegend=False,
                hoverinfo="skip",
            ))

    fig.add_trace(go.Scatter(
        x=x_nodes,
        y=y_nodes,
        mode="markers+text",
        text=symbols,
        textposition="top center",
        marker={
            "size": 20,
            "color": [COLORS["assets"][i % len(COLORS["assets"])] for i in range(n)],
            "line": {"width": 1.5, "color": "white"},
        },
        hovertemplate="%{text}<extra></extra>",
        showlegend=False,
    ))

    styled_layout(
        fig,
        title="Correlation Network (blue = positive, red = negative, |ρ| > 0.3)",
        xaxis={"showgrid": False, "zeroline": False, "showticklabels": False, "range": [-1.5, 1.5]},
        yaxis={"showgrid": False, "zeroline": False, "showticklabels": False, "range": [-1.5, 1.5]},
        height=520,
    )
    st.plotly_chart(fig, use_container_width=True)


def page_risk() -> None:
    """Render the Risk Analysis page."""
    mode_label = "Traditional" if _is_trad_mode() else "Crypto"
    st.title(f"Risk Analysis — {mode_label}")
    st.caption("Tail risk, volatility regimes, beta sensitivity, and correlation structure.")

    returns_resp = fetch_api(_metric_endpoint("returns"))
    mean_ret_resp = fetch_api(_metric_endpoint("mean_returns"))
    vol_resp = fetch_api(_metric_endpoint("volatility"))
    corr_resp = fetch_api(_metric_endpoint("correlation"))

    returns_data = returns_resp.get("data") if returns_resp else None
    mean_ret_data = mean_ret_resp.get("data") if mean_ret_resp else None
    vol_data = vol_resp.get("data") if vol_resp else None
    corr_data = corr_resp.get("data") if corr_resp else None

    if not returns_data:
        st.warning("No returns data. Run the pipeline first.")
        return

    st.subheader("Rolling Volatility")
    render_rolling_vol_chart(returns_data)
    st.markdown("---")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Beta vs BTC")
        render_beta_chart(returns_data)
    with col2:
        st.subheader("Tail Risk Statistics")
        render_skew_kurt_table(returns_data, mean_ret_data, vol_data)

    st.markdown("---")
    st.subheader("VaR & CVaR per Symbol (95%)")
    render_var_cvar_chart(returns_data)
    st.markdown("---")

    st.subheader("Correlation Network")
    if corr_data:
        render_correlation_network(
            corr_data.get("symbols", []),
            corr_data.get("matrix", []),
        )
    else:
        st.info("No correlation data available")


# =============================================================================
# Backtest Page
# =============================================================================


def _compute_drawdown_series(values: list[float]) -> list[float]:
    """Compute drawdown series from cumulative values."""
    peak = values[0] if values else 1.0
    drawdowns = []
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        drawdowns.append(-dd)
    return drawdowns


def render_weights_evolution(windows: list[dict[str, Any]], symbols: list[str]) -> None:
    """Stacked area chart of portfolio weights across rolling windows."""
    if not windows:
        return

    labels = []
    weight_data: dict[str, list[float]] = {s: [] for s in symbols}

    for w in windows:
        labels.append(w.get("test_start", f"W{w.get('window_id', '?')}"))
        weights = w.get("weights", {})
        for s in symbols:
            weight_data[s].append(weights.get(s, 0.0))

    fig = go.Figure()
    for i, s in enumerate(symbols):
        fig.add_trace(go.Scatter(
            x=labels, y=weight_data[s],
            mode="lines", stackgroup="one", name=s,
            line={"color": COLORS["assets"][i % len(COLORS["assets"])]},
        ))

    styled_layout(
        fig,
        title="Portfolio Weights Evolution",
        xaxis_title="Window Start",
        yaxis_title="Weight",
        yaxis={"tickformat": ".0%", "gridcolor": "rgba(128,128,128,0.15)"},
        xaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_return_distribution(cumulative_values: dict[str, Any]) -> None:
    """Histogram of daily simple returns with VaR and CVaR lines."""
    strategy_vals = cumulative_values.get("strategy", [])
    if len(strategy_vals) < 3:
        return

    # Daily simple returns (not log returns)
    daily_returns = [
        (strategy_vals[i] / strategy_vals[i - 1]) - 1.0
        for i in range(1, len(strategy_vals))
        if strategy_vals[i - 1] > 0
    ]

    if len(daily_returns) < 5:
        return

    sorted_returns = sorted(daily_returns)
    n = len(sorted_returns)
    var_idx = max(0, int(n * 0.05) - 1)
    var_95 = sorted_returns[var_idx]
    tail = sorted_returns[:var_idx + 1]
    cvar_95 = sum(tail) / len(tail) if tail else var_95

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=daily_returns, nbinsx=40,
        name="Daily Returns",
        marker_color=COLORS["equal"], opacity=0.75,
    ))
    fig.add_vline(x=var_95, line_dash="dash", line_color="red",
                  annotation_text=f"VaR 95%: {var_95:.2%}")
    fig.add_vline(x=cvar_95, line_dash="dot", line_color="darkred",
                  annotation_text=f"CVaR 95%: {cvar_95:.2%}")

    styled_layout(
        fig,
        title="Strategy Daily Return Distribution",
        xaxis_title="Daily Return",
        yaxis_title="Frequency",
        xaxis={"tickformat": ".1%", "gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"gridcolor": "rgba(128,128,128,0.15)"},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_rolling_sharpe(
    daily_returns: dict[str, Any],
    dates: list[str],
    risk_free_rate: float = 0.05,
    window: int = 30,
) -> None:
    """Rolling Sharpe ratio chart for all strategies."""
    daily_rf = risk_free_rate / 365

    fig = go.Figure()
    labels = _strategy_labels()
    colors = _strategy_colors()
    for key, label in labels.items():
        returns = daily_returns.get(key, [])
        if len(returns) < window:
            continue

        rolling_sharpe = []
        rolling_dates = []
        for i in range(window, len(returns)):
            win_returns = returns[i - window:i]
            mean_r = sum(win_returns) / len(win_returns)
            var_r = sum((r - mean_r) ** 2 for r in win_returns) / len(win_returns)
            std_r = var_r ** 0.5
            sharpe = (
                (mean_r - daily_rf) / std_r * math.sqrt(365)
                if std_r > 1e-10 else 0.0
            )
            rolling_sharpe.append(sharpe)
            rolling_dates.append(dates[i] if i < len(dates) else str(i))

        fig.add_trace(go.Scatter(
            x=rolling_dates, y=rolling_sharpe,
            mode="lines", name=label,
            line={"color": colors[key], "width": 2},
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    styled_layout(
        fig,
        title=f"Rolling Sharpe Ratio ({window}-day window)",
        xaxis_title="Date", yaxis_title="Sharpe Ratio",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_performance_comparison(metrics: dict[str, Any]) -> None:
    """Grouped bar chart comparing all strategies across metrics."""
    metric_keys = ["cumulative_return", "annualized_return", "sharpe_ratio", "sortino_ratio", "calmar_ratio"]
    display_names = ["Cumulative", "Annualized", "Sharpe", "Sortino", "Calmar"]

    labels = _strategy_labels()
    colors = _strategy_colors()
    fig = go.Figure()
    for key, label in labels.items():
        strat_metrics = metrics.get(key, {})
        values = [strat_metrics.get(k, 0) for k in metric_keys]
        fig.add_trace(go.Bar(
            name=label, x=display_names, y=values,
            marker_color=colors[key], opacity=0.85,
        ))

    styled_layout(
        fig,
        title="Strategy Comparison",
        barmode="group",
        yaxis_title="Value",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_backtest_monthly_heatmap(
    daily_returns: dict[str, Any], dates: list[str],
) -> None:
    """Monthly returns heatmap for all backtest strategies."""
    if not dates or not daily_returns:
        return

    strat_labels = _strategy_labels()
    strategies = list(strat_labels.keys())
    labels = list(strat_labels.values())

    month_data: dict[str, dict[str, float]] = {}
    for day_idx, date_str in enumerate(dates):
        month_key = date_str[:7]
        if month_key not in month_data:
            month_data[month_key] = {s: 0.0 for s in strategies}
        for s in strategies:
            rets = daily_returns.get(s, [])
            if day_idx < len(rets):
                month_data[month_key][s] += rets[day_idx]

    if not month_data:
        return

    months = sorted(month_data.keys())
    z = [[month_data[m][s] for s in strategies] for m in months]

    fig = px.imshow(
        z, x=labels, y=months,
        text_auto=".1%", aspect="auto",
        color_continuous_scale="RdYlGn",
    )
    styled_layout(fig, title="Monthly Returns by Strategy",
                  height=max(300, len(months) * 28 + 100))
    st.plotly_chart(fig, use_container_width=True)


def _fmt_metric(name: str, value: Any) -> str:
    """Format a backtest metric as % or ratio based on its name."""
    if value is None:
        return "N/A"
    pct_metrics = {"cumulative_return", "annualized_return", "max_drawdown"}
    try:
        v = float(value)
        return f"{v:.2%}" if name in pct_metrics else f"{v:.2f}"
    except (TypeError, ValueError):
        return str(value)


def render_win_rate(windows: list[dict[str, Any]]) -> None:
    """Win/loss bar per window + overall win rate KPI."""
    if not windows:
        return

    labels = []
    results = []
    for w in windows:
        wid = w.get("window_id", "?")
        test_ret = w.get("test_return")
        eq_ret = w.get("equal_weight_test_return")
        if test_ret is not None and eq_ret is not None:
            labels.append(f"W{wid}")
            results.append(1 if test_ret > eq_ret else 0)

    if not results:
        st.info("Per-window equal weight returns not available in backtest data")
        return

    win_rate = sum(results) / len(results)
    st.metric("Win Rate vs Equal Weight", f"{win_rate:.0%}",
              help="% of rolling windows where optimized strategy beat equal weight")

    colors = [COLORS["strategy"] if r == 1 else COLORS["danger"] for r in results]
    fig = go.Figure(go.Bar(
        x=labels, y=results,
        marker_color=colors,
        text=["Win" if r == 1 else "Loss" for r in results],
        textposition="auto",
    ))
    styled_layout(
        fig,
        title="Strategy vs Equal Weight per Window",
        yaxis={"tickvals": [0, 1], "ticktext": ["Loss", "Win"],
               "gridcolor": "rgba(128,128,128,0.15)"},
        xaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        height=300,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_contribution_chart(
    windows: list[dict[str, Any]], symbols: list[str],
) -> None:
    """Stacked bar chart: per-symbol return contribution per window."""
    if not windows or not symbols:
        return

    window_labels = []
    contributions: dict[str, list[float]] = {s: [] for s in symbols}

    for w in windows:
        weights = w.get("weights", {})
        test_ret = w.get("test_return", 0.0) or 0.0
        if not weights:
            continue
        window_labels.append(f"W{w.get('window_id', '?')}")
        total_w = sum(weights.values()) or 1.0
        for s in symbols:
            w_s = weights.get(s, 0.0)
            contributions[s].append((w_s / total_w) * test_ret)

    if not window_labels:
        return

    fig = go.Figure()
    for i, s in enumerate(symbols):
        fig.add_trace(go.Bar(
            name=s,
            x=window_labels,
            y=contributions[s],
            marker_color=COLORS["assets"][i % len(COLORS["assets"])],
        ))

    styled_layout(
        fig,
        title="Per-Symbol Return Contribution by Window",
        barmode="stack",
        xaxis_title="Window",
        yaxis_title="Contribution",
        yaxis={"tickformat": ".2%", "gridcolor": "rgba(128,128,128,0.15)"},
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def page_backtest() -> None:
    """Render the Backtest page."""
    mode_label = "Traditional" if _is_trad_mode() else "Crypto"
    st.title(f"Portfolio Backtest — {mode_label}")

    bt_data = fetch_api(_backtest_endpoint())
    if not bt_data:
        st.warning(
            "No backtest data available. Run: "
            "`python -c \"from src.pipeline.backtest import run_backtest; run_backtest()\"`"
        )
        return

    config = bt_data.get("config", {})
    metrics = bt_data.get("metrics", {})
    cum_vals = bt_data.get("cumulative_values", {})
    daily_rets = bt_data.get("daily_returns", {})
    windows = bt_data.get("windows", [])
    bt_symbols = bt_data.get("symbols", [])
    cum_dates = cum_vals.get("dates", [])
    rf = config.get("risk_free_rate", 0.05)

    st.info(
        f"Strategy: **{config.get('strategy', 'N/A')}** | "
        f"Train: **{config.get('train_window', 'N/A')}** days | "
        f"Test: **{config.get('test_window', 'N/A')}** days | "
        f"Risk-free: **{rf:.1%}**"
    )

    bt_labels = _strategy_labels()
    bt_colors = _strategy_colors()

    if cum_dates:
        fig_cum = go.Figure()
        for key, label in bt_labels.items():
            vals = cum_vals.get(key, [])
            if vals:
                fig_cum.add_trace(go.Scatter(
                    x=cum_dates,
                    y=vals[1:len(cum_dates) + 1],
                    mode="lines", name=label,
                    line={"color": bt_colors[key], "width": 2},
                ))
        styled_layout(
            fig_cum,
            title="Cumulative Portfolio Value",
            xaxis_title="Date",
            yaxis_title="Portfolio Value (starting at 1.0)",
            hovermode="x unified",
        )
        st.plotly_chart(fig_cum, use_container_width=True)

    st.markdown("---")
    st.subheader("Performance Metrics")
    metric_names = ["cumulative_return", "annualized_return", "max_drawdown",
                    "sharpe_ratio", "sortino_ratio", "calmar_ratio"]
    display_names = ["Cumulative Return", "Annualized Return", "Max Drawdown",
                     "Sharpe Ratio", "Sortino Ratio", "Calmar Ratio"]
    bench_key = "spy_only" if _is_trad_mode() else "btc_only"
    bench_label = "SPY Only" if _is_trad_mode() else "BTC Only"
    rows = []
    for mname, dname in zip(metric_names, display_names):
        rows.append({
            "Metric": dname,
            "Optimized": _fmt_metric(mname, metrics.get("strategy", {}).get(mname)),
            "Equal Weight": _fmt_metric(mname, metrics.get("equal_weight", {}).get(mname)),
            bench_label: _fmt_metric(mname, metrics.get(bench_key, {}).get(mname)),
        })
    df_metrics = pd.DataFrame(rows)
    st.dataframe(df_metrics, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Drawdown Comparison")
    if cum_dates:
        fig_dd = go.Figure()
        for key, label in bt_labels.items():
            vals = cum_vals.get(key, [])
            if vals:
                trimmed = vals[1:len(cum_dates) + 1]
                dd_series = _compute_drawdown_series(trimmed)
                fig_dd.add_trace(go.Scatter(
                    x=cum_dates, y=dd_series,
                    mode="lines", name=label,
                    line={"color": bt_colors[key], "width": 1.5},
                    fill="tozeroy" if key == "strategy" else None,
                    fillcolor="rgba(44,160,44,0.15)" if key == "strategy" else None,
                ))
        styled_layout(
            fig_dd,
            title="Drawdown by Strategy",
            xaxis_title="Date", yaxis_title="Drawdown",
            yaxis={"tickformat": ".1%", "gridcolor": "rgba(128,128,128,0.15)"},
            xaxis={"gridcolor": "rgba(128,128,128,0.15)"},
            hovermode="x unified",
        )
        st.plotly_chart(fig_dd, use_container_width=True)

    st.markdown("---")
    st.subheader("Monthly Returns")
    if daily_rets and cum_dates:
        render_backtest_monthly_heatmap(daily_rets, cum_dates)

    st.markdown("---")
    st.subheader("Win Rate vs Equal Weight")
    render_win_rate(windows)

    st.markdown("---")
    st.subheader("Per-Symbol Return Contribution")
    render_contribution_chart(windows, bt_symbols)

    st.markdown("---")
    st.subheader("Weights Evolution")
    render_weights_evolution(windows, bt_symbols)

    st.markdown("---")
    st.subheader("Rolling Sharpe Ratio")
    if daily_rets:
        render_rolling_sharpe(daily_rets, cum_dates, risk_free_rate=rf)
    else:
        st.info("Daily returns not available. Re-run backtest to enable rolling Sharpe.")

    st.markdown("---")
    st.subheader("Strategy Comparison")
    render_performance_comparison(metrics)

    st.markdown("---")
    st.subheader("Return Distribution")
    render_return_distribution(cum_vals)

    st.markdown("---")
    st.subheader("Window Details")
    if windows:
        for w in windows:
            wid = w.get("window_id", "?")
            with st.expander(
                f"Window {wid}: {w.get('train_start', '?')} → {w.get('test_end', '?')}"
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**Train**: {w.get('train_start', '?')} to {w.get('train_end', '?')}")
                with col2:
                    st.markdown(f"**Test**: {w.get('test_start', '?')} to {w.get('test_end', '?')}")
                with col3:
                    test_ret = w.get("test_return")
                    st.markdown(f"**Test Return**: {fmt_pct(test_ret)}")
                weights = w.get("weights", {})
                if weights:
                    sorted_w = sorted(weights.items(), key=lambda x: x[1], reverse=True)
                    df_ww = pd.DataFrame(sorted_w, columns=["Symbol", "Weight"])
                    df_ww["Weight"] = df_ww["Weight"].apply(lambda x: f"{x:.2%}")
                    st.dataframe(df_ww, use_container_width=True, hide_index=True)

    st.markdown("---")
    render_csv_export(df_metrics, "backtest_metrics.csv", "Export metrics CSV")


# =============================================================================
# Main
# =============================================================================


def _render_sidebar_data_range() -> None:
    """Show the date range of loaded data below API status."""
    returns_resp = fetch_api(_metric_endpoint("returns"))
    if returns_resp and returns_resp.get("data"):
        dates = returns_resp["data"].get("dates", [])
        if dates:
            st.sidebar.caption(f"Data: {dates[0]} → {dates[-1]}")


def _render_sidebar_last_updated() -> None:
    """Show when portfolio data was last computed."""
    try:
        weights_file = "weights_trad.json" if _is_trad_mode() else "weights.json"
        path = os.path.join("data", "output", weights_file)
        if os.path.exists(path):
            import json
            with open(path) as f:
                data = json.load(f)
            saved_at = data.get("_metadata", {}).get("saved_at", "")
            if saved_at:
                st.sidebar.caption(f"Last updated: {saved_at[:19]}")
    except Exception:
        pass


def main() -> None:
    """Main dashboard entry point."""
    st.set_page_config(
        page_title="Portfolio Dashboard",
        page_icon="📈",
        layout="wide",
    )

    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Page",
        ["Dashboard", "Symbols", "Metrics", "Risk Analysis", "Frontier", "Backtest"],
    )

    st.sidebar.markdown("---")
    st.sidebar.radio(
        "Portfolio",
        ["Crypto", "Traditional"],
        key="portfolio_mode",
        horizontal=True,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**API Status**")
    health = fetch_api("/")
    if health and health.get("status") == "ok":
        st.sidebar.success("Connected")
    else:
        st.sidebar.error("Disconnected")

    _render_sidebar_data_range()
    _render_sidebar_last_updated()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

    auto_refresh = st.sidebar.toggle("Auto-refresh (30s)", value=False)

    if page == "Dashboard":
        page_dashboard()
    elif page == "Symbols":
        page_symbols()
    elif page == "Metrics":
        page_metrics()
    elif page == "Risk Analysis":
        page_risk()
    elif page == "Frontier":
        page_frontier()
    elif page == "Backtest":
        page_backtest()

    if auto_refresh:
        time.sleep(30)
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
