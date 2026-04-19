"""
Tests for centralized configuration module.

Tests:
- Default values when no config file
- TOML loading
- Environment variable overrides
- Frozen dataclass immutability
"""

from pathlib import Path

import pytest

from src.config import (
    PipelineConfig,
    SymbolSelectorConfig,
    YFinanceConfig,
    load_config,
    load_symbol_selector_config,
    load_yfinance_config,
)


class TestDefaults:
    """Tests for PipelineConfig default values."""

    def test_default_symbols(self):
        cfg = PipelineConfig()
        assert len(cfg.symbols) == 51
        assert "BTCUSDT" in cfg.symbols
        assert "HBARUSDT" in cfg.symbols

    def test_default_interval(self):
        cfg = PipelineConfig()
        assert cfg.interval == "1m"

    def test_default_period_days(self):
        cfg = PipelineConfig()
        assert cfg.period_days == 30

    def test_default_risk_free_rate(self):
        cfg = PipelineConfig()
        assert cfg.risk_free_rate == 0.05

    def test_default_storage_backend(self):
        cfg = PipelineConfig()
        assert cfg.storage_backend == "parquet"

    def test_default_paths_are_paths(self):
        cfg = PipelineConfig()
        assert isinstance(cfg.data_dir, Path)
        assert isinstance(cfg.reference_dir, Path)

    def test_frozen(self):
        cfg = PipelineConfig()
        with pytest.raises(AttributeError):
            cfg.interval = "1h"


