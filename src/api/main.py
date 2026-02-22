"""
FastAPI endpoints to expose portfolio data.

Covers C12: Partager le jeu de données via API REST.

Run with: uvicorn src.api.main:app --reload
"""

import logging
import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    BacktestResponse,
    FrontierResponse,
    HealthResponse,
    KlinesResponse,
    MetricResponse,
    MetricsListResponse,
    PortfolioResponse,
    PortfolioSummaryResponse,
    SymbolsResponse,
)
from src.config import load_config
from src.storage import Storage, get_storage

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Portfolio Optimization API",
    description="Expose crypto portfolio data and optimization results",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_storage_dep() -> Storage:
    """Dependency: injectable storage backend."""
    return get_storage(load_config().storage_backend)


@app.get("/", response_model=HealthResponse)
def root() -> dict[str, str]:
    """API health check."""
    return {"status": "ok", "message": "Portfolio API"}


@app.get("/symbols", response_model=SymbolsResponse)
def get_symbols(storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """List available symbols in raw data."""
    symbols = storage.list_raw_symbols()
    return {"symbols": symbols, "count": len(symbols)}


@app.get("/klines/{symbol}", response_model=KlinesResponse)
def get_klines(
    symbol: str,
    limit: int = 500,
    offset: int = 0,
    storage: Storage = Depends(get_storage_dep),
) -> dict[str, Any]:
    """Get raw klines data for a symbol (paginated)."""
    available = storage.list_raw_symbols()
    if symbol not in available:
        raise HTTPException(404, f"Symbol {symbol} not found")
    try:
        data = storage.load_raw([symbol])
        records = data[symbol]
        page = records[offset : offset + limit]
        return {"symbol": symbol, "count": len(page), "data": page}
    except Exception as e:
        logger.error("Failed to load klines for %s: %s", symbol, e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/metrics", response_model=MetricsListResponse)
def get_metrics(storage: Storage = Depends(get_storage_dep)) -> dict[str, list[str]]:
    """List available processed metrics."""
    return {"metrics": storage.list_processed()}


@app.get("/metrics/{name}", response_model=MetricResponse)
def get_metric(name: str, storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """Get a specific processed metric (returns, volatility, correlation, covariance)."""
    try:
        data = storage.load_processed(name)
        return {"name": name, "data": data}
    except Exception as e:
        logger.warning("Metric %s not found: %s", name, e)
        raise HTTPException(404, "Metric not found") from e


@app.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """Get optimal portfolio weights."""
    try:
        data = storage.load_output("weights")
        return data
    except Exception as e:
        logger.warning("Portfolio not found: %s", e)
        raise HTTPException(404, "Portfolio not found") from e


@app.get("/portfolio/summary", response_model=PortfolioSummaryResponse)
def get_portfolio_summary(storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """Get portfolio summary (weights only, no full data)."""
    try:
        data = storage.load_output("weights")
        return {
            "weights": data.get("weights", {}),
            "expected_return": data.get("expected_return"),
            "volatility": data.get("volatility"),
            "sharpe_ratio": data.get("sharpe_ratio"),
        }
    except Exception as e:
        logger.warning("Portfolio not found: %s", e)
        raise HTTPException(404, "Portfolio not found") from e


@app.get("/portfolio/frontier", response_model=FrontierResponse)
def get_frontier(storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """Get efficient frontier data."""
    try:
        data = storage.load_output("frontier")
        return data
    except Exception as e:
        logger.warning("Frontier not found: %s", e)
        raise HTTPException(404, "Frontier not found") from e


@app.get("/portfolio/backtest", response_model=BacktestResponse)
def get_backtest(storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """Get backtest results."""
    try:
        data = storage.load_output("backtest")
        return data
    except Exception as e:
        logger.warning("Backtest not found: %s", e)
        raise HTTPException(404, "Backtest not found") from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
