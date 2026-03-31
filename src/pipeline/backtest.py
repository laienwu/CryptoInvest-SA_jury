"""
Backtesting engine for portfolio optimization.

Implements walk-forward validation: optimize on a training window,
then measure out-of-sample performance on the next test window.

Compares the optimized strategy against two benchmarks:
- Equal-weight portfolio
- BTC-only portfolio

Output:
- Rolling window results (weights, test returns)
- Cumulative value series for strategy and benchmarks
- Performance metrics (Sharpe, max drawdown, Calmar ratio)

Example usage:
    >>> from src.pipeline.backtest import run_backtest
    >>> result = run_backtest()
    >>> print(result["metrics"]["strategy"])
"""

import logging
import math
from typing import Any

from src.config import load_config, load_yfinance_config
from src.pipeline.optimize import optimize_weights
from src.pipeline.transform import (
    align_data_by_date,
    calculate_covariance_matrix,
    calculate_log_returns,
    calculate_mean,
    calculate_mean_returns,
    calculate_stddev,
)
from src.storage import Storage, get_storage

logger = logging.getLogger(__name__)

# =============================================================================
# Exceptions
# =============================================================================


class BacktestError(Exception):
    """Custom exception for backtesting errors."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


# =============================================================================
# Rolling Windows
# =============================================================================


def _create_rolling_windows(
    dates: list[str],
    prices_matrix: list[list[float]],
    train_window: int,
    test_window: int,
) -> list[dict[str, Any]]:
    """
    Create rolling train/test windows from time series data.

    Slides through the data creating non-overlapping test windows,
    each preceded by a training window of the specified size.

    Args:
        dates: List of dates.
        prices_matrix: 2D list [n_symbols][n_dates] of prices.
        train_window: Number of days in training window.
        test_window: Number of days in test window.

    Returns:
        List of window dictionaries with indices and date ranges.

    Raises:
        BacktestError: If insufficient data for at least one window.
    """
    n_dates = len(dates)
    min_required = train_window + test_window

    if n_dates < min_required:
        raise BacktestError(
            f"Insufficient data: {n_dates} dates, need at least {min_required}",
            operation="create_windows",
        )

    windows = []
    start = 0
    window_id = 0

    while start + min_required <= n_dates:
        train_start = start
        train_end = start + train_window
        test_start = train_end
        test_end = min(test_start + test_window, n_dates)

        windows.append({
            "window_id": window_id,
            "train_start_idx": train_start,
            "train_end_idx": train_end,
            "test_start_idx": test_start,
            "test_end_idx": test_end,
            "train_start_date": dates[train_start],
            "train_end_date": dates[train_end - 1],
            "test_start_date": dates[test_start],
            "test_end_date": dates[test_end - 1],
        })

        start = test_end
        window_id += 1

    return windows


# =============================================================================
# Window Optimization
# =============================================================================


def _optimize_on_window(
    prices_window: list[list[float]],
    strategy: str = "max_sharpe",
    risk_free_rate: float = 0.05,
    trading_days: int = 365,
) -> list[float]:
    """
    Optimize portfolio weights on a training price window.

    Calculates returns, covariance, and mean returns from the price window,
    then runs the optimizer for the specified strategy.

    Args:
        prices_window: 2D list [n_symbols][n_train_days] of prices.
        strategy: "max_sharpe" or "min_variance".
        risk_free_rate: Risk-free rate for Sharpe calculation.
        trading_days: Trading days per year for annualization.

    Returns:
        Optimal weights.

    Raises:
        BacktestError: If unknown strategy (via optimize_weights).
    """
    returns = calculate_log_returns(prices_window)
    cov_matrix = calculate_covariance_matrix(returns, trading_days)
    mean_returns = calculate_mean_returns(returns, trading_days)

    return optimize_weights(strategy, mean_returns, cov_matrix, risk_free_rate)


# =============================================================================
# Portfolio Returns on Test Period
# =============================================================================


def _compute_portfolio_daily_returns(
    prices_test: list[list[float]],
    weights: list[float],
) -> list[float]:
    """
    Compute daily portfolio returns on test prices.

    Calculates log returns on the test period, then computes
    the weighted sum across assets for each day.

    Args:
        prices_test: 2D list [n_symbols][n_test_days] of prices.
        weights: Portfolio weights [n_symbols].

    Returns:
        List of daily portfolio returns (n_test_days - 1).
    """
    returns = calculate_log_returns(prices_test)
    n_days = len(returns[0])

    portfolio_returns = []
    for t in range(n_days):
        daily_return = sum(weights[i] * returns[i][t] for i in range(len(weights)))
        portfolio_returns.append(daily_return)

    return portfolio_returns


# =============================================================================
# Performance Metrics
# =============================================================================


def _cumulative_values(returns: list[float], initial: float = 1.0) -> list[float]:
    """
    Compute cumulative portfolio values from returns.

    value[t] = initial * exp(sum(returns[0:t]))

    Args:
        returns: List of log returns.
        initial: Initial portfolio value.

    Returns:
        List of cumulative values (length = len(returns) + 1).
    """
    values = [initial]
    cum_return = 0.0
    for r in returns:
        cum_return += r
        values.append(initial * math.exp(cum_return))
    return values


def _max_drawdown(values: list[float]) -> float:
    """
    Compute maximum drawdown from a value series.

    Max drawdown = max((peak - value) / peak) over all time points.

    Args:
        values: List of portfolio values.

    Returns:
        Maximum drawdown as a positive fraction (0 to 1).
    """
    if not values:
        return 0.0

    peak = values[0]
    max_dd = 0.0

    for v in values:
        if v > peak:
            peak = v
        drawdown = (peak - v) / peak if peak > 0 else 0.0
        if drawdown > max_dd:
            max_dd = drawdown

    return max_dd


def _compute_metrics(
    returns: list[float],
    risk_free_rate: float = 0.05,
    trading_days: int = 365,
) -> dict[str, float]:
    """
    Compute performance metrics from a return series.

    Args:
        returns: List of daily log returns.
        risk_free_rate: Annualized risk-free rate.
        trading_days: Trading days per year for annualization.

    Returns:
        Dictionary with cumulative_return, annualized_return,
        max_drawdown, sharpe_ratio, calmar_ratio.
    """
    if not returns:
        return {
            "cumulative_return": 0.0,
            "annualized_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "calmar_ratio": 0.0,
        }

    # Cumulative return
    cum_return = sum(returns)
    cumulative_return = math.exp(cum_return) - 1

    # Annualized return
    n_days = len(returns)
    annualized_return = (math.exp(cum_return) ** (trading_days / n_days)) - 1 if n_days > 0 else 0.0

    # Max drawdown
    values = _cumulative_values(returns)
    max_dd = _max_drawdown(values)

    # Sharpe ratio (annualized)
    daily_rf = risk_free_rate / trading_days
    mean_daily = calculate_mean(returns)
    std_daily = calculate_stddev(returns) if len(returns) > 1 else 0.0
    sharpe = (
        (mean_daily - daily_rf) / std_daily * math.sqrt(trading_days)
        if std_daily > 1e-10
        else 0.0
    )

    # Sortino ratio (annualized, penalizes only downside volatility)
    # Standard formula: downside deviation uses ALL observations in denominator,
    # squaring only negative excess returns (others contribute 0).
    downside_sq = [min(r - daily_rf, 0.0) ** 2 for r in returns]
    if len(returns) > 1:
        downside_dev = math.sqrt(sum(downside_sq) / len(returns))
        sortino = (
            (mean_daily - daily_rf) / downside_dev * math.sqrt(trading_days)
            if downside_dev > 1e-10
            else 0.0
        )
    else:
        sortino = 0.0

    # Calmar ratio
    calmar = annualized_return / abs(max_dd) if abs(max_dd) > 1e-10 else 0.0

    return {
        "cumulative_return": round(cumulative_return, 6),
        "annualized_return": round(annualized_return, 6),
        "max_drawdown": round(max_dd, 6),
        "sharpe_ratio": round(sharpe, 6),
        "sortino_ratio": round(sortino, 6),
        "calmar_ratio": round(calmar, 6),
    }


# =============================================================================
# Main Backtest Function
# =============================================================================


def run_backtest(
    train_window: int = 60,
    test_window: int = 30,
    strategy: str = "max_sharpe",
    storage: Storage | None = None,
    risk_free_rate: float = 0.05,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run walk-forward backtest on portfolio optimization.

    For each rolling window:
    1. Optimize weights on training data
    2. Measure out-of-sample return on test data
    3. Compare against equal-weight and BTC-only benchmarks

    Args:
        train_window: Training window size in days.
        test_window: Test window size in days.
        strategy: Optimization strategy ("max_sharpe" or "min_variance").
        storage: Storage instance. If None, resolves from config.
        risk_free_rate: Risk-free rate.
        save: Whether to save results.

    Returns:
        Dictionary with windows, cumulative values, metrics, and config.

    Raises:
        BacktestError: If backtest fails.
    """
    logger.info("Running walk-forward backtest")
    logger.info(f"Strategy: {strategy}")
    logger.info(f"Train window: {train_window} days")
    logger.info(f"Test window: {test_window} days")

    cfg = load_config()
    if storage is None:
        storage = get_storage(cfg.storage_backend)
    trading_days = cfg.trading_days_per_year

    # Load raw data
    try:
        raw_data = storage.load_raw()
    except Exception as e:
        raise BacktestError(
            f"Failed to load raw data: {e}. Ensure ingest_data() has been run first.",
            operation="load",
        ) from e

    # Align data
    symbols, dates, prices_matrix = align_data_by_date(raw_data)
    n_symbols = len(symbols)
    logger.info(f"Symbols: {symbols}")
    logger.info(f"Data points: {len(dates)}")

    # Create rolling windows
    windows = _create_rolling_windows(dates, prices_matrix, train_window, test_window)
    logger.info(f"Windows: {len(windows)}")

    # Walk-forward loop
    all_strategy_returns: list[float] = []
    all_equal_returns: list[float] = []
    all_btc_returns: list[float] = []
    all_dates: list[str] = []
    window_results: list[dict[str, Any]] = []

    equal_weights = [1.0 / n_symbols] * n_symbols

    # Find BTC index by symbol name instead of assuming position 0
    btc_idx = 0
    for i, sym in enumerate(symbols):
        if "BTC" in sym:
            btc_idx = i
            break
    btc_weights = [0.0] * n_symbols
    btc_weights[btc_idx] = 1.0

    for window in windows:
        ti, te = window["train_start_idx"], window["train_end_idx"]
        tsi, tei = window["test_start_idx"], window["test_end_idx"]

        # Extract price windows
        train_prices = [s[ti:te] for s in prices_matrix]
        test_prices = [s[tsi:tei] for s in prices_matrix]

        # Optimize on training data
        opt_weights = _optimize_on_window(train_prices, strategy, risk_free_rate, trading_days)

        # Compute test returns for all strategies
        strategy_returns = _compute_portfolio_daily_returns(test_prices, opt_weights)
        equal_returns = _compute_portfolio_daily_returns(test_prices, equal_weights)
        btc_returns = _compute_portfolio_daily_returns(test_prices, btc_weights)

        # Accumulate
        all_strategy_returns.extend(strategy_returns)
        all_equal_returns.extend(equal_returns)
        all_btc_returns.extend(btc_returns)

        # Test dates (returns have one less element than prices)
        test_dates = dates[tsi + 1:tei]
        all_dates.extend(test_dates)

        # Test period return
        test_return = sum(strategy_returns)

        window_results.append({
            "window_id": window["window_id"],
            "train_start": window["train_start_date"],
            "train_end": window["train_end_date"],
            "test_start": window["test_start_date"],
            "test_end": window["test_end_date"],
            "weights": {symbols[i]: round(opt_weights[i], 6) for i in range(n_symbols)},
            "test_return": round(test_return, 6),
        })

        logger.info(f"Window {window['window_id']}: test return = {test_return:+.4f}")

    # Build cumulative value series
    strategy_values = _cumulative_values(all_strategy_returns)
    equal_values = _cumulative_values(all_equal_returns)
    btc_values = _cumulative_values(all_btc_returns)

    # Compute metrics
    strategy_metrics = _compute_metrics(all_strategy_returns, risk_free_rate, trading_days)
    equal_metrics = _compute_metrics(all_equal_returns, risk_free_rate, trading_days)
    btc_metrics = _compute_metrics(all_btc_returns, risk_free_rate, trading_days)

    result: dict[str, Any] = {
        "windows": window_results,
        "daily_returns": {
            "strategy": [round(r, 8) for r in all_strategy_returns],
            "equal_weight": [round(r, 8) for r in all_equal_returns],
            "btc_only": [round(r, 8) for r in all_btc_returns],
        },
        "cumulative_values": {
            "dates": all_dates,
            "strategy": [round(v, 6) for v in strategy_values],
            "equal_weight": [round(v, 6) for v in equal_values],
            "btc_only": [round(v, 6) for v in btc_values],
        },
        "metrics": {
            "strategy": strategy_metrics,
            "equal_weight": equal_metrics,
            "btc_only": btc_metrics,
        },
        "symbols": symbols,
        "config": {
            "train_window": train_window,
            "test_window": test_window,
            "strategy": strategy,
            "risk_free_rate": risk_free_rate,
        },
    }

    # Log summary
    logger.info("BACKTEST RESULTS")
    logger.info(f"{'Metric':<25} {'Strategy':>12} {'Equal Wt':>12} {'BTC Only':>12}")
    for metric_name in ["cumulative_return", "annualized_return", "max_drawdown", "sharpe_ratio", "calmar_ratio"]:
        sv = strategy_metrics[metric_name]
        ev = equal_metrics[metric_name]
        bv = btc_metrics[metric_name]
        logger.info(f"{metric_name:<25} {sv:>12.4f} {ev:>12.4f} {bv:>12.4f}")

    if save:
        try:
            output_path = storage.save_output(result, "backtest")
            logger.info(f"Saved backtest to: {output_path}")
        except Exception as e:
            raise BacktestError(
                f"Failed to save backtest results: {e}", operation="save"
            ) from e

    logger.info("Backtest complete")
    return result


