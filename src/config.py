"""
Centralized configuration for the portfolio optimization project.

Loads settings from config.toml with environment variable overrides.
Modules can opt-in gradually — existing module-level constants remain
as fallbacks so nothing breaks.

Usage:
    >>> from src.config import load_config
    >>> cfg = load_config()
    >>> print(cfg.symbols)
    ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Project root = two levels up from this file (src/config.py -> project root)
_PROJECT_ROOT = Path(__file__).parent.parent


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable pipeline configuration."""

    # Portfolio
    symbols: list[str] = field(
        default_factory=lambda: [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"
        ]
    )
    interval: str = "1d"
    period_days: int = 90

    # Paths
    data_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "data")
    reference_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "data" / "reference")

    # API sources
    binance_api_base: str = "https://api.binance.com"
    rate_limit_delay: float = 0.5
    max_retries: int = 3

    # Optimization
    risk_free_rate: float = 0.05
    grid_steps: int = 20
    trading_days_per_year: int = 365

    # Storage
    storage_backend: str = "parquet"


def _read_toml(config_path: Path) -> dict[str, Any]:
    """Read a TOML file and return its contents as a dict."""
    if not config_path.exists():
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def load_config(config_path: Path | None = None) -> PipelineConfig:
    """
    Load configuration from config.toml, overlaid with environment variables.

    Precedence (highest wins):
        1. Environment variables (PORTFOLIO_SYMBOLS, PORTFOLIO_INTERVAL, etc.)
        2. config.toml values
        3. PipelineConfig defaults

    Args:
        config_path: Path to config.toml. Defaults to project root.

    Returns:
        Frozen PipelineConfig dataclass.
    """
    if config_path is None:
        config_path = _PROJECT_ROOT / "config.toml"

    toml_data = _read_toml(config_path)
    portfolio = toml_data.get("portfolio", {})

    # Build kwargs from TOML
    kwargs: dict[str, Any] = {}

    if "symbols" in portfolio:
        kwargs["symbols"] = portfolio["symbols"]
    if "interval" in portfolio:
        kwargs["interval"] = portfolio["interval"]
    if "period_days" in portfolio:
        kwargs["period_days"] = portfolio["period_days"]

    # Environment variable overrides
    env_symbols = os.environ.get("PORTFOLIO_SYMBOLS")
    if env_symbols:
        kwargs["symbols"] = [s.strip() for s in env_symbols.split(",")]

    env_interval = os.environ.get("PORTFOLIO_INTERVAL")
    if env_interval:
        kwargs["interval"] = env_interval

    env_period = os.environ.get("PORTFOLIO_PERIOD_DAYS")
    if env_period:
        kwargs["period_days"] = int(env_period)

    env_backend = os.environ.get("STORAGE_BACKEND")
    if env_backend:
        kwargs["storage_backend"] = env_backend

    env_risk_free = os.environ.get("RISK_FREE_RATE")
    if env_risk_free:
        kwargs["risk_free_rate"] = float(env_risk_free)

    return PipelineConfig(**kwargs)
