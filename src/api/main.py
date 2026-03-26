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
    AlphaBetaResponse,
    AttributionResponse,
    BacktestResponse,
    BlackLittermanResponse,
    CombinedPortfolioResponse,
    ConstrainedPortfolioRequest,
    ConstrainedPortfolioResponse,
    CostAnalysisResponse,
    CustomPortfolioRequest,
    CustomPortfolioResponse,
    DecayResponse,
    DrawdownResponse,
    FactorAnalysisResponse,
    FrontierResponse,
    HRPResponse,
    HealthResponse,
    KlinesResponse,
    LivePricesResponse,
    MaxDiversificationResponse,
    MetricResponse,
    MetricsListResponse,
    MinVarianceResponse,
    MonteCarloResponse,
    PairsResponse,
    PortfolioResponse,
    PortfolioSummaryResponse,
    PositionSizingResponse,
    RebalanceResponse,
    RegimeResponse,
    RiskContributionResponse,
    RiskParityResponse,
    RollingCorrelationResponse,
    ScenarioListResponse,
    ShrinkageResponse,
    SignalsResponse,
    SortinoResponse,
    StressTestResponse,
    SymbolsResponse,
    TailRiskResponse,
    VaRResponse,
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
    allow_methods=["GET", "POST"],
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
# Rolling Correlation — /portfolio/rolling-correlation
# =============================================================================


@app.get("/portfolio/rolling-correlation", response_model=RollingCorrelationResponse)
def get_rolling_correlation(
    window: int = 30,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get rolling pairwise correlation between portfolio assets."""
    from src.pipeline.transform import TransformError, compute_rolling_correlation

    try:
        def _compute() -> dict[str, Any]:
            returns_data = storage.load_processed("returns")
            symbols = returns_data["symbols"]
            returns = returns_data["values"]
            return compute_rolling_correlation(returns, symbols, window=window)

        return cached_response(
            cache,
            f"portfolio:rolling_corr:{window}",
            _CACHE_TTL_SECONDS,
            _compute,
        )
    except TransformError as e:
        raise HTTPException(400, e.message) from e
    except (StorageError, FileNotFoundError) as e:
        raise HTTPException(404, "Returns data not found") from e
    except Exception as e:
        logger.error("Failed to compute rolling correlation: %s", e)
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


# =============================================================================
# Stress Testing — /portfolio/stress-test
# =============================================================================


@app.get("/portfolio/scenarios", response_model=ScenarioListResponse)
def get_scenarios() -> dict[str, Any]:
    """List available stress test scenarios."""
    from src.pipeline.stress_test import list_scenarios

    return {"scenarios": list_scenarios()}


@app.get("/portfolio/stress-test", response_model=StressTestResponse)
def get_stress_test(
    scenario: str = "crypto_crash",
    portfolio_key: str = "weights",
    storage: Storage = Depends(get_storage_dep),
) -> dict[str, Any]:
    """Run a stress test scenario against the portfolio."""
    from src.pipeline.stress_test import StressTestError, run_stress_test

    try:
        return run_stress_test(
            scenario_name=scenario,
            portfolio_key=portfolio_key,
            storage=storage,
            save=False,
        )
    except StressTestError as e:
        raise HTTPException(400, e.message) from e
    except Exception as e:
        logger.error("Failed to run stress test: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Drawdown Analysis — /portfolio/drawdown
# =============================================================================


@app.get("/portfolio/drawdown", response_model=DrawdownResponse)
def get_drawdown_analysis(
    portfolio_key: str = "backtest",
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get drawdown analysis for all backtest strategies."""
    from src.pipeline.drawdown import DrawdownError, analyze_portfolio_drawdowns

    try:
        return cached_response(
            cache,
            f"portfolio:drawdown:{portfolio_key}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_portfolio_drawdowns(
                portfolio_key=portfolio_key, storage=storage, save=False
            ),
        )
    except DrawdownError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to compute drawdown analysis: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Performance Attribution — /portfolio/attribution
# =============================================================================


