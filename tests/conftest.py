"""
Pytest fixtures for portfolio optimization tests.

Provides reusable test data and mock objects.
"""

from pathlib import Path

import pytest

from src.config import load_config


@pytest.fixture(autouse=True)
def _clear_config_cache() -> None:
    """Clear load_config LRU cache between tests."""
    load_config.cache_clear()


@pytest.fixture
def sample_prices() -> list[list[float]]:
    """Sample price matrix for 3 symbols over 10 days."""
    return [
        [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 110.0],  # BTC
        [50.0, 51.0, 49.0, 52.0, 53.0, 51.0, 54.0, 55.0, 53.0, 56.0],  # ETH
        [10.0, 10.2, 10.1, 10.3, 10.5, 10.4, 10.6, 10.8, 10.7, 11.0],  # BNB
    ]


@pytest.fixture
def sample_returns() -> list[list[float]]:
    """Pre-calculated log returns for sample_prices."""
    import math

    prices = [
        [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 110.0],
        [50.0, 51.0, 49.0, 52.0, 53.0, 51.0, 54.0, 55.0, 53.0, 56.0],
        [10.0, 10.2, 10.1, 10.3, 10.5, 10.4, 10.6, 10.8, 10.7, 11.0],
    ]
    returns = []
    for symbol_prices in prices:
        symbol_returns = [
            math.log(symbol_prices[i] / symbol_prices[i - 1])
            for i in range(1, len(symbol_prices))
        ]
        returns.append(symbol_returns)
    return returns


@pytest.fixture
def sample_raw_data() -> dict[str, list[dict]]:
    """Sample raw OHLCV data for testing."""
    dates = [f"2024-01-{i:02d}" for i in range(1, 11)]
    btc_prices = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 110.0]
    eth_prices = [50.0, 51.0, 49.0, 52.0, 53.0, 51.0, 54.0, 55.0, 53.0, 56.0]

    return {
        "BTCUSDT": [
            {
                "timestamp": dates[i],
                "open": btc_prices[i] - 1,
                "high": btc_prices[i] + 2,
                "low": btc_prices[i] - 2,
                "close": btc_prices[i],
                "volume": 1000000.0,
            }
            for i in range(10)
        ],
        "ETHUSDT": [
            {
                "timestamp": dates[i],
                "open": eth_prices[i] - 0.5,
                "high": eth_prices[i] + 1,
                "low": eth_prices[i] - 1,
                "close": eth_prices[i],
                "volume": 500000.0,
            }
            for i in range(10)
        ],
    }


@pytest.fixture
def sample_covariance_matrix() -> list[list[float]]:
    """Sample covariance matrix for 3 assets."""
    return [
        [0.04, 0.02, 0.01],  # BTC variance and covariances
        [0.02, 0.09, 0.015],  # ETH variance and covariances
        [0.01, 0.015, 0.0225],  # BNB variance and covariances
    ]


@pytest.fixture
def sample_mean_returns() -> list[float]:
    """Sample annualized mean returns for 3 assets."""
    return [0.15, 0.20, 0.10]  # 15%, 20%, 10%


@pytest.fixture
def sample_weights() -> list[float]:
    """Sample portfolio weights (equal weight)."""
    return [1 / 3, 1 / 3, 1 / 3]


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Create temporary data directory structure."""
    raw_dir = tmp_path / "raw" / "klines"
    processed_dir = tmp_path / "processed"
    output_dir = tmp_path / "output"

    raw_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    return tmp_path


@pytest.fixture
def sample_portfolio_result() -> dict:
    """Sample portfolio optimization result."""
    return {
        "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        "weights": {"BTCUSDT": 0.4, "ETHUSDT": 0.35, "BNBUSDT": 0.25},
        "weights_list": [0.4, 0.35, 0.25],
        "expected_return": 0.18,
        "volatility": 0.25,
        "sharpe_ratio": 0.52,
        "risk_free_rate": 0.05,
        "method": "scipy",
    }


@pytest.fixture
def sample_correlation_matrix() -> list[list[float]]:
    """Sample correlation matrix for 3 assets."""
    return [
        [1.0, 0.7, 0.5],
        [0.7, 1.0, 0.6],
        [0.5, 0.6, 1.0],
    ]


@pytest.fixture
def sample_volatility() -> list[float]:
    """Sample annualized volatilities for 3 assets."""
    return [0.45, 0.55, 0.35]  # 45%, 55%, 35%
