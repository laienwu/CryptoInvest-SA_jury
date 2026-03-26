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


class PositionItem(BaseModel):
    symbol: str
    original_weight: float
    adjusted_weight: float
    amount_usd: float


class PositionSizingResponse(BaseModel):
    """Position sizing results."""

    positions: list[PositionItem]
    total_allocated: float
    portfolio_value: float
    method: str
    target_volatility: float | None = None
    risk_per_trade: float | None = None
    n_assets: int


class RiskParityContribution(BaseModel):
    symbol: str
    weight: float
    risk_contribution: float
    pct_contribution: float


class RiskParityResponse(BaseModel):
    """Risk parity portfolio allocation."""

    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    contributions: list[RiskParityContribution]
    converged: bool
    iterations: int
    n_assets: int
    optimization_method: str


class SignalItem(BaseModel):
    symbol: str
    sma_crossover: str | None = None
    rsi: str | None = None
    macd: str | None = None
    bollinger: str | None = None
    combined: str | None = None
    rsi_value: float | None = None
    n_periods: int


class SignalSummary(BaseModel):
    buy_count: int
    sell_count: int
    hold_count: int
    total: int


class SignalsResponse(BaseModel):
    """Trading signals for all portfolio assets."""

    signals: list[SignalItem]
    summary: SignalSummary
    n_assets: int


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


class TradeDetail(BaseModel):
    symbol: str
    weight_change: float
    trade_value_usd: float
    action: str
    fee_cost: float
    slippage_cost: float
    total_cost: float
    cost_pct: float


class RebalanceCosts(BaseModel):
    trades: list[TradeDetail]
    total_cost_usd: float
    total_turnover_usd: float
    cost_pct_of_portfolio: float
    n_trades: int
    fee_rate: float
    slippage_bps: float
    portfolio_value: float


class CostAdjustedReturns(BaseModel):
    gross_return: float
    net_return: float
    annual_cost: float
    gross_sharpe: float
    net_sharpe: float
    sharpe_drag: float
    n_rebalances_per_year: int
    cost_per_rebalance: float


class CostAnalysisResponse(BaseModel):
    """Transaction cost analysis results."""

    rebalance_costs: RebalanceCosts
    cost_adjusted_returns: CostAdjustedReturns
    portfolio_key: str


class AlphaBetaResponse(BaseModel):
    """Alpha/beta CAPM analysis results."""

    benchmark: str
    portfolio_key: str
    beta: float
    alpha_annual: float
    r_squared: float
    tracking_error: float
    information_ratio: float
    n_periods: int
    periods_per_year: int
    risk_free_rate: float


class SortinoResponse(BaseModel):
    """Sortino ratio and downside risk metrics."""

    portfolio_key: str
    benchmark: str
    sortino_ratio: float
    downside_deviation: float
    upside_deviation: float
    gain_to_pain: float
    upside_capture: float | None
    downside_capture: float | None
    n_periods: int
    n_negative: int
    n_positive: int
    worst_return: float
    best_return: float
    periods_per_year: int
    risk_free_rate: float


class ConstrainedPortfolioRequest(BaseModel):
    """Request body for constrained portfolio optimization."""

    min_weights: dict[str, float] | None = None
    max_weights: dict[str, float] | None = None
    group_constraints: list[dict[str, Any]] | None = None
    risk_free_rate: float = 0.0


class ConstraintsApplied(BaseModel):
    min_weights: dict[str, float]
    max_weights: dict[str, float]
    n_active: int
    groups: list[dict[str, Any]] | None = None


class ConstrainedPortfolioResponse(BaseModel):
    """Constrained portfolio optimization result."""

    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    risk_free_rate: float
    constraints: ConstraintsApplied
    n_assets: int
    optimization_method: str


class RegimeItem(BaseModel):
    symbol: str
    regime: str
    confidence: float
    trend_signal: str
    vol_regime: str
    short_sma: float | None
    long_sma: float | None
    current_vol: float
    median_vol: float
    n_periods: int


class RegimeSummary(BaseModel):
    market_regime: str
    bull_count: int
    bear_count: int
    sideways_count: int
    n_assets: int


class RegimeResponse(BaseModel):
    """Market regime detection results."""

    regimes: list[RegimeItem]
    summary: RegimeSummary


class BlackLittermanResponse(BaseModel):
    """Black-Litterman portfolio optimization result."""

    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    equilibrium_returns: dict[str, float]
    posterior_returns: dict[str, float]
    views: list[dict[str, Any]]
    n_assets: int
    method: str


class HRPResponse(BaseModel):
    """Hierarchical Risk Parity allocation result."""

    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    n_assets: int
    method: str


class VaRMethodResult(BaseModel):
    var: float
    cvar: float


class VaRAssetBreakdown(BaseModel):
    symbol: str
    historical: VaRMethodResult
    parametric: VaRMethodResult
    cornish_fisher: VaRMethodResult


class VaRResponse(BaseModel):
    """Value-at-Risk comparison across methods."""

    portfolio: dict[str, VaRMethodResult]
    per_asset: list[VaRAssetBreakdown]
    confidence: float
    n_observations: int
    method: str


class ShrinkageEigenvalue(BaseModel):
    sample: list[float]
    shrunk: list[float]
    condition_number_sample: float
    condition_number_shrunk: float


class ShrinkageResponse(BaseModel):
    """Ledoit-Wolf covariance shrinkage analysis."""

    intensity: float
    n_assets: int
    n_observations: int
    eigenvalue_comparison: ShrinkageEigenvalue
    symbols: list[str]
    method: str


class MaxDiversificationResponse(BaseModel):
    """Maximum diversification portfolio result."""

    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    diversification_ratio: float
    n_assets: int
    method: str


class MinVarianceResponse(BaseModel):
    """Minimum variance portfolio result."""

    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    equal_weight_volatility: float
    equal_weight_return: float
    volatility_reduction_pct: float
    n_assets: int
    method: str


class FactorExposure(BaseModel):
    symbol: str
    alpha: float
    betas: dict[str, float]
    r_squared: float


class FactorAnalysisResponse(BaseModel):
    """Factor exposure analysis result."""

    per_asset: list[FactorExposure]
    factors: list[str]
    n_assets: int
    n_periods: int
    method: str


class TailMetrics(BaseModel):
    symbol: str
    skewness: float
    excess_kurtosis: float
    jarque_bera: float
    is_normal: bool
    omega_ratio: float
    calmar_ratio: float
    max_drawdown: float
    n_observations: int


class TailRiskResponse(BaseModel):
    """Tail risk and higher moments analysis."""

    portfolio_metrics: TailMetrics
    per_asset: list[TailMetrics]
    n_assets: int
    method: str


class DecaySnapshot(BaseModel):
    period: int
    tracking_error: float
    max_deviation: float


class OptimalRebalance(BaseModel):
    periods_to_threshold: int
    threshold: float
    max_drift_at_threshold: float


class DecayResponse(BaseModel):
    """Portfolio weight decay analysis."""

    target_weights: dict[str, float]
    drift_summary: list[DecaySnapshot]
    optimal_rebalance: OptimalRebalance
    n_assets: int
    n_periods: int
    method: str


class PairResult(BaseModel):
    pair: list[str]
    adf_statistic: float
    hedge_ratio: float
    is_cointegrated: bool


class PairsResponse(BaseModel):
    """Pair trading cointegration analysis."""

    pairs: list[PairResult]
    n_pairs_tested: int
    n_cointegrated: int
    top_pair_detail: dict[str, Any] | None = None
    method: str