@app.get("/portfolio/attribution", response_model=AttributionResponse)
def get_attribution(
    portfolio_key: str = "weights",
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get per-asset performance attribution analysis."""
    from src.pipeline.attribution import (
        AttributionError,
        analyze_performance_attribution,
    )

    try:
        return cached_response(
            cache,
            f"portfolio:attribution:{portfolio_key}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_performance_attribution(
                portfolio_key=portfolio_key, storage=storage, save=False
            ),
        )
    except AttributionError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to compute attribution: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Custom Portfolio Evaluation — POST /portfolio/custom
# =============================================================================


@app.post("/portfolio/custom", response_model=CustomPortfolioResponse)
def evaluate_custom(
    body: CustomPortfolioRequest,
    storage: Storage = Depends(get_storage_dep),
) -> dict[str, Any]:
    """Evaluate custom portfolio weights against current market data."""
    from src.pipeline.evaluate import EvaluateError, evaluate_custom_portfolio

    try:
        return evaluate_custom_portfolio(
            weights=body.weights,
            risk_free_rate=body.risk_free_rate,
            storage=storage,
        )
    except EvaluateError as e:
        raise HTTPException(400, e.message) from e
    except Exception as e:
        logger.error("Failed to evaluate custom portfolio: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Trading Signals — /portfolio/signals
# =============================================================================


@app.get("/portfolio/signals", response_model=SignalsResponse)
def get_signals(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get trading signals (SMA crossover, RSI, MACD, Bollinger) for all assets."""
    from src.pipeline.signals import SignalError, generate_portfolio_signals

    try:
        return cached_response(
            cache,
            "portfolio:signals",
            _CACHE_TTL_SECONDS,
            lambda: generate_portfolio_signals(storage=storage, save=False),
        )
    except SignalError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to generate signals: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Risk Parity — /portfolio/risk-parity
# =============================================================================


@app.get("/portfolio/risk-parity", response_model=RiskParityResponse)
def get_risk_parity(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Get risk parity portfolio allocation (equal risk contribution)."""
    from src.pipeline.risk_parity import RiskParityError, optimize_risk_parity

    try:
        return cached_response(
            cache,
            "portfolio:risk-parity",
            _CACHE_TTL_SECONDS,
            lambda: optimize_risk_parity(storage=storage, save=False),
        )
    except RiskParityError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to compute risk parity: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Position Sizing — /portfolio/position-sizing
# =============================================================================


@app.get("/portfolio/position-sizing", response_model=PositionSizingResponse)
def get_position_sizing(
    portfolio_value: float = 10000.0,
    method: str = "weight",
    target_volatility: float = 0.15,
    portfolio_key: str = "weights",
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Compute position sizes (weight, vol-target, or fixed-fractional)."""
    from src.pipeline.position_sizing import (
        PositionSizingError,
        analyze_position_sizing,
    )

    try:
        return cached_response(
            cache,
            f"portfolio:position-sizing:{portfolio_key}:{method}:{portfolio_value}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_position_sizing(
                portfolio_key=portfolio_key,
                portfolio_value=portfolio_value,
                method=method,
                target_volatility=target_volatility,
                storage=storage,
                save=False,
            ),
        )
    except PositionSizingError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to compute position sizing: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio/cost-analysis", response_model=CostAnalysisResponse)
def get_cost_analysis(
    portfolio_key: str = "weights",
    portfolio_value: float = 10000.0,
    n_rebalances: int = 12,
    fee_rate: float = 0.001,
    slippage_bps: float = 5.0,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Analyze transaction costs: fees, slippage, net-of-cost returns."""
    from src.pipeline.costs import CostError, analyze_costs

    try:
        return cached_response(
            cache,
            f"cost_analysis:{portfolio_key}:{portfolio_value}:{n_rebalances}:{fee_rate}:{slippage_bps}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_costs(
                portfolio_key=portfolio_key,
                portfolio_value=portfolio_value,
                n_rebalances=n_rebalances,
                fee_rate=fee_rate,
                slippage_bps=slippage_bps,
                storage=storage,
                save=False,
            ),
        )
    except CostError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to compute cost analysis: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio/alpha-beta", response_model=AlphaBetaResponse)
def get_alpha_beta(
    portfolio_key: str = "weights",
    benchmark: str = "BTCUSDT",
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """CAPM alpha/beta analysis vs a benchmark (default BTC)."""
    from src.pipeline.alpha_beta import AlphaBetaError, analyze_alpha_beta

    try:
        return cached_response(
            cache,
            f"alpha_beta:{portfolio_key}:{benchmark}:{risk_free_rate}:{periods_per_year}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_alpha_beta(
                portfolio_key=portfolio_key,
                benchmark_symbol=benchmark,
                risk_free_rate=risk_free_rate,
                periods_per_year=periods_per_year,
                storage=storage,
                save=False,
            ),
        )
    except AlphaBetaError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to compute alpha/beta: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio/regime", response_model=RegimeResponse)
def get_regime(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Detect market regime (bull/bear/sideways) for each portfolio asset."""
    from src.pipeline.regime import RegimeError, analyze_regimes

    try:
        return cached_response(
            cache,
            "regime",
            _CACHE_TTL_SECONDS,
            lambda: analyze_regimes(storage=storage, save=False),
        )
    except RegimeError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to detect regimes: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.get("/portfolio/sortino", response_model=SortinoResponse)
def get_sortino(
    portfolio_key: str = "weights",
    benchmark: str = "BTCUSDT",
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Sortino ratio and downside risk metrics."""
    from src.pipeline.sortino import SortinoError, analyze_sortino

    try:
        return cached_response(
            cache,
            f"sortino:{portfolio_key}:{benchmark}:{risk_free_rate}:{periods_per_year}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_sortino(
                portfolio_key=portfolio_key,
                benchmark_symbol=benchmark,
                risk_free_rate=risk_free_rate,
                periods_per_year=periods_per_year,
                storage=storage,
                save=False,
            ),
        )
    except SortinoError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed to compute Sortino metrics: %s", e)
        raise HTTPException(500, "Internal server error") from e


@app.post("/portfolio/constrained", response_model=ConstrainedPortfolioResponse)
def post_constrained_portfolio(
    body: ConstrainedPortfolioRequest,
    storage: Storage = Depends(get_storage_dep),
) -> dict[str, Any]:
    """Optimize portfolio with min/max weight and group constraints."""
    from src.pipeline.constrained import ConstrainedError, analyze_constrained

    try:
        return analyze_constrained(
            min_weights=body.min_weights,
            max_weights=body.max_weights,
            group_constraints=body.group_constraints,
            risk_free_rate=body.risk_free_rate,
            storage=storage,
            save=False,
        )
    except ConstrainedError as e:
        raise HTTPException(
            422 if e.operation == "validate" else 404, e.message
        ) from e
    except Exception as e:
        logger.error("Failed constrained optimization: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Black-Litterman — /portfolio/black-litterman
# =============================================================================


@app.get("/portfolio/black-litterman", response_model=BlackLittermanResponse)
def get_black_litterman(
    risk_aversion: float = 2.5,
    tau: float = 0.05,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Black-Litterman portfolio optimization with implied views."""
    from src.pipeline.black_litterman import (
        BlackLittermanError,
        analyze_black_litterman,
    )

    try:
        return cached_response(
            cache,
            f"portfolio:black-litterman:{risk_aversion}:{tau}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_black_litterman(
                risk_aversion=risk_aversion,
                tau=tau,
                storage=storage,
                save=False,
            ),
        )
    except BlackLittermanError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed Black-Litterman optimization: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Hierarchical Risk Parity — /portfolio/hrp
# =============================================================================


@app.get("/portfolio/hrp", response_model=HRPResponse)
def get_hrp(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Hierarchical Risk Parity portfolio allocation."""
    from src.pipeline.hrp import HRPError, analyze_hrp

    try:
        return cached_response(
            cache,
            "portfolio:hrp",
            _CACHE_TTL_SECONDS,
            lambda: analyze_hrp(storage=storage, save=False),
        )
    except HRPError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed HRP allocation: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# VaR Comparison — /portfolio/var
# =============================================================================


@app.get("/portfolio/var", response_model=VaRResponse)
def get_var(
    confidence: float = 0.95,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Compare Value-at-Risk methods (Historical, Parametric, Cornish-Fisher)."""
    from src.pipeline.var_models import VaRError, analyze_var

    try:
        return cached_response(
            cache,
            f"portfolio:var:{confidence}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_var(
                confidence=confidence, storage=storage, save=False
            ),
        )
    except VaRError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed VaR computation: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Covariance Shrinkage — /portfolio/shrinkage
# =============================================================================


@app.get("/portfolio/shrinkage", response_model=ShrinkageResponse)
def get_shrinkage(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Ledoit-Wolf covariance shrinkage analysis."""
    from src.pipeline.shrinkage import ShrinkageError, analyze_shrinkage

    try:
        return cached_response(
            cache,
            "portfolio:shrinkage",
            _CACHE_TTL_SECONDS,
            lambda: analyze_shrinkage(storage=storage, save=False),
        )
    except ShrinkageError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed shrinkage analysis: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Maximum Diversification — /portfolio/max-diversification
# =============================================================================


@app.get("/portfolio/max-diversification", response_model=MaxDiversificationResponse)
def get_max_diversification(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Maximum diversification portfolio (maximize diversification ratio)."""
    from src.pipeline.max_diversification import (
        MaxDiversificationError,
        analyze_max_diversification,
    )

    try:
        return cached_response(
            cache,
            "portfolio:max-diversification",
            _CACHE_TTL_SECONDS,
            lambda: analyze_max_diversification(storage=storage, save=False),
        )
    except MaxDiversificationError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed max diversification: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Minimum Variance — /portfolio/min-variance
# =============================================================================


@app.get("/portfolio/min-variance", response_model=MinVarianceResponse)
def get_min_variance(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Global minimum variance portfolio."""
    from src.pipeline.min_variance import MinVarianceError, analyze_min_variance

    try:
        return cached_response(
            cache,
            "portfolio:min-variance",
            _CACHE_TTL_SECONDS,
            lambda: analyze_min_variance(storage=storage, save=False),
        )
    except MinVarianceError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed min variance optimization: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Factor Analysis — /portfolio/factors
# =============================================================================


@app.get("/portfolio/factors", response_model=FactorAnalysisResponse)
def get_factor_analysis(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Multi-factor exposure analysis (market, momentum, volatility)."""
    from src.pipeline.factor_analysis import FactorAnalysisError, analyze_factors

    try:
        return cached_response(
            cache,
            "portfolio:factors",
            _CACHE_TTL_SECONDS,
            lambda: analyze_factors(storage=storage, save=False),
        )
    except FactorAnalysisError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed factor analysis: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Tail Risk — /portfolio/tail-risk
# =============================================================================


@app.get("/portfolio/tail-risk", response_model=TailRiskResponse)
def get_tail_risk(
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Tail risk analysis: skewness, kurtosis, Jarque-Bera, Omega, Calmar."""
    from src.pipeline.tail_risk import TailRiskError, analyze_tail_risk

    try:
        return cached_response(
            cache,
            "portfolio:tail-risk",
            _CACHE_TTL_SECONDS,
            lambda: analyze_tail_risk(storage=storage, save=False),
        )
    except TailRiskError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed tail risk analysis: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Portfolio Decay — /portfolio/decay
# =============================================================================


@app.get("/portfolio/decay", response_model=DecayResponse)
def get_decay(
    max_deviation_threshold: float = 0.05,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Analyze portfolio weight drift from target over time."""
    from src.pipeline.decay import DecayError, analyze_decay

    try:
        return cached_response(
            cache,
            f"portfolio:decay:{max_deviation_threshold}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_decay(
                max_deviation_threshold=max_deviation_threshold,
                storage=storage,
                save=False,
            ),
        )
    except DecayError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed decay analysis: %s", e)
        raise HTTPException(500, "Internal server error") from e


# =============================================================================
# Pairs Trading — /portfolio/pairs
# =============================================================================


@app.get("/portfolio/pairs", response_model=PairsResponse)
def get_pairs(
    min_observations: int = 50,
    storage: Storage = Depends(get_storage_dep),
    cache: RedisCache | None = Depends(get_cache),
) -> dict[str, Any]:
    """Pair trading cointegration analysis across portfolio assets."""
    from src.pipeline.pairs import PairsError, analyze_pairs

    try:
        return cached_response(
            cache,
            f"portfolio:pairs:{min_observations}",
            _CACHE_TTL_SECONDS,
            lambda: analyze_pairs(
                min_observations=min_observations,
                storage=storage,
                save=False,
            ),
        )
    except PairsError as e:
        raise HTTPException(404, e.message) from e
    except Exception as e:
        logger.error("Failed pairs analysis: %s", e)
        raise HTTPException(500, "Internal server error") from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