def run_yfinance_backtest(
    train_window: int = 60,
    test_window: int = 30,
    strategy: str = "max_sharpe",
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run walk-forward backtest on traditional asset portfolio.

    Same algorithm as crypto backtest, but loads yfinance symbols
    and uses SPY as the single-asset benchmark instead of BTC.
    Saves to ``backtest_trad.json``.

    Args:
        train_window: Training window size in days.
        test_window: Test window size in days.
        strategy: Optimization strategy.
        storage: Storage instance. If None, resolves from config.
        save: Whether to save results.

    Returns:
        Dictionary with windows, cumulative values, metrics, and config.
    """
    logger.info("Running walk-forward backtest (traditional assets)")

    yf_cfg = load_yfinance_config()
    cfg = load_config()
    risk_free_rate = yf_cfg.risk_free_rate
    trading_days = yf_cfg.trading_days_per_year

    if storage is None:
        storage = get_storage(cfg.storage_backend)

    # Load raw data for yfinance symbols
    try:
        raw_data = storage.load_raw(list(yf_cfg.symbols))
    except Exception as e:
        raise BacktestError(
            f"Failed to load yfinance raw data: {e}",
            operation="load",
        ) from e

    symbols, dates, prices_matrix = align_data_by_date(raw_data)
    n_symbols = len(symbols)
    logger.info(f"Trad symbols: {symbols}, data points: {len(dates)}")

    windows = _create_rolling_windows(dates, prices_matrix, train_window, test_window)
    logger.info(f"Windows: {len(windows)}")

    all_strategy_returns: list[float] = []
    all_equal_returns: list[float] = []
    all_spy_returns: list[float] = []
    all_dates: list[str] = []
    window_results: list[dict[str, Any]] = []

    equal_weights = [1.0 / n_symbols] * n_symbols

    # Use SPY as single-asset benchmark (instead of BTC)
    spy_idx = 0
    for i, sym in enumerate(symbols):
        if sym == "SPY":
            spy_idx = i
            break
    spy_weights = [0.0] * n_symbols
    spy_weights[spy_idx] = 1.0

    for window in windows:
        ti, te = window["train_start_idx"], window["train_end_idx"]
        tsi, tei = window["test_start_idx"], window["test_end_idx"]

        train_prices = [s[ti:te] for s in prices_matrix]
        test_prices = [s[tsi:tei] for s in prices_matrix]

        opt_weights = _optimize_on_window(train_prices, strategy, risk_free_rate, trading_days)

        strategy_returns = _compute_portfolio_daily_returns(test_prices, opt_weights)
        equal_returns = _compute_portfolio_daily_returns(test_prices, equal_weights)
        spy_returns = _compute_portfolio_daily_returns(test_prices, spy_weights)

        all_strategy_returns.extend(strategy_returns)
        all_equal_returns.extend(equal_returns)
        all_spy_returns.extend(spy_returns)

        test_dates = dates[tsi + 1:tei]
        all_dates.extend(test_dates)

        test_return = sum(strategy_returns)

        window_results.append({
            "window_id": window["window_id"],
            "train_start": window["train_start_date"],
            "train_end": window["train_end_date"],
            "test_start": window["test_start_date"],
            "test_end": window["test_end_date"],
            "weights": {symbols[i]: round(opt_weights[i], 6) for i in range(n_symbols)},
            "test_return": round(test_return, 6),
        })

    strategy_values = _cumulative_values(all_strategy_returns)
    equal_values = _cumulative_values(all_equal_returns)
    spy_values = _cumulative_values(all_spy_returns)

    strategy_metrics = _compute_metrics(all_strategy_returns, risk_free_rate, trading_days)
    equal_metrics = _compute_metrics(all_equal_returns, risk_free_rate, trading_days)
    spy_metrics = _compute_metrics(all_spy_returns, risk_free_rate, trading_days)

    result: dict[str, Any] = {
        "windows": window_results,
        "daily_returns": {
            "strategy": [round(r, 8) for r in all_strategy_returns],
            "equal_weight": [round(r, 8) for r in all_equal_returns],
            "spy_only": [round(r, 8) for r in all_spy_returns],
        },
        "cumulative_values": {
            "dates": all_dates,
            "strategy": [round(v, 6) for v in strategy_values],
            "equal_weight": [round(v, 6) for v in equal_values],
            "spy_only": [round(v, 6) for v in spy_values],
        },
        "metrics": {
            "strategy": strategy_metrics,
            "equal_weight": equal_metrics,
            "spy_only": spy_metrics,
        },
        "symbols": symbols,
        "config": {
            "train_window": train_window,
            "test_window": test_window,
            "strategy": strategy,
            "risk_free_rate": risk_free_rate,
        },
    }

    if save:
        try:
            storage.save_output(result, "backtest_trad")
        except Exception as e:
            raise BacktestError(
                f"Failed to save trad backtest: {e}", operation="save"
            ) from e

    logger.info("Traditional backtest complete")
    return result


# =============================================================================
# Multi-Strategy Backtest
# =============================================================================

MULTI_STRATEGIES = ["max_sharpe", "hrp", "risk_parity", "min_variance", "max_diversification"]


def run_multi_backtest(
    train_window: int = 60,
    test_window: int = 30,
    strategies: list[str] | None = None,
    storage: Storage | None = None,
    risk_free_rate: float = 0.05,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run walk-forward backtest for multiple optimization strategies.

    Shares the same data loading and window creation, then runs each
    strategy through the same windows for fair comparison.

    Args:
        train_window: Training window size in days.
        test_window: Test window size in days.
        strategies: List of strategy names. Defaults to all 5 supported.
        storage: Storage instance.
        risk_free_rate: Risk-free rate.
        save: Whether to save results.

    Returns:
        Dictionary with per-strategy results, comparison metrics, and config.
    """
    if strategies is None:
        strategies = list(MULTI_STRATEGIES)

    logger.info("Running multi-strategy backtest for: %s", strategies)

    cfg = load_config()
    if storage is None:
        storage = get_storage(cfg.storage_backend)
    trading_days = cfg.trading_days_per_year

    # Load and align data
    try:
        raw_data = storage.load_raw()
    except Exception as e:
        raise BacktestError(
            f"Failed to load raw data: {e}", operation="load"
        ) from e

    symbols, dates, prices_matrix = align_data_by_date(raw_data)
    n_symbols = len(symbols)

    windows = _create_rolling_windows(dates, prices_matrix, train_window, test_window)
    equal_weights = [1.0 / n_symbols] * n_symbols

    # Run each strategy
    strategy_results: dict[str, dict[str, Any]] = {}

    for strat_name in strategies:
        try:
            all_returns: list[float] = []
            all_dates_strat: list[str] = []

            for window in windows:
                ti, te = window["train_start_idx"], window["train_end_idx"]
                tsi, tei = window["test_start_idx"], window["test_end_idx"]

                train_prices = [s[ti:te] for s in prices_matrix]
                test_prices = [s[tsi:tei] for s in prices_matrix]

                opt_weights = _optimize_on_window(
                    train_prices, strat_name, risk_free_rate, trading_days
                )
                daily_rets = _compute_portfolio_daily_returns(test_prices, opt_weights)
                all_returns.extend(daily_rets)
                all_dates_strat.extend(dates[tsi + 1:tei])

            # Cumulative values
            cum = [1.0]
            for r in all_returns:
                cum.append(cum[-1] * (1.0 + r))

            total_return = cum[-1] / cum[0] - 1.0 if cum[0] > 0 else 0.0
            ann_return = total_return * (trading_days / max(len(all_returns), 1))
            vol = _std(all_returns) * (trading_days ** 0.5) if all_returns else 0.0
            sharpe = ann_return / vol if vol > 0 else 0.0

            strategy_results[strat_name] = {
                "cumulative_values": cum,
                "total_return": round(total_return, 6),
                "annualized_return": round(ann_return, 6),
                "volatility": round(vol, 6),
                "sharpe_ratio": round(sharpe, 4),
                "n_periods": len(all_returns),
                "error": None,
            }
        except Exception as e:
            logger.warning("Strategy %s failed: %s", strat_name, e)
            strategy_results[strat_name] = {
                "cumulative_values": [],
                "total_return": None,
                "annualized_return": None,
                "volatility": None,
                "sharpe_ratio": None,
                "n_periods": 0,
                "error": str(e),
            }

    # Equal-weight benchmark
    eq_returns: list[float] = []
    for window in windows:
        tsi, tei = window["test_start_idx"], window["test_end_idx"]
        test_prices = [s[tsi:tei] for s in prices_matrix]
        eq_rets = _compute_portfolio_daily_returns(test_prices, equal_weights)
        eq_returns.extend(eq_rets)

    eq_cum = [1.0]
    for r in eq_returns:
        eq_cum.append(eq_cum[-1] * (1.0 + r))

    eq_total = eq_cum[-1] / eq_cum[0] - 1.0 if eq_cum[0] > 0 else 0.0
    eq_ann = eq_total * (trading_days / max(len(eq_returns), 1))
    eq_vol = _std(eq_returns) * (trading_days ** 0.5) if eq_returns else 0.0
    eq_sharpe = eq_ann / eq_vol if eq_vol > 0 else 0.0

    # Ranking
    ranked = sorted(
        [(name, r) for name, r in strategy_results.items() if r.get("sharpe_ratio") is not None],
        key=lambda x: x[1]["sharpe_ratio"],
        reverse=True,
    )
    ranking = [{"rank": i + 1, "strategy": name, "sharpe_ratio": r["sharpe_ratio"]} for i, (name, r) in enumerate(ranked)]

    result: dict[str, Any] = {
        "strategies": strategy_results,
        "equal_weight": {
            "cumulative_values": eq_cum,
            "total_return": round(eq_total, 6),
            "annualized_return": round(eq_ann, 6),
            "volatility": round(eq_vol, 6),
            "sharpe_ratio": round(eq_sharpe, 4),
        },
        "ranking": ranking,
        "symbols": symbols,
        "n_windows": len(windows),
        "config": {
            "train_window": train_window,
            "test_window": test_window,
            "strategies": strategies,
            "risk_free_rate": risk_free_rate,
        },
        "method": "multi_backtest",
    }

    if save:
        try:
            storage.save_output(result, "backtest_multi")
        except Exception as e:
            raise BacktestError(
                f"Failed to save multi backtest: {e}", operation="save"
            ) from e

    logger.info("Multi-strategy backtest complete: %d strategies, %d windows", len(strategies), len(windows))
    return result


def _std(values: list[float]) -> float:
    """Compute standard deviation of a list of floats."""
    if len(values) < 2:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return variance ** 0.5
