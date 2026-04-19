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
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
            "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "ATOMUSDT", "FILUSDT",
            "POLUSDT", "NEARUSDT", "AAVEUSDT", "UNIUSDT", "LTCUSDT", "TRXUSDT",
            "ICPUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "INJUSDT",
            "FETUSDT", "RUNEUSDT", "THETAUSDT", "ALGOUSDT", "VETUSDT", "SEIUSDT",
            "GRTUSDT", "DYDXUSDT", "SNXUSDT", "WLDUSDT", "COMPUSDT",
            "SUSHIUSDT", "CRVUSDT", "LDOUSDT", "PENDLEUSDT", "ENSUSDT",
            "SHIBUSDT", "PEPEUSDT", "FLOKIUSDT", "BOMEUSDT",
            "SANDUSDT", "MANAUSDT", "AXSUSDT", "GALAUSDT", "IMXUSDT",
            "RENDERUSDT", "HBARUSDT",
        ]
    )
    interval: str = "1m"
    period_days: int = 30

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
    # US broad market
    "SPY", "QQQ", "IWM", "DIA",
    # International
    "EFA", "VGK", "EEM",
    # Bonds
    "TLT", "BND", "HYG",
    # Commodities
    "GLD", "SLV", "USO",
    # US sectors
    "XLF", "XLE", "XLK", "XLV",
    # Mega caps
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    # Financials
    "JPM", "V", "GS",
    # Healthcare / Consumer
    "JNJ", "PG", "KO",
    # European
    "ASML.AS", "MC.PA", "SAP",
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
# Symbol selector (daily Binance trading-universe builder)
# =============================================================================


@dataclass(frozen=True)
class SymbolSelectorConfig:
    """Immutable configuration for the daily Binance symbol selector."""

    # Ranking / filter thresholds
    min_quote_volume: float = 50_000_000.0
    min_daily_range: float = 0.02
    min_abs_price_change_pct: float = 1.0
    momentum_filter_enabled: bool = True
    top_n: int = 30
    min_universe_size: int = 10

    # Quote/market filters
    quote_asset: str = "USDT"
    leveraged_suffixes: tuple[str, ...] = ("UP", "DOWN", "BULL", "BEAR")
    stablecoin_blocklist: tuple[str, ...] = (
        "USDCUSDT",
        "BUSDUSDT",
        "FDUSDUSDT",
        "TUSDUSDT",
        "DAIUSDT",
        "USDPUSDT",
        "PAXGUSDT",
    )

    # HTTP
    binance_api_base: str = "https://api.binance.com"
    rate_limit_delay: float = 0.5
    max_retries: int = 3


@functools.lru_cache(maxsize=4)
def load_symbol_selector_config(config_path: Path | None = None) -> SymbolSelectorConfig:
    """
    Load symbol selector configuration from the ``[symbol_selector]`` section
    of config.toml, overlaid with ``SELECTOR_*`` environment variables.

    Precedence (highest wins):
        1. Environment variables (SELECTOR_MIN_QUOTE_VOLUME, SELECTOR_TOP_N, ...)
        2. config.toml ``[symbol_selector]`` values
        3. SymbolSelectorConfig defaults
    """
    if config_path is None:
        config_path = _PROJECT_ROOT / "config.toml"

    toml_data = _read_toml(config_path)
    section = toml_data.get("symbol_selector", {})

    kwargs: dict[str, Any] = {}

    _float_keys = ("min_quote_volume", "min_daily_range", "min_abs_price_change_pct", "rate_limit_delay")
    _int_keys = ("top_n", "min_universe_size", "max_retries")
    _str_keys = ("quote_asset", "binance_api_base")
    _tuple_keys = ("leveraged_suffixes", "stablecoin_blocklist")

    for key in _float_keys:
        if key in section:
            kwargs[key] = float(section[key])
    for key in _int_keys:
        if key in section:
            kwargs[key] = int(section[key])
    for key in _str_keys:
        if key in section:
            kwargs[key] = str(section[key])
    for key in _tuple_keys:
        if key in section:
            kwargs[key] = tuple(section[key])
    if "momentum_filter_enabled" in section:
        kwargs["momentum_filter_enabled"] = bool(section["momentum_filter_enabled"])

    env_min_qv = os.environ.get("SELECTOR_MIN_QUOTE_VOLUME")
    if env_min_qv:
        kwargs["min_quote_volume"] = float(env_min_qv)

    env_min_range = os.environ.get("SELECTOR_MIN_DAILY_RANGE")
    if env_min_range:
        kwargs["min_daily_range"] = float(env_min_range)

    env_min_pct = os.environ.get("SELECTOR_MIN_ABS_PRICE_CHANGE_PCT")
    if env_min_pct:
        kwargs["min_abs_price_change_pct"] = float(env_min_pct)

    env_momentum = os.environ.get("SELECTOR_MOMENTUM_FILTER_ENABLED")
    if env_momentum is not None:
        kwargs["momentum_filter_enabled"] = env_momentum.strip().lower() in {"1", "true", "yes"}

    env_top_n = os.environ.get("SELECTOR_TOP_N")
    if env_top_n:
        kwargs["top_n"] = int(env_top_n)

    env_min_size = os.environ.get("SELECTOR_MIN_UNIVERSE_SIZE")
    if env_min_size:
        kwargs["min_universe_size"] = int(env_min_size)

    env_quote = os.environ.get("SELECTOR_QUOTE_ASSET")
    if env_quote:
        kwargs["quote_asset"] = env_quote

    env_blocklist = os.environ.get("SELECTOR_STABLECOIN_BLOCKLIST")
    if env_blocklist:
        kwargs["stablecoin_blocklist"] = tuple(s.strip() for s in env_blocklist.split(",") if s.strip())

    env_suffixes = os.environ.get("SELECTOR_LEVERAGED_SUFFIXES")
    if env_suffixes:
        kwargs["leveraged_suffixes"] = tuple(s.strip() for s in env_suffixes.split(",") if s.strip())

    return SymbolSelectorConfig(**kwargs)


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