class TestLoadFromToml:
    """Tests for loading config from TOML files."""

    def test_load_from_toml(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(
            '[portfolio]\nsymbols = ["BTCUSDT"]\ninterval = "4h"\nperiod_days = 30\n'
        )
        cfg = load_config(toml_file)
        assert cfg.symbols == ["BTCUSDT"]
        assert cfg.interval == "4h"
        assert cfg.period_days == 30

    def test_missing_file_uses_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "nonexistent.toml")
        assert len(cfg.symbols) == 51
        assert cfg.interval == "1m"

    def test_partial_toml_merges_with_defaults(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('[portfolio]\ninterval = "1h"\n')
        cfg = load_config(toml_file)
        assert cfg.interval == "1h"
        # Other values stay default
        assert cfg.period_days == 30
        assert cfg.risk_free_rate == 0.05

    def test_empty_toml_uses_defaults(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text("")
        cfg = load_config(toml_file)
        assert cfg.interval == "1m"


class TestEnvVarOverrides:
    """Tests for environment variable overrides."""

    def test_env_symbols(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTFOLIO_SYMBOLS", "BTCUSDT, ETHUSDT")
        cfg = load_config(tmp_path / "missing.toml")
        assert cfg.symbols == ["BTCUSDT", "ETHUSDT"]

    def test_env_interval(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTFOLIO_INTERVAL", "1h")
        cfg = load_config(tmp_path / "missing.toml")
        assert cfg.interval == "1h"

    def test_env_period_days(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTFOLIO_PERIOD_DAYS", "30")
        cfg = load_config(tmp_path / "missing.toml")
        assert cfg.period_days == 30

    def test_env_storage_backend(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "duckdb")
        cfg = load_config(tmp_path / "missing.toml")
        assert cfg.storage_backend == "duckdb"

    def test_env_risk_free_rate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RISK_FREE_RATE", "0.03")
        cfg = load_config(tmp_path / "missing.toml")
        assert cfg.risk_free_rate == 0.03

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        """Env vars take precedence over TOML values."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('[portfolio]\ninterval = "4h"\n')
        monkeypatch.setenv("PORTFOLIO_INTERVAL", "15m")
        cfg = load_config(toml_file)
        assert cfg.interval == "15m"


# =============================================================================
# YFinanceConfig
# =============================================================================


class TestYFinanceDefaults:
    """Tests for YFinanceConfig default values."""

    def test_default_symbols(self):
        cfg = YFinanceConfig()
        assert "SPY" in cfg.symbols
        assert "GLD" in cfg.symbols
        assert len(cfg.symbols) == 33

    def test_default_trading_days(self):
        cfg = YFinanceConfig()
        assert cfg.trading_days_per_year == 252

    def test_default_period_days(self):
        cfg = YFinanceConfig()
        assert cfg.period_days == 365

    def test_default_risk_free_rate(self):
        cfg = YFinanceConfig()
        assert cfg.risk_free_rate == 0.05

    def test_frozen(self):
        cfg = YFinanceConfig()
        with pytest.raises(AttributeError):
            cfg.period_days = 180


class TestYFinanceLoadFromToml:
    """Tests for loading yfinance config from TOML."""

    def test_load_from_toml(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(
            '[yfinance]\nsymbols = ["AAPL", "MSFT"]\nperiod_days = 180\n'
        )
        cfg = load_yfinance_config(toml_file)
        assert cfg.symbols == ["AAPL", "MSFT"]
        assert cfg.period_days == 180

    def test_missing_file_uses_defaults(self, tmp_path):
        cfg = load_yfinance_config(tmp_path / "nonexistent.toml")
        assert len(cfg.symbols) == 33
        assert cfg.trading_days_per_year == 252

    def test_partial_toml_merges_with_defaults(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('[yfinance]\nperiod_days = 180\n')
        cfg = load_yfinance_config(toml_file)
        assert cfg.period_days == 180
        assert cfg.trading_days_per_year == 252


class TestYFinanceEnvVarOverrides:
    """Tests for yfinance environment variable overrides."""

    def test_env_symbols(self, tmp_path, monkeypatch):
        monkeypatch.setenv("YFINANCE_SYMBOLS", "AAPL, MSFT, TSLA")
        cfg = load_yfinance_config(tmp_path / "missing.toml")
        assert cfg.symbols == ["AAPL", "MSFT", "TSLA"]

    def test_env_period_days(self, tmp_path, monkeypatch):
        monkeypatch.setenv("YFINANCE_PERIOD_DAYS", "180")
        cfg = load_yfinance_config(tmp_path / "missing.toml")
        assert cfg.period_days == 180

    def test_env_risk_free_rate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("YFINANCE_RISK_FREE_RATE", "0.04")
        cfg = load_yfinance_config(tmp_path / "missing.toml")
        assert cfg.risk_free_rate == 0.04

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('[yfinance]\nperiod_days = 180\n')
        monkeypatch.setenv("YFINANCE_PERIOD_DAYS", "90")
        cfg = load_yfinance_config(toml_file)
        assert cfg.period_days == 90


class TestSymbolSelectorDefaults:
    """Defaults for the daily symbol-selector config."""

    def test_default_thresholds(self):
        cfg = SymbolSelectorConfig()
        assert cfg.min_quote_volume == 50_000_000.0
        assert cfg.min_daily_range == 0.02
        assert cfg.min_abs_price_change_pct == 1.0
        assert cfg.top_n == 30
        assert cfg.min_universe_size == 10
        assert cfg.momentum_filter_enabled is True

    def test_default_quote_asset_and_suffixes(self):
        cfg = SymbolSelectorConfig()
        assert cfg.quote_asset == "USDT"
        assert cfg.leveraged_suffixes == ("UP", "DOWN", "BULL", "BEAR")
        assert "USDCUSDT" in cfg.stablecoin_blocklist

    def test_frozen(self):
        cfg = SymbolSelectorConfig()
        with pytest.raises(AttributeError):
            cfg.top_n = 10


class TestSymbolSelectorLoadFromToml:
    """Loading [symbol_selector] config from TOML."""

    def test_load_overrides(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(
            "[symbol_selector]\n"
            "min_quote_volume = 100000000\n"
            "top_n = 25\n"
            "momentum_filter_enabled = false\n"
            'leveraged_suffixes = ["UP", "DOWN"]\n'
        )
        cfg = load_symbol_selector_config(toml_file)
        assert cfg.min_quote_volume == 100_000_000.0
        assert cfg.top_n == 25
        assert cfg.momentum_filter_enabled is False
        assert cfg.leveraged_suffixes == ("UP", "DOWN")

    def test_missing_file_uses_defaults(self, tmp_path):
        cfg = load_symbol_selector_config(tmp_path / "nonexistent.toml")
        assert cfg.top_n == 30
        assert cfg.quote_asset == "USDT"

    def test_partial_toml_merges_with_defaults(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text("[symbol_selector]\ntop_n = 15\n")
        cfg = load_symbol_selector_config(toml_file)
        assert cfg.top_n == 15
        assert cfg.min_quote_volume == 50_000_000.0


class TestSymbolSelectorEnvOverrides:
    """Environment-variable overrides for the selector config."""

    def test_env_min_quote_volume(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SELECTOR_MIN_QUOTE_VOLUME", "75000000")
        cfg = load_symbol_selector_config(tmp_path / "missing.toml")
        assert cfg.min_quote_volume == 75_000_000.0

    def test_env_top_n(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SELECTOR_TOP_N", "20")
        cfg = load_symbol_selector_config(tmp_path / "missing.toml")
        assert cfg.top_n == 20

    def test_env_momentum_filter_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SELECTOR_MOMENTUM_FILTER_ENABLED", "false")
        cfg = load_symbol_selector_config(tmp_path / "missing.toml")
        assert cfg.momentum_filter_enabled is False

    def test_env_stablecoin_blocklist(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SELECTOR_STABLECOIN_BLOCKLIST", "USDCUSDT, TUSDUSDT")
        cfg = load_symbol_selector_config(tmp_path / "missing.toml")
        assert cfg.stablecoin_blocklist == ("USDCUSDT", "TUSDUSDT")

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        toml_file = tmp_path / "config.toml"
        toml_file.write_text("[symbol_selector]\ntop_n = 40\n")
        monkeypatch.setenv("SELECTOR_TOP_N", "15")
        cfg = load_symbol_selector_config(toml_file)
        assert cfg.top_n == 15
