"""
Portfolio stress testing module.

Applies predefined or custom shock scenarios to a portfolio and measures
the impact on value, risk, and individual holdings.

Scenarios:
- Market crash: uniform negative shock across all assets
- Volatility spike: scale covariance matrix by a multiplier
- Sector rotation: shock one group of assets, benefit another
- Custom: user-defined per-asset shocks

Output: data/output/stress_test.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class StressTestError(Exception):
    """Error during stress testing."""

    def __init__(self, message: str, *, operation: str = "stress_test") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


# =============================================================================
# Predefined Scenarios
# =============================================================================

PREDEFINED_SCENARIOS: dict[str, dict[str, Any]] = {
    "crypto_crash": {
        "name": "Crypto Crash",
        "description": "All crypto assets drop 30%, traditional assets drop 5%",
        "shocks": {},  # Filled dynamically based on symbols
        "crypto_shock": -0.30,
        "trad_shock": -0.05,
    },
    "volatility_spike": {
        "name": "Volatility Spike",
        "description": "Covariance scales 2x, expected returns unchanged",
        "cov_multiplier": 2.0,
    },
    "flight_to_safety": {
        "name": "Flight to Safety",
        "description": "Risky assets -20%, gold/bonds +10%",
        "risk_shock": -0.20,
        "safety_shock": 0.10,
        "safety_symbols": ["GLD", "TLT", "SLV"],
    },
    "btc_halving_rally": {
        "name": "BTC Halving Rally",
        "description": "BTC +50%, alts +25%, traditional -5%",
        "btc_shock": 0.50,
        "alt_shock": 0.25,
        "trad_shock": -0.05,
    },
    "black_swan": {
        "name": "Black Swan",
        "description": "All assets drop 40%, correlation goes to 1",
        "uniform_shock": -0.40,
    },
}


def _is_crypto_symbol(symbol: str) -> bool:
    """Check if a symbol is a crypto trading pair."""
    return symbol.endswith("USDT") or symbol.endswith("BUSD")


def _build_shocks(
    scenario: dict[str, Any], symbols: list[str]
) -> dict[str, float]:
    """Build per-asset shock map from a scenario definition."""
    shocks: dict[str, float] = {}

    # Uniform shock
    if "uniform_shock" in scenario:
        for s in symbols:
            shocks[s] = scenario["uniform_shock"]
        return shocks

    # Crypto vs trad split
    if "crypto_shock" in scenario:
        for s in symbols:
            if _is_crypto_symbol(s):
                shocks[s] = scenario["crypto_shock"]
            else:
                shocks[s] = scenario.get("trad_shock", 0.0)
        return shocks

    # Flight to safety
    if "risk_shock" in scenario:
        safety = set(scenario.get("safety_symbols", []))
        for s in symbols:
            if s in safety:
                shocks[s] = scenario["safety_shock"]
            else:
                shocks[s] = scenario["risk_shock"]
        return shocks

    # BTC halving rally
    if "btc_shock" in scenario:
        for s in symbols:
            if s.startswith("BTC"):
                shocks[s] = scenario["btc_shock"]
            elif _is_crypto_symbol(s):
                shocks[s] = scenario.get("alt_shock", 0.0)
            else:
                shocks[s] = scenario.get("trad_shock", 0.0)
        return shocks

    # Custom shocks passed directly
    if "shocks" in scenario and scenario["shocks"]:
        return scenario["shocks"]

    return shocks


def run_stress_test(
    scenario_name: str | None = None,
    custom_shocks: dict[str, float] | None = None,
    portfolio_key: str = "weights",
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run a stress test scenario against the portfolio.

    Args:
        scenario_name: Name of predefined scenario. If None, uses custom_shocks.
        custom_shocks: Per-asset shock values (e.g., {"BTCUSDT": -0.3}).
        portfolio_key: Storage key for portfolio weights.
        storage: Storage instance.
        save: Whether to save results.

    Returns:
        Dictionary with scenario details, per-asset impact, and portfolio impact.

    Raises:
        StressTestError: If scenario or portfolio data is invalid.
    """
    if storage is None:
        storage = get_storage()

    # Load portfolio
    try:
        portfolio = storage.load_output(portfolio_key)
    except (StorageError, FileNotFoundError) as e:
        raise StressTestError(
            f"Portfolio not found (key={portfolio_key})", operation="load"
        ) from e

    weights = portfolio.get("weights", {})
    if not weights:
        raise StressTestError("Portfolio has no weights", operation="validate")

    symbols = list(weights.keys())

    # Resolve scenario
    if scenario_name:
        if scenario_name not in PREDEFINED_SCENARIOS:
            available = ", ".join(PREDEFINED_SCENARIOS.keys())
            raise StressTestError(
                f"Unknown scenario '{scenario_name}'. Available: {available}",
                operation="resolve_scenario",
            )
        scenario = PREDEFINED_SCENARIOS[scenario_name]
        shocks = _build_shocks(scenario, symbols)
        scenario_info = {
            "name": scenario["name"],
            "description": scenario["description"],
            "type": "predefined",
        }
    elif custom_shocks:
        shocks = custom_shocks
        scenario_info = {
            "name": "Custom Scenario",
            "description": f"Custom shocks on {len(custom_shocks)} assets",
            "type": "custom",
        }
    else:
        raise StressTestError(
            "Either scenario_name or custom_shocks must be provided",
            operation="validate",
        )

    # Compute impact
    asset_impacts: list[dict[str, Any]] = []
    total_impact = 0.0

    for symbol in symbols:
        weight = float(weights[symbol])
        shock = shocks.get(symbol, 0.0)
        impact = weight * shock
        total_impact += impact

        asset_impacts.append({
            "symbol": symbol,
            "weight": round(weight, 6),
            "shock": round(shock, 4),
            "impact": round(impact, 6),
            "stressed_weight": round(weight * (1 + shock), 6),
        })

    # Sort by impact (worst first)
    asset_impacts.sort(key=lambda x: x["impact"])

    # Portfolio-level stressed metrics
    original_return = portfolio.get("expected_return", 0.0)
    original_vol = portfolio.get("volatility", 0.0)

    # Try to compute stressed volatility if cov_multiplier scenario
    cov_multiplier = 1.0
    if scenario_name and "cov_multiplier" in PREDEFINED_SCENARIOS.get(scenario_name, {}):
        cov_multiplier = PREDEFINED_SCENARIOS[scenario_name]["cov_multiplier"]

    stressed_vol = original_vol * math.sqrt(cov_multiplier)

    result: dict[str, Any] = {
        "scenario": scenario_info,
        "asset_impacts": asset_impacts,
        "portfolio_impact": {
            "total_return_impact": round(total_impact, 6),
            "original_return": original_return,
            "stressed_return": round(original_return + total_impact, 6),
            "original_volatility": original_vol,
            "stressed_volatility": round(stressed_vol, 6),
            "value_at_risk_1pct": round(
                (original_return + total_impact) - 2.326 * stressed_vol, 6
            ),
        },
        "worst_hit": asset_impacts[0]["symbol"] if asset_impacts else None,
        "best_performer": asset_impacts[-1]["symbol"] if asset_impacts else None,
        "n_assets": len(symbols),
        "portfolio_key": portfolio_key,
    }

    if save:
        storage.save_output("stress_test", result)
        logger.info(
            "Stress test '%s': portfolio impact %.2f%%",
            scenario_info["name"],
            total_impact * 100,
        )

    return result


def list_scenarios() -> list[dict[str, str]]:
    """List all predefined stress test scenarios."""
    return [
        {"id": k, "name": v["name"], "description": v["description"]}
        for k, v in PREDEFINED_SCENARIOS.items()
    ]
