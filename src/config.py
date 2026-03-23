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

import functools
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
    trading_days_per_year: int = 365

    # Storage
    storage_backend: str = "parquet"

    # MinIO (S3-compatible)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "portfolio-data"


def _read_toml(config_path: Path) -> dict[str, Any]:
    """Read a TOML file and return its contents as a dict."""
    if not config_path.exists():
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)


@functools.lru_cache(maxsize=4)
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
    if "risk_free_rate" in portfolio:
        kwargs["risk_free_rate"] = portfolio["risk_free_rate"]
    if "trading_days_per_year" in portfolio:
        kwargs["trading_days_per_year"] = portfolio["trading_days_per_year"]
    if "storage_backend" in portfolio:
        kwargs["storage_backend"] = portfolio["storage_backend"]

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

    env_minio_endpoint = os.environ.get("MINIO_ENDPOINT")
    if env_minio_endpoint:
        kwargs["minio_endpoint"] = env_minio_endpoint

    env_minio_access = os.environ.get("MINIO_ACCESS_KEY")
    if env_minio_access:
        kwargs["minio_access_key"] = env_minio_access

    env_minio_secret = os.environ.get("MINIO_SECRET_KEY")
    if env_minio_secret:
        kwargs["minio_secret_key"] = env_minio_secret

    env_minio_bucket = os.environ.get("MINIO_BUCKET")
    if env_minio_bucket:
        kwargs["minio_bucket"] = env_minio_bucket

    env_risk_free = os.environ.get("RISK_FREE_RATE")
    if env_risk_free:
        kwargs["risk_free_rate"] = float(env_risk_free)

    return PipelineConfig(**kwargs)


# =============================================================================
# yfinance configuration (traditional assets — stocks, ETFs, commodities)
# =============================================================================

_DEFAULT_YFINANCE_SYMBOLS = [
    "SPY",      # S&P 500 (US)
    "EFA",      # MSCI EAFE (Europe/Asia)
    "GLD",      # Gold
    "SLV",      # Silver
    "TLT",      # US Treasury Bonds 20y
    "AAPL",     # Apple (US)
    "MSFT",     # Microsoft (US)
    "ASML.AS",  # ASML (Europe/Amsterdam)
    "MC.PA",    # LVMH (Europe/Paris)
    "SAP.DE",   # SAP (Europe/Frankfurt)
]


@dataclass(frozen=True)
class YFinanceConfig:
    """Immutable configuration for traditional asset tracking via yfinance."""

    symbols: list[str] = field(default_factory=lambda: list(_DEFAULT_YFINANCE_SYMBOLS))
    trading_days_per_year: int = 252
    period_days: int = 365
    risk_free_rate: float = 0.05


@functools.lru_cache(maxsize=4)
def load_yfinance_config(config_path: Path | None = None) -> YFinanceConfig:
    """
    Load yfinance configuration from ``[yfinance]`` section of config.toml.

    Precedence (highest wins):
        1. Environment variables (YFINANCE_SYMBOLS, YFINANCE_PERIOD_DAYS)
        2. config.toml ``[yfinance]`` values
        3. YFinanceConfig defaults

    Args:
        config_path: Path to config.toml. Defaults to project root.

    Returns:
        Frozen YFinanceConfig dataclass.
    """
    if config_path is None:
        config_path = _PROJECT_ROOT / "config.toml"

    toml_data = _read_toml(config_path)
    yfinance = toml_data.get("yfinance", {})

    kwargs: dict[str, Any] = {}

    if "symbols" in yfinance:
        kwargs["symbols"] = yfinance["symbols"]
    if "trading_days_per_year" in yfinance:
        kwargs["trading_days_per_year"] = yfinance["trading_days_per_year"]
    if "period_days" in yfinance:
        kwargs["period_days"] = yfinance["period_days"]
    if "risk_free_rate" in yfinance:
        kwargs["risk_free_rate"] = yfinance["risk_free_rate"]

    env_symbols = os.environ.get("YFINANCE_SYMBOLS")
    if env_symbols:
        kwargs["symbols"] = [s.strip() for s in env_symbols.split(",")]

    env_period = os.environ.get("YFINANCE_PERIOD_DAYS")
    if env_period:
        kwargs["period_days"] = int(env_period)

    env_risk_free = os.environ.get("YFINANCE_RISK_FREE_RATE")
    if env_risk_free:
        kwargs["risk_free_rate"] = float(env_risk_free)

    return YFinanceConfig(**kwargs)


# =============================================================================
# Database configuration (infrastructure, separate from pipeline parameters)
# =============================================================================


@dataclass(frozen=True)
class DatabaseConfig:
    """Immutable PostgreSQL connection configuration."""

    host: str = "localhost"
    port: int = 5432
    database: str = "portfolio_benchmarks"
    user: str = "portfolio"
    password: str = ""


def load_db_config(config_path: Path | None = None) -> DatabaseConfig:
    """
    Load database configuration from config.toml ``[database]`` section,
    overlaid with ``BENCHMARKS_DB_*`` environment variables.

    Precedence (highest wins):
        1. Environment variables (BENCHMARKS_DB_HOST, BENCHMARKS_DB_PORT, etc.)
        2. config.toml ``[database]`` values
        3. DatabaseConfig defaults

    Args:
        config_path: Path to config.toml. Defaults to project root.

    Returns:
        Frozen DatabaseConfig dataclass.
    """
    if config_path is None:
        config_path = _PROJECT_ROOT / "config.toml"

    toml_data = _read_toml(config_path)
    database = toml_data.get("database", {})

    kwargs: dict[str, Any] = {}

    if "host" in database:
        kwargs["host"] = database["host"]
    if "port" in database:
        kwargs["port"] = int(database["port"])
    if "database" in database:
        kwargs["database"] = database["database"]
    if "user" in database:
        kwargs["user"] = database["user"]
    if "password" in database:
        kwargs["password"] = database["password"]

    env_host = os.environ.get("BENCHMARKS_DB_HOST")
    if env_host:
        kwargs["host"] = env_host

    env_port = os.environ.get("BENCHMARKS_DB_PORT")
    if env_port:
        kwargs["port"] = int(env_port)

    env_db = os.environ.get("BENCHMARKS_DB_NAME")
    if env_db:
        kwargs["database"] = env_db

    env_user = os.environ.get("BENCHMARKS_DB_USER")
    if env_user:
        kwargs["user"] = env_user

    env_password = os.environ.get("BENCHMARKS_DB_PASSWORD")
    if env_password:
        kwargs["password"] = env_password

    return DatabaseConfig(**kwargs)
