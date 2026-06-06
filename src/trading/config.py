"""
Configuration for the automated trading tick.

Secrets (API key/secret) load from environment only — never TOML.
Non-secret knobs layer as: env > config.toml [trading] > dataclass defaults.
"""

from __future__ import annotations

import functools
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_TESTNET_BASE_URL = "https://testnet.binance.vision"


@dataclass(frozen=True)
class TradingConfig:
    """Immutable trading configuration. Testnet is enforced elsewhere."""

    # Credentials (env-only)
    api_key: str = ""
    api_secret: str = ""

    # Posture
    dry_run: bool = True
    testnet_base_url: str = _TESTNET_BASE_URL

    # Market data
    candle_interval: str = "5m"
    candle_lookback: int = 120  # bars fetched per symbol per tick

    # Strategy
    sma_short: int = 20
    sma_long: int = 50

    # Risk
    risk_per_trade: float = 0.01
    stop_loss_pct: float = 0.03
    max_open_positions: int = 10
    max_daily_loss_pct: float = 0.05
    min_equity_floor_usdt: float = 100.0
    max_cost_fraction_of_risk: float = 0.20
    post_stop_cooldown_minutes: int = 60  # re-entry lockout after a stop fill

    # Persistence
    ledger_path: Path = _PROJECT_ROOT / "data" / "trading" / "ledger.duckdb"

    # HTTP
    rate_limit_delay: float = 0.5
    max_retries: int = 3
    recv_window_ms: int = 5000


def _read_toml(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def _env_bool(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@functools.lru_cache(maxsize=4)
def load_trading_config(config_path: Path | None = None) -> TradingConfig:
    """Load TradingConfig from env + config.toml, with env taking precedence."""
    if config_path is None:
        config_path = _PROJECT_ROOT / "config.toml"

    toml_data = _read_toml(config_path)
    section = toml_data.get("trading", {})

    kwargs: dict[str, Any] = {}

    _float_keys = (
        "risk_per_trade",
        "stop_loss_pct",
        "max_daily_loss_pct",
        "min_equity_floor_usdt",
        "max_cost_fraction_of_risk",
        "rate_limit_delay",
    )
    _int_keys = ("candle_lookback", "sma_short", "sma_long", "max_open_positions",
                 "max_retries", "recv_window_ms", "post_stop_cooldown_minutes")
    _str_keys = ("candle_interval",)

    for key in _float_keys:
        if key in section:
            kwargs[key] = float(section[key])
    for key in _int_keys:
        if key in section:
            kwargs[key] = int(section[key])
    for key in _str_keys:
        if key in section:
            kwargs[key] = str(section[key])
    if "dry_run" in section:
        kwargs["dry_run"] = bool(section["dry_run"])
    if "ledger_path" in section:
        kwargs["ledger_path"] = Path(str(section["ledger_path"]))

    # Secrets via env ONLY
    kwargs["api_key"] = os.environ.get("BINANCE_TESTNET_API_KEY", "")
    kwargs["api_secret"] = os.environ.get("BINANCE_TESTNET_API_SECRET", "")

    env_dry = _env_bool("TRADING_DRY_RUN")
    if env_dry is not None:
        kwargs["dry_run"] = env_dry

    env_interval = os.environ.get("TRADING_CANDLE_INTERVAL")
    if env_interval:
        kwargs["candle_interval"] = env_interval

    for env_name, key, caster in (
        ("TRADING_CANDLE_LOOKBACK", "candle_lookback", int),
        ("TRADING_SMA_SHORT", "sma_short", int),
        ("TRADING_SMA_LONG", "sma_long", int),
        ("TRADING_RISK_PER_TRADE", "risk_per_trade", float),
        ("TRADING_STOP_LOSS_PCT", "stop_loss_pct", float),
        ("TRADING_MAX_OPEN_POSITIONS", "max_open_positions", int),
        ("TRADING_MAX_DAILY_LOSS_PCT", "max_daily_loss_pct", float),
        ("TRADING_MIN_EQUITY_FLOOR_USDT", "min_equity_floor_usdt", float),
        ("TRADING_POST_STOP_COOLDOWN_MINUTES", "post_stop_cooldown_minutes", int),
    ):
        raw = os.environ.get(env_name)
        if raw:
            kwargs[key] = caster(raw)

    env_ledger = os.environ.get("TRADING_LEDGER_PATH")
    if env_ledger:
        kwargs["ledger_path"] = Path(env_ledger)

    env_base = os.environ.get("TRADING_TESTNET_BASE_URL")
    if env_base:
        kwargs["testnet_base_url"] = env_base

    return TradingConfig(**kwargs)
