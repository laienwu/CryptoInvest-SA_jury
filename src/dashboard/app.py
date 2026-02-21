"""
Streamlit dashboard for portfolio optimization visualization.

Connects to FastAPI backend to display:
- KPI cards (expected return, volatility, Sharpe ratio, Sortino, Max DD)
- Portfolio allocation donut chart + risk-return scatter
- Correlation & covariance heatmaps
- Monthly returns heatmap
- Technical price charts (SMA, Bollinger, RSI, volume)
- Efficient frontier with iso-Sharpe curves
- Walk-forward backtest analytics
"""

import math
import os
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


def fetch_api(endpoint: str) -> dict[str, Any] | None:
    """Fetch data from API endpoint."""
    try:
        response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data
    except requests.RequestException as e:
        st.error(f"API Error: {e}")
        return None


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
    """Render a calendar-grid monthly returns heatmap.

    Rows = year-month, columns = symbols. Color = total return for that month.
    """
    if not dates or not values or not symbols:
        return

    # Build month → symbol → cumulative return
    month_returns: dict[str, dict[str, float]] = {}
    for day_idx, date_str in enumerate(dates):
        month_key = date_str[:7]  # "YYYY-MM"
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
    """Render 5 KPI metric cards across the top row."""
    cols = st.columns(5)

    expected_return = portfolio.get("expected_return")
    volatility = portfolio.get("volatility")
    sharpe = portfolio.get("sharpe_ratio")

    sortino = None
    max_dd = None
    if backtest_metrics:
        strat = backtest_metrics.get("strategy", {})
        sortino = strat.get("sortino_ratio")
        max_dd = strat.get("max_drawdown")

    with cols[0]:
        st.metric("Expected Return", fmt_pct(expected_return))
    with cols[1]:
        st.metric("Volatility", fmt_pct(volatility))
    with cols[2]:
        st.metric("Sharpe Ratio", fmt_ratio(sharpe))
    with cols[3]:
        st.metric("Sortino Ratio", fmt_ratio(sortino))
    with cols[4]:
        st.metric("Max Drawdown", fmt_pct(max_dd))


def render_allocation_donut(weights: dict[str, float]) -> None:
    """Render portfolio allocation donut chart."""
    if not weights:
        st.warning("No allocation data available")
        return

    symbols = list(weights.keys())
    values = list(weights.values())

    fig = go.Figure(go.Pie(
        labels=symbols,
        values=values,
        hole=0.5,
        marker={"colors": COLORS["assets"][:len(symbols)]},
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="%{label}: %{value:.4f} (%{percent})<extra></extra>",
    ))
    styled_layout(fig, title="Portfolio Allocation", showlegend=False)
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
    # Scale bubble size: minimum visible size + proportional
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


