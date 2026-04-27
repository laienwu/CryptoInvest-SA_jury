"""
Streamlit dashboard for the automated trading bot — bot-ops surface only.

Sibling to ``src/dashboard/app.py`` (the analytics dashboard on :8501). This
app runs on a separate Streamlit instance (:8502 in docker-compose) so the
bot view can evolve and crash independently of the analytics view.

Pages:
- Trading Activity (live ledger snapshot — open positions, PnL, ticks).
- Theory vs Reality (optimizer allocation vs bot holdings — diagnostic).

Both page functions are imported from their existing modules; this file is
just the app shell (page config, sidebar nav, API status, refresh controls).
"""

from __future__ import annotations

import os
import time

import requests
import streamlit as st

from src.dashboard.comparison_page import page_comparison
from src.dashboard.trading_page import page_trading_activity


_API_URL = os.getenv("API_URL", "http://localhost:8000")

_PAGES = {
    "Trading Activity": page_trading_activity,
    "Theory vs Reality": page_comparison,
}


def _api_healthy() -> bool:
    try:
        resp = requests.get(f"{_API_URL}/", timeout=5)
        resp.raise_for_status()
        return bool(resp.json().get("status") == "ok")
    except requests.RequestException:
        return False


def main() -> None:
    st.set_page_config(
        page_title="Trading Bot Dashboard",
        page_icon="🤖",
        layout="wide",
    )

    if "trading_page" not in st.session_state:
        st.session_state.trading_page = next(iter(_PAGES))

    st.sidebar.title("Trading Bot")
    st.sidebar.radio(
        "Page",
        list(_PAGES.keys()),
        key="trading_page",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**API Status**")
    if _api_healthy():
        st.sidebar.success("Connected")
    else:
        st.sidebar.error("Disconnected")

    st.sidebar.markdown("---")
    if st.sidebar.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

    auto_refresh = st.sidebar.toggle("Auto-refresh (30s)", value=False)

    _PAGES[st.session_state.trading_page]()

    if auto_refresh:
        time.sleep(30)
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
