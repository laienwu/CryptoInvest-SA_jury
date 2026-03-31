"""Tests for PySpark transforms module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.spark_transforms import SparkTransformError


class TestSparkTransformError:
    def test_message(self):
        err = SparkTransformError("fail")
        assert err.message == "fail"
        assert err.operation is None

    def test_message_and_operation(self):
        err = SparkTransformError("fail", operation="rolling_correlation")
        assert err.message == "fail"
        assert err.operation == "rolling_correlation"

    def test_str(self):
        err = SparkTransformError("broken")
        assert str(err) == "broken"


# Skip remaining tests if pyspark is not installed
pyspark = pytest.importorskip("pyspark")


def _make_mock_storage(n_dates: int = 30, symbols: list[str] | None = None):
    """Create a mock storage with deterministic price data."""
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    raw_data = {}
    for i, sym in enumerate(symbols):
        base_price = 100.0 * (i + 1)
        records = []
        for d in range(n_dates):
            records.append({
                "timestamp": f"2024-01-{d + 1:02d}",
                "open": base_price + d,
                "high": base_price + d + 5,
                "low": base_price + d - 5,
                "close": base_price + d + 1,
                "volume": 1000.0 + d * 10,
            })
        raw_data[sym] = records

    storage = MagicMock()
    storage.load_raw.return_value = raw_data
    return storage


class TestSparkRollingCorrelation:
    def test_returns_correct_structure(self):
        from src.pipeline.spark_transforms import spark_rolling_correlation, _stop_spark
        try:
            storage = _make_mock_storage()
            result = spark_rolling_correlation(storage, window=5)
            assert "pairs" in result
            assert "window" in result
            assert "n_periods" in result
            assert result["window"] == 5
            assert len(result["pairs"]) == 3  # 3 choose 2
        finally:
            _stop_spark()

    def test_pair_fields(self):
        from src.pipeline.spark_transforms import spark_rolling_correlation, _stop_spark
        try:
            storage = _make_mock_storage()
            result = spark_rolling_correlation(storage, window=5)
            pair = result["pairs"][0]
            assert "pair" in pair
            assert "symbol_a" in pair
            assert "symbol_b" in pair
            assert "correlations" in pair
            assert isinstance(pair["correlations"], list)
        finally:
            _stop_spark()

    def test_too_few_symbols_raises(self):
        from src.pipeline.spark_transforms import spark_rolling_correlation, _stop_spark
        try:
            storage = _make_mock_storage(symbols=["BTCUSDT"])
            with pytest.raises(SparkTransformError, match="at least 2"):
                spark_rolling_correlation(storage)
        finally:
            _stop_spark()

    def test_empty_storage_raises(self):
        from src.pipeline.spark_transforms import spark_rolling_correlation, _stop_spark
        try:
            storage = MagicMock()
            storage.load_raw.return_value = {}
            with pytest.raises(SparkTransformError, match="No raw data"):
                spark_rolling_correlation(storage)
        finally:
            _stop_spark()


class TestSparkVolatilitySurface:
    def test_returns_correct_structure(self):
        from src.pipeline.spark_transforms import spark_volatility_surface, _stop_spark
        try:
            storage = _make_mock_storage(n_dates=100)
            result = spark_volatility_surface(storage, windows=[7, 14])
            assert "symbols" in result
            assert "windows" in result
            assert "surface" in result
            assert result["windows"] == [7, 14]
            assert len(result["symbols"]) == 3
        finally:
            _stop_spark()

    def test_surface_has_all_symbols(self):
        from src.pipeline.spark_transforms import spark_volatility_surface, _stop_spark
        try:
            storage = _make_mock_storage(n_dates=50)
            result = spark_volatility_surface(storage, windows=[7])
            for sym in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
                assert sym in result["surface"]
        finally:
            _stop_spark()


class TestSparkVolumeAnalysis:
    def test_returns_correct_structure(self):
        from src.pipeline.spark_transforms import spark_volume_analysis, _stop_spark
        try:
            storage = _make_mock_storage()
            result = spark_volume_analysis(storage)
            assert "per_symbol" in result
            assert "n_symbols" in result
            assert "method" in result
            assert result["n_symbols"] == 3
        finally:
            _stop_spark()

    def test_per_symbol_fields(self):
        from src.pipeline.spark_transforms import spark_volume_analysis, _stop_spark
        try:
            storage = _make_mock_storage()
            result = spark_volume_analysis(storage)
            btc = result["per_symbol"]["BTCUSDT"]
            assert "total_volume" in btc
            assert "mean_volume" in btc
            assert "max_volume" in btc
            assert "vwap" in btc
            assert "n_records" in btc
        finally:
            _stop_spark()

    def test_empty_storage_raises(self):
        from src.pipeline.spark_transforms import spark_volume_analysis, _stop_spark
        try:
            storage = MagicMock()
            storage.load_raw.return_value = {}
            with pytest.raises(SparkTransformError, match="No raw data"):
                spark_volume_analysis(storage)
        finally:
            _stop_spark()
