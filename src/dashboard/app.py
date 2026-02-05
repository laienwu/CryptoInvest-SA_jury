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
        return response.json()
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


def main():
    """Main dashboard entry point."""
    st.set_page_config(
        page_title="Portfolio Dashboard",
        page_icon="📈",
        layout="wide",
    )

    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Page",
        ["Dashboard", "Symbols", "Metrics"],
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


if __name__ == "__main__":
    main()