def page_dashboard() -> None:
    """Render the main Dashboard page."""
    st.title("Portfolio Optimization Dashboard")

    portfolio = fetch_api("/portfolio")
    if not portfolio:
        st.warning(
            "No portfolio data available. Run the pipeline first: "
            "`docker compose --profile pipeline up pipeline`"
        )
        return

    # Fetch backtest for Sortino + Max DD KPIs
    bt_data = fetch_api("/portfolio/backtest")
    bt_metrics = bt_data.get("metrics") if bt_data else None

    # Row 1: KPIs
    render_kpi_cards(portfolio, bt_metrics)
    st.markdown("---")

    # Row 2: Allocation donut + Risk-return scatter
    col1, col2 = st.columns(2)
    with col1:
        render_allocation_donut(portfolio.get("weights", {}))

    with col2:
        mean_ret = fetch_api("/metrics/mean_returns")
        vol = fetch_api("/metrics/volatility")
        if mean_ret and vol and mean_ret.get("data") and vol.get("data"):
            render_risk_return_scatter(
                mean_ret["data"], vol["data"], portfolio.get("weights", {})
            )
        else:
            st.info("Run transform pipeline for risk-return scatter")

    st.markdown("---")

    # Row 3: Correlation + Covariance heatmaps
    col1, col2 = st.columns(2)
    with col1:
        corr = fetch_api("/metrics/correlation")
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
        cov = fetch_api("/metrics/covariance")
        if cov and cov.get("data"):
            cd = cov["data"]
            render_matrix_heatmap(
                cd.get("symbols", []),
                cd.get("matrix", []),
                "Covariance Matrix",
                color_scale="Viridis",
            )

    st.markdown("---")

    # Row 4: Monthly returns heatmap
    returns_resp = fetch_api("/metrics/returns")
    if returns_resp and returns_resp.get("data"):
        rd = returns_resp["data"]
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

    # Initial average gain/loss
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

    # Smoothed RSI
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

    # Price candlestick
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

    # SMA 20
    fig.add_trace(go.Scatter(
        x=dates, y=sma20, mode="lines", name="SMA 20",
        line={"color": "#e377c2", "width": 1, "dash": "dot"},
    ), row=1, col=1)

    # SMA 50
    fig.add_trace(go.Scatter(
        x=dates, y=sma50, mode="lines", name="SMA 50",
        line={"color": "#17becf", "width": 1, "dash": "dot"},
    ), row=1, col=1)

    # Bollinger Bands
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

    # Volume bars
    if "volume" in df.columns:
        vol_colors = [
            COLORS["strategy"] if c >= o else COLORS["danger"]
            for c, o in zip(df["close"], df["open"])
        ]
        fig.add_trace(go.Bar(
            x=dates, y=df["volume"], name="Volume",
            marker_color=vol_colors, opacity=0.6, showlegend=False,
        ), row=2, col=1)

        # Volume 20-day moving average
        vol_sma = _compute_sma(df["volume"].tolist(), 20)
        fig.add_trace(go.Scatter(
            x=dates, y=vol_sma, mode="lines", name="Vol SMA 20",
            line={"color": COLORS["btc"], "width": 1},
            showlegend=False,
        ), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(
        x=dates, y=rsi, mode="lines", name="RSI",
        line={"color": COLORS["accent"], "width": 1.5},
    ), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(214,39,40,0.5)",
                  row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(44,160,44,0.5)",
                  row=3, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(128,128,128,0.05)",
                  line_width=0, row=3, col=1)

    styled_layout(
        fig,
        height=700,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])

    st.plotly_chart(fig, use_container_width=True)


def render_symbol_stats(df: pd.DataFrame) -> None:
    """Render 4 summary stat cards for a symbol."""
    cols = st.columns(4)
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


