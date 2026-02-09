"""
FastAPI endpoints to expose portfolio data.

Covers C12: Partager le jeu de données via API REST.

Run with: uvicorn src.api.main:app --reload
"""

from typing import Any

from fastapi import Depends, FastAPI, HTTPException

from src.api.schemas import (
    HealthResponse,
    KlinesResponse,
    MetricResponse,
    MetricsListResponse,
    PortfolioSummaryResponse,
    SymbolsResponse,
)
from src.storage import Storage, get_storage

app = FastAPI(
    title="Portfolio Optimization API",
    description="Expose crypto portfolio data and optimization results",
    version="1.0.0",
)


def get_storage_dep() -> Storage:
    """Dependency: injectable storage backend."""
    return get_storage("parquet")


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
def get_klines(symbol: str, storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """Get raw klines data for a symbol."""
    try:
        data = storage.load_raw([symbol])
        if symbol not in data:
            raise HTTPException(404, f"Symbol {symbol} not found")
        return {"symbol": symbol, "count": len(data[symbol]), "data": data[symbol]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e)) from e


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
        raise HTTPException(404, f"Metric {name} not found: {e}") from e


@app.get("/portfolio")
def get_portfolio(storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """Get optimal portfolio weights."""
    try:
        data = storage.load_output("weights")
        return data
    except Exception as e:
        raise HTTPException(404, f"Portfolio not found: {e}") from e


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
        raise HTTPException(404, f"Portfolio not found: {e}") from e


@app.get("/portfolio/frontier")
def get_frontier(storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """Get efficient frontier data."""
    try:
        data = storage.load_output("frontier")
        return data
    except Exception as e:
        raise HTTPException(404, f"Frontier not found: {e}") from e


@app.get("/portfolio/backtest")
def get_backtest(storage: Storage = Depends(get_storage_dep)) -> dict[str, Any]:
    """Get backtest results."""
    try:
        data = storage.load_output("backtest")
        return data
    except Exception as e:
        raise HTTPException(404, f"Backtest not found: {e}") from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
