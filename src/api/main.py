"""
FastAPI endpoints to expose portfolio data.

Covers C12: Partager le jeu de données via API REST.

Run with: uvicorn src.api.main:app --reload
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.cache import _CACHE_TTL_SECONDS, RedisCache, cached_response, get_cache
from src.api.metrics import pipeline_last_run, portfolio_sharpe, records_ingested  # noqa: F401
from src.api.schemas import (
    BacktestResponse,
    CombinedPortfolioResponse,
    LivePricesResponse,
    RebalanceResponse,
    RiskContributionResponse,
    FrontierResponse,
    HealthResponse,
    KlinesResponse,
    MetricResponse,
    MetricsListResponse,
    MonteCarloResponse,
    PortfolioResponse,
    PortfolioSummaryResponse,
    SymbolsResponse,
)
from src.config import load_config
from src.storage import Storage, get_storage
from src.storage.base import StorageError

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

# Prometheus instrumentation — exposed at /prom/metrics to avoid
# colliding with the existing /metrics endpoint (processed financial metrics).
Instrumentator().instrument(app).expose(app, endpoint="/prom/metrics")


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
    storage: Storage = Depends(get_storage_dep),
) -> dict[str, Any]:
    """Get all raw klines data for a symbol."""
    available = storage.list_raw_symbols()
    if symbol not in available:
        raise HTTPException(404, f"Symbol {symbol} not found")
    try:
        data = storage.load_raw([symbol])
        records = data[symbol]
        return {"symbol": symbol, "count": len(records), "data": records}
    except Exception as e:
        logger.error("Failed to load klines for %s: %s", symbol, e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/metrics", response_model=MetricsListResponse)
def get_metrics(storage: Storage = Depends(get_storage_dep)) -> dict[str, list[str]]:
    """List available processed metrics."""
    return {"metrics": storage.list_processed()}


@app.get("/metrics/{name}", response_model=MetricResponse)
def get_metric(
    name: str,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get a specific processed metric (returns, volatility, correlation, covariance)."""
    try:
        return cached_response(
            cache,
            f"portfolio:metrics:{name}",
            _CACHE_TTL_SECONDS,
            lambda: {"name": name, "data": storage.load_processed(name)},
        )
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, f"Metric '{name}' not found") from e
    except Exception as e:
        logger.error("Failed to load metric %s: %s", name, e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get optimal portfolio weights."""
    try:
        return cached_response(
            cache,
            "portfolio:weights",
            _CACHE_TTL_SECONDS,
            lambda: storage.load_output("weights"),
        )
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Portfolio not found") from e
    except Exception as e:
        logger.error("Failed to load portfolio: %s", e)
        raise HTTPException(500, "Internal server error") from e


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
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Portfolio not found") from e
    except Exception as e:
        logger.error("Failed to load portfolio summary: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio/frontier", response_model=FrontierResponse)
def get_frontier(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get efficient frontier data."""
    try:
        return cached_response(
            cache,
            "portfolio:frontier",
            _CACHE_TTL_SECONDS,
            lambda: storage.load_output("frontier"),
        )
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Frontier not found") from e
    except Exception as e:
        logger.error("Failed to load frontier: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio/backtest", response_model=BacktestResponse)
def get_backtest(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get backtest results."""
    try:
        return cached_response(
            cache,
            "portfolio:backtest",
            _CACHE_TTL_SECONDS,
            lambda: storage.load_output("backtest"),
        )
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Backtest not found") from e
    except Exception as e:
        logger.error("Failed to load backtest: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Traditional Assets (yfinance) — /portfolio/trad/*
# =============================================================================


@app.get("/portfolio/trad", response_model=PortfolioResponse)
def get_trad_portfolio(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get optimal traditional asset portfolio weights."""
    try:
        return cached_response(
            cache,
            "portfolio:weights_trad",
            _CACHE_TTL_SECONDS,
            lambda: storage.load_output("weights_trad"),
        )
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Traditional portfolio not found") from e
    except Exception as e:
        logger.error("Failed to load trad portfolio: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio/trad/frontier", response_model=FrontierResponse)
def get_trad_frontier(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get efficient frontier for traditional assets."""
    try:
        return cached_response(
            cache,
            "portfolio:frontier_trad",
            _CACHE_TTL_SECONDS,
            lambda: storage.load_output("frontier_trad"),
        )
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Traditional frontier not found") from e
    except Exception as e:
        logger.error("Failed to load trad frontier: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio/trad/backtest", response_model=BacktestResponse)
def get_trad_backtest(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get backtest results for traditional assets."""
    try:
        return cached_response(
            cache,
            "portfolio:backtest_trad",
            _CACHE_TTL_SECONDS,
            lambda: storage.load_output("backtest_trad"),
        )
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Traditional backtest not found") from e
    except Exception as e:
        logger.error("Failed to load trad backtest: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio/monte-carlo", response_model=MonteCarloResponse)
def get_monte_carlo(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get Monte Carlo simulation results."""
    try:
        return cached_response(
            cache,
            "portfolio:monte_carlo",
            _CACHE_TTL_SECONDS,
            lambda: storage.load_output("monte_carlo"),
        )
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Monte Carlo results not found") from e
    except Exception as e:
        logger.error("Failed to load Monte Carlo results: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Risk Contribution — /portfolio/risk-contribution
# =============================================================================


@app.get("/portfolio/risk-contribution", response_model=RiskContributionResponse)
def get_risk_contribution(
    portfolio_key: str = "weights",
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get per-asset marginal risk contribution analysis."""
    from src.pipeline.optimize import compute_risk_contribution

    try:
        def _compute() -> dict[str, Any]:
            portfolio = storage.load_output(portfolio_key)
            weights_dict = portfolio.get("weights", {})
            symbols = list(weights_dict.keys())
            weights = list(weights_dict.values())
            cov_data = storage.load_processed("covariance")
            cov_matrix = cov_data["matrix"]
            return compute_risk_contribution(weights, cov_matrix, symbols)

        return cached_response(
            cache,
            f"portfolio:risk_contribution:{portfolio_key}",
            _CACHE_TTL_SECONDS,
            _compute,
        )
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Portfolio or covariance data not found") from e
    except Exception as e:
        logger.error("Failed to compute risk contribution: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Combined Portfolio — /portfolio/combined
# =============================================================================


@app.get("/portfolio/combined", response_model=CombinedPortfolioResponse)
def get_combined_portfolio(
    crypto_weight: float = 0.6,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get combined crypto + traditional portfolio with configurable split."""
    from src.pipeline.combine import CombineError, combine_portfolios

    try:
        return cached_response(
            cache,
            f"portfolio:combined:{crypto_weight}",
            _CACHE_TTL_SECONDS,
            lambda: combine_portfolios(
                crypto_weight=crypto_weight, storage=storage, save=False
            ),
        )
    except CombineError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to compute combined portfolio: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Rebalancing Alerts — /portfolio/rebalance
# =============================================================================


@app.get("/portfolio/rebalance", response_model=RebalanceResponse)
def get_rebalance_alerts(
    drift_threshold: float = 0.05,
    portfolio_value: float = 10000.0,
    portfolio_key: str = "weights",
    storage: Storage = Depends(get_storage_dep),
) -> dict[str, Any]:
    """Get rebalancing alerts comparing current vs optimal weights."""
    from src.pipeline.rebalance import RebalanceError, compute_rebalance_alerts

    try:
        return compute_rebalance_alerts(
            drift_threshold=drift_threshold,
            portfolio_value=portfolio_value,
            portfolio_key=portfolio_key,
            storage=storage,
            save=False,
        )
    except RebalanceError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to compute rebalance alerts: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# PDF Export — /portfolio/report
# =============================================================================


@app.get("/portfolio/report", response_class=FileResponse)
def get_portfolio_report(
    portfolio_key: str = "weights",
    storage: Storage = Depends(get_storage_dep),
) -> FileResponse:
    """Download a PDF report of portfolio optimization results."""
    from src.pipeline.pdf_export import PDFExportError, generate_portfolio_report

    try:
        tmp_dir = tempfile.mkdtemp()
        output_path = Path(tmp_dir) / "portfolio_report.pdf"
        generate_portfolio_report(
            output_path=output_path,
            portfolio_key=portfolio_key,
            storage=storage,
        )
        return FileResponse(
            path=str(output_path),
            filename="portfolio_report.pdf",
            media_type="application/pdf",
        )
    except PDFExportError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to generate PDF report: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Live Prices — /prices/live
# =============================================================================


@app.get("/prices/live", response_model=LivePricesResponse)
def get_live_prices() -> dict[str, Any]:
    """Get live prices for portfolio symbols from Binance."""
    from src.pipeline.live_prices import fetch_live_prices

    try:
        return fetch_live_prices()
    except Exception as e:
        logger.error("Failed to fetch live prices: %s", e)
        raise HTTPException(500, "Internal server error") from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
