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


class MonteCarloResponse(BaseModel):
    """Monte Carlo simulation results."""

    percentiles: dict[str, list[float]]
    final_values: list[float]
    var_95: float
    cvar_95: float
    symbols: list[str] | None = None
    config: dict[str, Any]


class RebalanceAlertItem(BaseModel):
    symbol: str
    current_weight: float
    target_weight: float
    drift: float
    drift_pct: float
    action: str


class RebalanceTradeItem(BaseModel):
    symbol: str
    action: str
    amount_usd: float
    weight_change: float


class RebalanceSummary(BaseModel):
    total_drift: float
    max_drift: float
    n_alerts: int
    n_symbols: int
    drift_threshold: float
    portfolio_value: float
    needs_rebalance: bool


class RebalanceResponse(BaseModel):
    """Rebalancing alerts and suggested trades."""

    alerts: list[RebalanceAlertItem]
    trades: list[RebalanceTradeItem]
    summary: RebalanceSummary
    portfolio_key: str


class StressTestAssetImpact(BaseModel):
    symbol: str
    weight: float
    shock: float
    impact: float
    stressed_weight: float


class StressTestPortfolioImpact(BaseModel):
    total_return_impact: float
    original_return: float
    stressed_return: float
    original_volatility: float
    stressed_volatility: float
    value_at_risk_1pct: float


class StressTestResponse(BaseModel):
    """Stress test results."""

    scenario: dict[str, Any]
    asset_impacts: list[StressTestAssetImpact]
    portfolio_impact: StressTestPortfolioImpact
    worst_hit: str | None
    best_performer: str | None
    n_assets: int
    portfolio_key: str


class ScenarioListResponse(BaseModel):
    """Available stress test scenarios."""

    scenarios: list[dict[str, str]]


class RollingCorrelationPair(BaseModel):
    pair: str
    symbol_a: str
    symbol_b: str
    correlations: list[float | None]


class RollingCorrelationResponse(BaseModel):
    """Rolling pairwise correlation data."""

    pairs: list[RollingCorrelationPair]
    window: int
    n_periods: int
    n_pairs: int


class RiskContributionItem(BaseModel):
    symbol: str
    weight: float
    mctr: float
    risk_contribution: float
    pct_contribution: float


class RiskContributionResponse(BaseModel):
    """Per-asset risk contribution analysis."""

    contributions: list[RiskContributionItem]
    portfolio_volatility: float
    n_assets: int


class TickerItem(BaseModel):
    symbol: str
    price: float
    change_24h: float
    volume_24h: float
    high_24h: float
    low_24h: float


class LivePricesResponse(BaseModel):
    """Live price ticker data."""

    crypto: list[TickerItem]
    trad: list[TickerItem]
    timestamp: str
    n_crypto: int
    n_trad: int


class CustomPortfolioRequest(BaseModel):
    """Request body for custom portfolio evaluation."""

    weights: dict[str, float]
    risk_free_rate: float = 0.0


class CustomPortfolioContribution(BaseModel):
    symbol: str
    weight: float
    expected_return: float
    mctr: float
    risk_contribution: float


class CustomPortfolioResponse(BaseModel):
    """Custom portfolio evaluation result."""

    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    risk_free_rate: float
    contributions: list[CustomPortfolioContribution]
    n_assets: int


class AttributionItem(BaseModel):
    symbol: str
    weight: float
    asset_return: float
    contribution: float
    pct_contribution: float


class AttributionResponse(BaseModel):
    """Performance attribution analysis."""

    contributions: list[AttributionItem]
    portfolio_return: float
    n_assets: int
    top_contributors: list[str]
    bottom_contributors: list[str]
    portfolio_key: str


class DrawdownSummary(BaseModel):
    max_drawdown: float
    avg_drawdown: float
    n_periods: int
    longest_duration: int
    current_drawdown: float
    time_in_drawdown_pct: float


class DrawdownAnalysisItem(BaseModel):
    strategy: str
    drawdown_series: list[float]
    dates: list[str] | None = None
    periods: list[dict[str, Any]]
    summary: DrawdownSummary


class DrawdownComparisonItem(BaseModel):
    strategy: str
    max_drawdown: float


class DrawdownResponse(BaseModel):
    """Full drawdown analysis across strategies."""

    analyses: dict[str, DrawdownAnalysisItem]
    comparison: list[DrawdownComparisonItem]
    n_strategies: int
    portfolio_key: str


class CombinedPortfolioResponse(BaseModel):
    """Combined crypto + traditional portfolio."""

    weights: dict[str, float]
    allocation: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    crypto_symbols: list[str]
    trad_symbols: list[str]
    crypto_metrics: dict[str, Any]
    trad_metrics: dict[str, Any]
