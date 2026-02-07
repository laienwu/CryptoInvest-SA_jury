"""
Pydantic response models for the Portfolio Optimization API.

Provides typed, validated response schemas that also drive the
auto-generated OpenAPI documentation.
"""

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
    data: dict


class PortfolioSummaryResponse(BaseModel):
    weights: dict[str, float]
    expected_return: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
