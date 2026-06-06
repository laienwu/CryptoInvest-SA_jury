"""Tests for src/trading/config.py — env/TOML layering and secret handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.trading.config import load_trading_config


def _write_toml(path: Path, contents: str) -> Path:
    path.write_text(contents, encoding="utf-8")
    return path


def test_defaults_when_no_toml_no_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_API_SECRET", "TRADING_DRY_RUN",
        "TRADING_CANDLE_INTERVAL", "TRADING_SMA_SHORT", "TRADING_SMA_LONG",
        "TRADING_RISK_PER_TRADE", "TRADING_STOP_LOSS_PCT", "TRADING_MAX_OPEN_POSITIONS",
        "TRADING_MAX_DAILY_LOSS_PCT", "TRADING_LEDGER_PATH", "TRADING_TESTNET_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)

    cfg = load_trading_config(config_path=tmp_path / "nonexistent.toml")
    assert cfg.dry_run is True
    assert cfg.candle_interval == "5m"
    assert cfg.sma_short == 20
    assert cfg.sma_long == 50
    assert cfg.risk_per_trade == 0.01
    assert cfg.api_key == ""
    assert cfg.api_secret == ""


def test_toml_overrides_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("TRADING_SMA_SHORT", "TRADING_RISK_PER_TRADE", "TRADING_DRY_RUN"):
        monkeypatch.delenv(var, raising=False)

    cfg_path = _write_toml(
        tmp_path / "config.toml",
        """
        [trading]
        sma_short = 7
        sma_long = 25
        risk_per_trade = 0.02
        dry_run = false
        """,
    )
    cfg = load_trading_config(config_path=cfg_path)
    assert cfg.sma_short == 7
    assert cfg.sma_long == 25
    assert cfg.risk_per_trade == 0.02
    assert cfg.dry_run is False


def test_env_overrides_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = _write_toml(
        tmp_path / "config.toml",
        """
        [trading]
        sma_short = 7
        risk_per_trade = 0.02
        """,
    )
    monkeypatch.setenv("TRADING_SMA_SHORT", "11")
    monkeypatch.setenv("TRADING_RISK_PER_TRADE", "0.005")
    monkeypatch.setenv("TRADING_DRY_RUN", "false")

    cfg = load_trading_config(config_path=cfg_path)
    assert cfg.sma_short == 11
    assert cfg.risk_per_trade == 0.005
    assert cfg.dry_run is False


def test_secrets_read_from_env_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # TOML containing api_key must NOT be honored — secrets are env-only.
    cfg_path = _write_toml(
        tmp_path / "config.toml",
        """
        [trading]
        api_key = "should-be-ignored"
        api_secret = "should-be-ignored"
        """,
    )
    monkeypatch.setenv("BINANCE_TESTNET_API_KEY", "env-key")
    monkeypatch.setenv("BINANCE_TESTNET_API_SECRET", "env-secret")

    cfg = load_trading_config(config_path=cfg_path)
    assert cfg.api_key == "env-key"
    assert cfg.api_secret == "env-secret"