def page_symbols() -> None:
    """Render the Symbols page."""
    st.title("Symbol Analysis")

    symbols_data = fetch_api("/symbols")
    if not symbols_data or not symbols_data.get("symbols"):
        st.warning("No symbols available")
        return

    symbols = symbols_data["symbols"]

    col_sym, col_chart = st.columns([2, 1])
    with col_sym:
        selected_symbol = st.selectbox("Select Symbol", symbols)
    with col_chart:
        chart_type = st.selectbox("Chart Type", ["technical", "candlestick", "line"])

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

    # Chart
    if chart_type == "technical":
        render_technical_chart(df)
    elif chart_type == "candlestick" and all(c in df.columns for c in ["open", "high", "low", "close"]):
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
        st.plotly_chart(fig, use_container_width=True)

    # Stats cards
    st.markdown("---")
    render_symbol_stats(df)

    # Raw data + CSV export
    st.markdown("---")
    st.subheader("Raw Data")
    st.dataframe(df.drop(columns=["date"], errors="ignore").head(20), use_container_width=True)
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
        # Cumulative return from log returns: exp(cumsum(r)) - 1
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

    # Sort by value descending
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

    # Fallback: show each key as a row to avoid unhashable type errors
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

    # Metric-specific visualization
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
    elif selected_metric == "covariance":
        render_matrix_heatmap(
            data.get("symbols", []), data.get("matrix", []),
            "Covariance Matrix", color_scale="Viridis",
        )

    # Risk-return summary table
    st.markdown("---")
    st.subheader("Risk-Return Summary")
    mean_ret = fetch_api("/metrics/mean_returns")
    vol = fetch_api("/metrics/volatility")
    if mean_ret and vol and mean_ret.get("data") and vol.get("data"):
        render_risk_return_table(mean_ret["data"], vol["data"])

    # Raw data table + CSV
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
    st.title("Efficient Frontier")

    frontier_data = fetch_api("/portfolio/frontier")
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

    # Iso-Sharpe curves (faint arcs)
    for sharpe_val in [0.5, 1.0, 1.5, 2.0]:
        iso_vol = [v / 100 for v in range(1, 101)]
        iso_ret = [rf + sharpe_val * v for v in iso_vol]
        fig.add_trace(go.Scatter(
            x=iso_vol, y=iso_ret, mode="lines",
            line={"color": "rgba(180,180,180,0.3)", "width": 1, "dash": "dot"},
            showlegend=False,
            hoverinfo="skip",
        ))
        # Label at the end of the arc
        fig.add_annotation(
            x=iso_vol[-1], y=iso_ret[-1],
            text=f"S={sharpe_val}",
            showarrow=False,
            font={"size": 9, "color": "rgba(150,150,150,0.6)"},
        )

    # Frontier curve
    if frontier:
        fig.add_trace(go.Scatter(
            x=[p["volatility"] for p in frontier],
            y=[p["return"] for p in frontier],
            mode="lines",
            name="Efficient Frontier",
            line={"color": COLORS["equal"], "width": 3},
        ))

    # Individual assets — text directly on markers
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

    # Max Sharpe
    if max_sharpe:
        fig.add_trace(go.Scatter(
            x=[max_sharpe["volatility"]], y=[max_sharpe["return"]],
            mode="markers",
            name=f"Max Sharpe ({max_sharpe.get('sharpe_ratio', 0):.2f})",
            marker={"symbol": "star", "size": 18, "color": COLORS["strategy"],
                    "line": {"width": 1, "color": "white"}},
        ))

    # Min Variance
    if min_var:
        fig.add_trace(go.Scatter(
            x=[min_var["volatility"]], y=[min_var["return"]],
            mode="markers",
            name="Min Variance",
            marker={"symbol": "square", "size": 14, "color": COLORS["btc"],
                    "line": {"width": 1, "color": "white"}},
        ))

    # Current portfolio
    current = fetch_api("/portfolio")
    if current and current.get("volatility") and current.get("expected_return"):
        fig.add_trace(go.Scatter(
            x=[current["volatility"]], y=[current["expected_return"]],
            mode="markers",
            name="Current Portfolio",
            marker={"symbol": "circle", "size": 14, "color": COLORS["accent"],
                    "line": {"width": 2, "color": "white"}},
        ))

    # Capital Market Line
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

    # Portfolio weights — horizontal bar chart
    st.markdown("---")
    portfolio_type = st.selectbox(
        "View portfolio weights",
        ["Max Sharpe", "Min Variance"],
    )
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

        # Sorted horizontal bar
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
    """Render stacked area chart of portfolio weights across rolling windows."""
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
        yaxis={"tickformat": ".0%", "range": [0, 1], "gridcolor": "rgba(128,128,128,0.15)"},
        xaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_return_distribution(cumulative_values: dict[str, Any]) -> None:
    """Render histogram of daily returns with VaR and CVaR lines."""
    strategy_vals = cumulative_values.get("strategy", [])
    if len(strategy_vals) < 3:
        return

    daily_returns = [
        math.log(strategy_vals[i] / strategy_vals[i - 1])
        for i in range(1, len(strategy_vals))
        if strategy_vals[i - 1] > 0
    ]

    if len(daily_returns) < 5:
        return

    sorted_returns = sorted(daily_returns)
    n = len(sorted_returns)
    var_idx = max(0, int(n * 0.05) - 1)
    var_95 = sorted_returns[var_idx]
    tail = sorted_returns[: var_idx + 1]
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
        xaxis_title="Daily Log Return",
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
    """Render rolling Sharpe ratio chart for all strategies."""
    daily_rf = risk_free_rate / 365

    fig = go.Figure()
    for key, label in STRATEGY_LABELS.items():
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
            line={"color": STRATEGY_COLORS[key], "width": 2},
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
    """Render grouped bar chart comparing all strategies across metrics."""
    metric_keys = ["cumulative_return", "annualized_return", "sharpe_ratio", "sortino_ratio", "calmar_ratio"]
    display_names = ["Cumulative", "Annualized", "Sharpe", "Sortino", "Calmar"]

    fig = go.Figure()
    for key, label in STRATEGY_LABELS.items():
        strat_metrics = metrics.get(key, {})
        values = [strat_metrics.get(k, 0) for k in metric_keys]
        fig.add_trace(go.Bar(
            name=label, x=display_names, y=values,
            marker_color=STRATEGY_COLORS[key], opacity=0.85,
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
    """Render monthly returns heatmap for backtest strategies."""
    if not dates or not daily_returns:
        return

    strategies = ["strategy", "equal_weight", "btc_only"]
    labels = [STRATEGY_LABELS[s] for s in strategies]

    # Aggregate daily returns by month per strategy
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


def page_backtest() -> None:
    """Render the Backtest page."""
    st.title("Portfolio Backtest")

    bt_data = fetch_api("/portfolio/backtest")
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

    # Config banner
    st.info(
        f"Strategy: **{config.get('strategy', 'N/A')}** | "
        f"Train: **{config.get('train_window', 'N/A')}** days | "
        f"Test: **{config.get('test_window', 'N/A')}** days | "
        f"Risk-free: **{rf:.1%}**"
    )

    # Cumulative return chart
    if cum_dates:
        fig_cum = go.Figure()
        for key, label in STRATEGY_LABELS.items():
            vals = cum_vals.get(key, [])
            if vals:
                fig_cum.add_trace(go.Scatter(
                    x=cum_dates,
                    y=vals[1:len(cum_dates) + 1],
                    mode="lines", name=label,
                    line={"color": STRATEGY_COLORS[key], "width": 2},
                ))

        styled_layout(
            fig_cum,
            title="Cumulative Portfolio Value",
            xaxis_title="Date",
            yaxis_title="Portfolio Value (starting at 1.0)",
            hovermode="x unified",
        )
        st.plotly_chart(fig_cum, use_container_width=True)

    # Metrics comparison table
    st.markdown("---")
    st.subheader("Performance Metrics")
    metric_names = ["cumulative_return", "annualized_return", "max_drawdown",
                    "sharpe_ratio", "sortino_ratio", "calmar_ratio"]
    display_names = ["Cumulative Return", "Annualized Return", "Max Drawdown",
                     "Sharpe Ratio", "Sortino Ratio", "Calmar Ratio"]
    rows = []
    for mname, dname in zip(metric_names, display_names):
        rows.append({
            "Metric": dname,
            "Optimized": metrics.get("strategy", {}).get(mname, "N/A"),
            "Equal Weight": metrics.get("equal_weight", {}).get(mname, "N/A"),
            "BTC Only": metrics.get("btc_only", {}).get(mname, "N/A"),
        })
    df_metrics = pd.DataFrame(rows)
    st.dataframe(df_metrics, use_container_width=True, hide_index=True)

    # Drawdown comparison — all 3 strategies overlaid
    st.markdown("---")
    st.subheader("Drawdown Comparison")
    if cum_dates:
        fig_dd = go.Figure()
        for key, label in STRATEGY_LABELS.items():
            vals = cum_vals.get(key, [])
            if vals:
                trimmed = vals[1:len(cum_dates) + 1]
                dd_series = _compute_drawdown_series(trimmed)
                fig_dd.add_trace(go.Scatter(
                    x=cum_dates, y=dd_series,
                    mode="lines", name=label,
                    line={"color": STRATEGY_COLORS[key], "width": 1.5},
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

    # Monthly returns heatmap
    st.markdown("---")
    st.subheader("Monthly Returns")
    if daily_rets and cum_dates:
        render_backtest_monthly_heatmap(daily_rets, cum_dates)

    # Weights evolution
    st.markdown("---")
    st.subheader("Weights Evolution")
    render_weights_evolution(windows, bt_symbols)

    # Rolling Sharpe
    st.markdown("---")
    st.subheader("Rolling Sharpe Ratio")
    if daily_rets:
        render_rolling_sharpe(daily_rets, cum_dates, risk_free_rate=rf)
    else:
        st.info("Daily returns not available. Re-run backtest to enable rolling Sharpe.")

    # Performance comparison bar chart
    st.markdown("---")
    st.subheader("Strategy Comparison")
    render_performance_comparison(metrics)

    # Return distribution with VaR/CVaR
    st.markdown("---")
    st.subheader("Return Distribution")
    render_return_distribution(cum_vals)

    # Per-window details
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

    # CSV export
    st.markdown("---")
    render_csv_export(df_metrics, "backtest_metrics.csv", "Export metrics CSV")


# =============================================================================
# Main
# =============================================================================


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
        ["Dashboard", "Symbols", "Metrics", "Frontier", "Backtest"],
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**API Status**")

    health = fetch_api("/")
    if health and health.get("status") == "ok":
        st.sidebar.success("Connected")
    else:
        st.sidebar.error("Disconnected")

    if page == "Dashboard":
        page_dashboard()
    elif page == "Symbols":
        page_symbols()
    elif page == "Metrics":
        page_metrics()
    elif page == "Frontier":
        page_frontier()
    elif page == "Backtest":
        page_backtest()


if __name__ == "__main__":
    main()
