"""
Pydantic response models for the Portfolio Optimization API.

Provides typed, validated response schemas that also drive the
auto-generated OpenAPI documentation.
"""

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    message: str


class SymbolsResponse(BaseModel):
    symbols: list[str]
    count: int


class KlineRecord(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class KlinesResponse(BaseModel):
    symbol: str
    count: int
    data: list[KlineRecord]


class MetricsListResponse(BaseModel):
    metrics: list[str]


class MetricResponse(BaseModel):
    name: str
    data: dict[str, Any]


class PortfolioSummaryResponse(BaseModel):
    weights: dict[str, float]
    expected_return: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None


class PortfolioResponse(BaseModel):
    """Full portfolio optimization result."""

    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    optimization_method: str | None = None
    computed_at: str | None = None


class FrontierResponse(BaseModel):
    """Efficient frontier data."""

    frontier: list[dict[str, Any]]
    max_sharpe: dict[str, Any]
    min_variance: dict[str, Any]
    assets: list[dict[str, Any]]
    capital_market_line: dict[str, Any] | None = None
    risk_free_rate: float | None = None
    symbols: list[str] | None = None


class BacktestResponse(BaseModel):
    """Walk-forward backtest results."""

    windows: list[dict[str, Any]]
    cumulative_values: dict[str, Any]
    metrics: dict[str, Any]
    symbols: list[str] | None = None
    config: dict[str, Any]
