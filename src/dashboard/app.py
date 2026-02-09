"""
Streamlit dashboard for portfolio optimization visualization.

Connects to FastAPI backend to display:
- KPI cards (expected return, volatility, Sharpe ratio)
- Portfolio allocation pie chart
- Price charts per symbol
- Correlation heatmap
"""

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")


def fetch_api(endpoint: str) -> dict | None:
    """Fetch data from API endpoint."""
    try:
        response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        response.raise_for_status()
        data: dict = response.json()
        return data
    except requests.RequestException as e:
        st.error(f"API Error: {e}")
        return None


def render_kpi_cards(portfolio: dict) -> None:
    """Render KPI metric cards."""
    col1, col2, col3 = st.columns(3)

    expected_return = portfolio.get("expected_return", 0)
    volatility = portfolio.get("volatility", 0)
    sharpe_ratio = portfolio.get("sharpe_ratio", 0)

    with col1:
        st.metric(
            label="Expected Return",
            value=f"{expected_return:.2%}" if expected_return else "N/A",
        )

    with col2:
        st.metric(
            label="Volatility",
            value=f"{volatility:.2%}" if volatility else "N/A",
        )

    with col3:
        st.metric(
            label="Sharpe Ratio",
            value=f"{sharpe_ratio:.2f}" if sharpe_ratio else "N/A",
        )


def render_allocation_chart(weights: dict) -> None:
    """Render portfolio allocation pie chart."""
    if not weights:
        st.warning("No allocation data available")
        return

    df = pd.DataFrame(
        {"Symbol": list(weights.keys()), "Weight": list(weights.values())}
    )

    fig = px.pie(
        df,
        values="Weight",
        names="Symbol",
        title="Portfolio Allocation",
        hole=0.4,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)


