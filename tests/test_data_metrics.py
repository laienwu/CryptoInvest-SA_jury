"""Tests for data volume metrics module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.pipeline.data_metrics import (
    DataMetricsError,
    _count_parquet_files,
    _measure_dir_size,
    compute_data_metrics,
)


class TestDataMetricsError:
    def test_message(self):
        err = DataMetricsError("fail")
        assert err.message == "fail"
        assert err.operation is None

    def test_message_and_operation(self):
        err = DataMetricsError("fail", operation="compute")
        assert err.message == "fail"
        assert err.operation == "compute"

    def test_str(self):
        err = DataMetricsError("broken")
        assert str(err) == "broken"


class TestCountParquetFiles:
    def test_no_directory(self, tmp_path):
        assert _count_parquet_files(tmp_path / "nonexistent") == 0

    def test_empty_directory(self, tmp_path):
        assert _count_parquet_files(tmp_path) == 0

    def test_counts_parquet_files(self, tmp_path):
        (tmp_path / "a.parquet").write_bytes(b"data")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.parquet").write_bytes(b"data")
        (tmp_path / "c.json").write_bytes(b"data")
        assert _count_parquet_files(tmp_path) == 2


class TestMeasureDirSize:
    def test_no_directory(self, tmp_path):
        assert _measure_dir_size(tmp_path / "nonexistent") == 0

    def test_measures_total_size(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"hello")  # 5 bytes
        (tmp_path / "b.txt").write_bytes(b"world!")  # 6 bytes
        assert _measure_dir_size(tmp_path) == 11


class TestComputeDataMetrics:
    @pytest.fixture()
    def mock_storage(self):
        storage = MagicMock()
        storage.load_raw.return_value = {
            "BTCUSDT": [
                {"timestamp": "2024-01-01", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 100.0},
                {"timestamp": "2024-01-02", "open": 42500.0, "high": 44000.0, "low": 42000.0, "close": 43500.0, "volume": 150.0},
            ],
            "ETHUSDT": [
                {"timestamp": "2024-01-01", "open": 2200.0, "high": 2300.0, "low": 2100.0, "close": 2250.0, "volume": 500.0},
            ],
        }
        storage.list_processed.return_value = ["returns", "correlation"]
        storage.list_outputs.return_value = ["portfolio"]
        return storage

    def test_total_records(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        assert result["total_records"] == 3

    def test_total_symbols(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        assert result["total_symbols"] == 2

    def test_per_symbol_breakdown(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        assert result["symbols"]["BTCUSDT"]["records"] == 2
        assert result["symbols"]["ETHUSDT"]["records"] == 1

    def test_per_symbol_dates(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        btc = result["symbols"]["BTCUSDT"]
        assert btc["first_date"] == "2024-01-01"
        assert btc["last_date"] == "2024-01-02"

    def test_zones_structure(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        zones = result["zones"]
        assert "raw" in zones
        assert "processed" in zones
        assert "output" in zones

    def test_processed_count(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        assert result["zones"]["processed"]["count"] == 2

    def test_output_count(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        assert result["zones"]["output"]["count"] == 1

    def test_total_size_fields(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        assert "total_size_bytes" in result
        assert "total_size_mb" in result
        assert isinstance(result["total_size_mb"], float)

    def test_partitions_count(self, mock_storage, tmp_path):
        # Create some parquet files
        raw_dir = tmp_path / "raw" / "klines"
        raw_dir.mkdir(parents=True)
        (raw_dir / "a.parquet").write_bytes(b"data")
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        assert result["partitions"] == 1

    def test_freshness_hours(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        assert result["freshness_hours"] is not None
        assert result["freshness_hours"] > 0

    def test_method_field(self, mock_storage, tmp_path):
        result = compute_data_metrics(mock_storage, data_dir=tmp_path)
        assert result["method"] == "data_volume_metrics"

    def test_empty_storage(self, tmp_path):
        storage = MagicMock()
        storage.load_raw.return_value = {}
        storage.list_processed.return_value = []
        storage.list_outputs.return_value = []
        result = compute_data_metrics(storage, data_dir=tmp_path)
        assert result["total_records"] == 0
        assert result["total_symbols"] == 0

    def test_storage_load_failure_raises(self, tmp_path):
        storage = MagicMock()
        storage.load_raw.side_effect = Exception("connection failed")
        with pytest.raises(DataMetricsError, match="Failed to load"):
            compute_data_metrics(storage, data_dir=tmp_path)

    def test_intraday_timestamp_freshness(self, tmp_path):
        storage = MagicMock()
        storage.load_raw.return_value = {
            "BTCUSDT": [
                {"timestamp": "2024-01-01T12:30:00", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 100.0},
            ],
        }
        storage.list_processed.return_value = []
        storage.list_outputs.return_value = []
        result = compute_data_metrics(storage, data_dir=tmp_path)
        assert result["freshness_hours"] is not None
