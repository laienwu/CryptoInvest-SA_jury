"""
Monte Carlo simulation for portfolio outcome forecasting.

Generates random return paths using multivariate normal distribution
based on historical mean returns and covariance matrix, then computes
percentile bands and risk metrics (VaR, CVaR).

Output:
    {
        "percentiles": {"p5": [...], "p25": [...], "p50": [...], "p75": [...], "p95": [...]},
        "final_values": [1.12, 0.95, ...],
        "var_95": -0.15,
        "cvar_95": -0.22,
        "config": {"n_simulations": 1000, "n_days": 252}
    }
"""

import logging
from typing import Any

import numpy as np

from src.config import load_config
from src.storage import Storage, get_storage

logger = logging.getLogger(__name__)


class MonteCarloError(Exception):
    """Custom exception for Monte Carlo simulation errors."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


def run_monte_carlo(
    n_simulations: int = 1000,
    n_days: int = 252,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run Monte Carlo simulation of portfolio returns.

    Loads optimal weights, mean returns, and covariance from storage,
    then generates random return paths via multivariate normal distribution.

    Args:
        n_simulations: Number of simulation paths to generate.
        n_days: Number of trading days to simulate forward.
        storage: Storage backend. Defaults to configured backend.
        save: Whether to save results to storage.

    Returns:
        Dict with percentiles, final_values, var_95, cvar_95, config.

    Raises:
        MonteCarloError: If required data is missing from storage.
    """
    cfg = load_config()
    if storage is None:
        storage = get_storage(cfg.storage_backend)

    # Load inputs
    try:
        weights_data = storage.load_output("weights")
    except Exception as e:
        raise MonteCarloError(f"Cannot load weights: {e}", operation="load_weights")

    try:
        mean_returns_data = storage.load_processed("mean_returns")
    except Exception as e:
        raise MonteCarloError(f"Cannot load mean_returns: {e}", operation="load_mean_returns")

    try:
        cov_data = storage.load_processed("covariance")
    except Exception as e:
        raise MonteCarloError(f"Cannot load covariance: {e}", operation="load_covariance")

    weights_dict = weights_data.get("weights", {})
    symbols = list(weights_dict.keys())
    n_assets = len(symbols)

    if n_assets == 0:
        raise MonteCarloError("No symbols in weights", operation="validate")

    # Build arrays
    w = np.array([weights_dict[s] for s in symbols])

    mean_ret_map = mean_returns_data.get("mean_returns", {})
    daily_means = np.array([mean_ret_map.get(s, 0.0) for s in symbols])

    cov_symbols = cov_data.get("symbols", [])
    cov_matrix_raw = cov_data.get("matrix", [])

    # Reorder covariance to match weights symbol order
    sym_idx = {s: i for i, s in enumerate(cov_symbols)}
    cov_matrix = np.zeros((n_assets, n_assets))
    for i, si in enumerate(symbols):
        for j, sj in enumerate(symbols):
            if si in sym_idx and sj in sym_idx:
                cov_matrix[i, j] = cov_matrix_raw[sym_idx[si]][sym_idx[sj]]

    logger.info(
        f"Running Monte Carlo: {n_simulations} simulations, {n_days} days, {n_assets} assets"
    )

    # Generate random returns: (n_simulations, n_days, n_assets)
    rng = np.random.default_rng(seed=42)
    random_returns = rng.multivariate_normal(
        daily_means, cov_matrix, size=(n_simulations, n_days)
    )

    # Portfolio returns per day: dot with weights → (n_simulations, n_days)
    portfolio_returns = random_returns @ w

    # Cumulative portfolio value starting at 1.0
    cumulative = np.cumprod(1.0 + portfolio_returns, axis=1)

    # Percentiles at each time step
    percentile_levels = [5, 25, 50, 75, 95]
    percentiles: dict[str, list[float]] = {}
    for p in percentile_levels:
        vals = np.percentile(cumulative, p, axis=0)
        percentiles[f"p{p}"] = [round(float(v), 6) for v in vals]

    # Final values
    final_values = [round(float(v), 6) for v in cumulative[:, -1]]
    final_values_sorted = sorted(final_values)

    # VaR (95%): 5th percentile of final returns (loss from 1.0)
    var_95_idx = max(0, int(n_simulations * 0.05) - 1)
    var_95 = round(float(final_values_sorted[var_95_idx] - 1.0), 6)

    # CVaR (95%): mean of worst 5%
    cutoff = max(1, int(n_simulations * 0.05))
    worst = final_values_sorted[:cutoff]
    cvar_95 = round(float(sum(worst) / len(worst) - 1.0), 6)

    result: dict[str, Any] = {
        "percentiles": percentiles,
        "final_values": final_values,
        "var_95": var_95,
        "cvar_95": cvar_95,
        "symbols": symbols,
        "config": {
            "n_simulations": n_simulations,
            "n_days": n_days,
        },
    }

    if save:
        storage.save_output("monte_carlo", result)
        logger.info("Monte Carlo results saved to storage")

    return result