def render_price_chart(symbol: str) -> None:
    """Render OHLCV price chart for a symbol."""
    data = fetch_api(f"/klines/{symbol}")
    if not data or "data" not in data:
        st.warning(f"No price data for {symbol}")
        return

    klines = data["data"]
    if not klines:
        st.warning(f"Empty price data for {symbol}")
        return

    df = pd.DataFrame(klines)

    if "open_time" in df.columns:
        df["date"] = pd.to_datetime(df["open_time"], unit="ms")
    elif "timestamp" in df.columns:
        df["date"] = pd.to_datetime(df["timestamp"])
    else:
        df["date"] = range(len(df))

    fig = go.Figure()

    if "close" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["close"],
                mode="lines",
                name="Close Price",
                line={"color": "#1f77b4"},
            )
        )

    fig.update_layout(
        title=f"{symbol} Price History",
        xaxis_title="Date",
        yaxis_title="Price (USDT)",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_correlation_heatmap() -> None:
    """Render correlation matrix heatmap."""
    data = fetch_api("/metrics/correlation")
    if not data or "data" not in data:
        st.warning("No correlation data available")
        return

    corr_data = data["data"]
    if not corr_data:
        st.warning("Empty correlation data")
        return

    df = pd.DataFrame(corr_data)

    fig = px.imshow(
        df,
        text_auto=".2f",
        aspect="auto",
        title="Correlation Matrix",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
    )

    fig.update_layout(
        xaxis_title="Symbol",
        yaxis_title="Symbol",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_volatility_chart() -> None:
    """Render volatility comparison bar chart."""
    data = fetch_api("/metrics/volatility")
    if not data or "data" not in data:
        st.warning("No volatility data available")
        return

    vol_data = data["data"]
    if not vol_data:
        st.warning("Empty volatility data")
        return

    if isinstance(vol_data, dict):
        df = pd.DataFrame(
            {"Symbol": list(vol_data.keys()), "Volatility": list(vol_data.values())}
        )
    else:
        df = pd.DataFrame(vol_data)

    fig = px.bar(
        df,
        x="Symbol",
        y="Volatility",
        title="Volatility by Symbol",
        color="Volatility",
        color_continuous_scale="Viridis",
    )

    st.plotly_chart(fig, use_container_width=True)


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
        st.title("Portfolio Optimization Dashboard")

        portfolio = fetch_api("/portfolio")
        if portfolio:
            render_kpi_cards(portfolio)

            st.markdown("---")

            col1, col2 = st.columns(2)
            with col1:
                weights = portfolio.get("weights", {})
                render_allocation_chart(weights)

            with col2:
                render_volatility_chart()

            st.markdown("---")
            render_correlation_heatmap()

        else:
            st.warning(
                "No portfolio data available. Run the pipeline first: "
                "`docker compose --profile pipeline up pipeline`"
            )

    elif page == "Symbols":
        st.title("Symbol Analysis")

        symbols_data = fetch_api("/symbols")
        if symbols_data and symbols_data.get("symbols"):
            symbols = symbols_data["symbols"]

            selected_symbol = st.selectbox("Select Symbol", symbols)

            if selected_symbol:
                render_price_chart(selected_symbol)

                st.markdown("---")

                klines_data = fetch_api(f"/klines/{selected_symbol}")
                if klines_data and klines_data.get("data"):
                    st.subheader("Raw Data")
                    df = pd.DataFrame(klines_data["data"])
                    st.dataframe(df.head(20), use_container_width=True)
        else:
            st.warning("No symbols available")

    elif page == "Metrics":
        st.title("Metrics Explorer")

        metrics_data = fetch_api("/metrics")
        if metrics_data and metrics_data.get("metrics"):
            metrics = metrics_data["metrics"]

            selected_metric = st.selectbox("Select Metric", metrics)

            if selected_metric:
                metric_data = fetch_api(f"/metrics/{selected_metric}")
                if metric_data and metric_data.get("data"):
                    st.subheader(f"{selected_metric.title()}")

                    data = metric_data["data"]
                    if isinstance(data, dict):
                        df = pd.DataFrame(data)
                    else:
                        df = pd.DataFrame(data)

                    st.dataframe(df, use_container_width=True)

                    if selected_metric == "correlation":
                        render_correlation_heatmap()
                    elif selected_metric == "volatility":
                        render_volatility_chart()
        else:
            st.warning("No metrics available")

    elif page == "Frontier":
        st.title("Efficient Frontier")

        frontier_data = fetch_api("/portfolio/frontier")
        if frontier_data:
            symbols = frontier_data.get("symbols", [])
            frontier = frontier_data.get("frontier", [])
            max_sharpe = frontier_data.get("max_sharpe", {})
            min_var = frontier_data.get("min_variance", {})
            assets = frontier_data.get("assets", [])
            cml = frontier_data.get("capital_market_line", {})
            rf = frontier_data.get("risk_free_rate", 0.05)

            fig = go.Figure()

            # Frontier curve
            if frontier:
                fig.add_trace(go.Scatter(
                    x=[p["volatility"] for p in frontier],
                    y=[p["return"] for p in frontier],
                    mode="lines",
                    name="Efficient Frontier",
                    line={"color": "#1f77b4", "width": 3},
                ))

            # Individual assets
            if assets:
                asset_labels = [
                    symbols[a["symbol_index"]] if a["symbol_index"] < len(symbols) else f"Asset {a['symbol_index']}"
                    for a in assets
                ]
                fig.add_trace(go.Scatter(
                    x=[a["volatility"] for a in assets],
                    y=[a["return"] for a in assets],
                    mode="markers+text",
                    name="Individual Assets",
                    marker={"symbol": "diamond", "size": 12, "color": "#d62728"},
                    text=asset_labels,
                    textposition="top center",
                ))

            # Max Sharpe point
            if max_sharpe:
                fig.add_trace(go.Scatter(
                    x=[max_sharpe["volatility"]],
                    y=[max_sharpe["return"]],
                    mode="markers",
                    name="Max Sharpe",
                    marker={"symbol": "star", "size": 18, "color": "#2ca02c"},
                ))

            # Min Variance point
            if min_var:
                fig.add_trace(go.Scatter(
                    x=[min_var["volatility"]],
                    y=[min_var["return"]],
                    mode="markers",
                    name="Min Variance",
                    marker={"symbol": "square", "size": 14, "color": "#ff7f0e"},
                ))

            # Capital Market Line
            if cml and cml.get("x") and cml.get("y"):
                fig.add_trace(go.Scatter(
                    x=cml["x"],
                    y=cml["y"],
                    mode="lines",
                    name=f"CML (Rf={rf:.1%})",
                    line={"color": "gray", "dash": "dash", "width": 1},
                ))

            fig.update_layout(
                title="Efficient Frontier (Markowitz)",
                xaxis_title="Volatility (annualized)",
                yaxis_title="Expected Return (annualized)",
                hovermode="closest",
                xaxis={"tickformat": ".1%"},
                yaxis={"tickformat": ".1%"},
            )
            st.plotly_chart(fig, use_container_width=True)

            # Weights detail
            st.markdown("---")
            portfolio_type = st.selectbox(
                "View portfolio weights",
                ["Max Sharpe", "Min Variance"],
            )
            selected = max_sharpe if portfolio_type == "Max Sharpe" else min_var
            if selected and selected.get("weights"):
                weights_map = {
                    symbols[i]: round(selected["weights"][i], 4)
                    for i in range(min(len(symbols), len(selected["weights"])))
                }
                df_w = pd.DataFrame(
                    {"Symbol": list(weights_map.keys()), "Weight": list(weights_map.values())}
                )
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Expected Return", f"{selected['return']:.2%}")
                with col2:
                    st.metric("Volatility", f"{selected['volatility']:.2%}")
                st.dataframe(df_w, use_container_width=True)
        else:
            st.warning(
                "No frontier data available. Run: "
                "`python -c \"from src.pipeline.optimize import compute_and_save_frontier; compute_and_save_frontier()\"`"
            )

    elif page == "Backtest":
        st.title("Portfolio Backtest")

        bt_data = fetch_api("/portfolio/backtest")
        if bt_data:
            config = bt_data.get("config", {})
            metrics = bt_data.get("metrics", {})
            cum_vals = bt_data.get("cumulative_values", {})

            # Config banner
            st.info(
                f"Strategy: **{config.get('strategy', 'N/A')}** | "
                f"Train: **{config.get('train_window', 'N/A')}** days | "
                f"Test: **{config.get('test_window', 'N/A')}** days | "
                f"Risk-free: **{config.get('risk_free_rate', 0.05):.1%}**"
            )

            # Cumulative return chart
            cum_dates = cum_vals.get("dates", [])
            if cum_dates:
                fig_cum = go.Figure()

                strategy_vals = cum_vals.get("strategy", [])
                equal_vals = cum_vals.get("equal_weight", [])
                btc_vals = cum_vals.get("btc_only", [])

                # Values lists have len(dates)+1 points; trim to match dates
                if strategy_vals:
                    fig_cum.add_trace(go.Scatter(
                        x=cum_dates,
                        y=strategy_vals[1:len(cum_dates) + 1],
                        mode="lines",
                        name=f"Strategy ({config.get('strategy', '')})",
                        line={"color": "#2ca02c", "width": 2},
                    ))
                if equal_vals:
                    fig_cum.add_trace(go.Scatter(
                        x=cum_dates,
                        y=equal_vals[1:len(cum_dates) + 1],
                        mode="lines",
                        name="Equal Weight",
                        line={"color": "#1f77b4", "width": 2},
                    ))
                if btc_vals:
                    fig_cum.add_trace(go.Scatter(
                        x=cum_dates,
                        y=btc_vals[1:len(cum_dates) + 1],
                        mode="lines",
                        name="BTC Only",
                        line={"color": "#ff7f0e", "width": 2},
                    ))

                fig_cum.update_layout(
                    title="Cumulative Portfolio Value",
                    xaxis_title="Date",
                    yaxis_title="Portfolio Value (starting at 1.0)",
                    hovermode="x unified",
                )
                st.plotly_chart(fig_cum, use_container_width=True)

            # Metrics comparison table
            st.markdown("---")
            st.subheader("Performance Metrics")
            metric_names = ["cumulative_return", "annualized_return", "max_drawdown", "sharpe_ratio", "calmar_ratio"]
            display_names = ["Cumulative Return", "Annualized Return", "Max Drawdown", "Sharpe Ratio", "Calmar Ratio"]
            rows = []
            for mname, dname in zip(metric_names, display_names):
                rows.append({
                    "Metric": dname,
                    "Strategy": metrics.get("strategy", {}).get(mname, "N/A"),
                    "Equal Weight": metrics.get("equal_weight", {}).get(mname, "N/A"),
                    "BTC Only": metrics.get("btc_only", {}).get(mname, "N/A"),
                })
            df_metrics = pd.DataFrame(rows)
            st.dataframe(df_metrics, use_container_width=True)

            # Drawdown chart
            st.markdown("---")
            st.subheader("Drawdown")
            if cum_dates and strategy_vals:
                vals_series = strategy_vals[1:len(cum_dates) + 1]
                peak = vals_series[0] if vals_series else 1.0
                drawdowns = []
                for v in vals_series:
                    if v > peak:
                        peak = v
                    dd = (peak - v) / peak if peak > 0 else 0.0
                    drawdowns.append(-dd)

                fig_dd = go.Figure()
                fig_dd.add_trace(go.Scatter(
                    x=cum_dates,
                    y=drawdowns,
                    mode="lines",
                    fill="tozeroy",
                    name="Drawdown",
                    line={"color": "#d62728"},
                    fillcolor="rgba(214, 39, 40, 0.3)",
                ))
                fig_dd.update_layout(
                    title="Strategy Drawdown",
                    xaxis_title="Date",
                    yaxis_title="Drawdown",
                    yaxis={"tickformat": ".1%"},
                    hovermode="x unified",
                )
                st.plotly_chart(fig_dd, use_container_width=True)
        else:
            st.warning(
                "No backtest data available. Run: "
                "`python -c \"from src.pipeline.backtest import run_backtest; run_backtest()\"`"
            )


if __name__ == "__main__":
    main()
