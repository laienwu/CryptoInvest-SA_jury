"""Tests for MinIO (S3-compatible) storage backend."""

import io
import json
import sys
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.storage.base import StorageError


# ---------------------------------------------------------------------------
# Mock the minio pip package at sys.modules level if not installed.
# This allows `from minio import Minio` and `from minio.error import S3Error`
# inside src.storage.minio to resolve without the real package.
# ---------------------------------------------------------------------------

class _MockS3Error(Exception):
    """Fake S3Error that matches the real constructor signature."""
    def __init__(self, code="", message="", resource="", request_id="", host_id="", response=""):
        super().__init__(message)
        self.code = code


def _ensure_minio_mocks():
    """Inject mock minio modules if the real package is not installed."""
    if "minio" not in sys.modules or isinstance(sys.modules["minio"], MagicMock):
        minio_mod = MagicMock()
        error_mod = MagicMock()
        error_mod.S3Error = _MockS3Error
        minio_mod.error = error_mod
        sys.modules["minio"] = minio_mod
        sys.modules["minio.error"] = error_mod


_ensure_minio_mocks()

# Now S3Error resolves from our mock
from minio.error import S3Error  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_klines_parquet(records):
    """Build Parquet bytes from OHLCV records."""
    table = pa.table({
        "timestamp": pa.array([r["timestamp"] for r in records], type=pa.string()),
        "open": pa.array([r["open"] for r in records], type=pa.float64()),
        "high": pa.array([r["high"] for r in records], type=pa.float64()),
        "low": pa.array([r["low"] for r in records], type=pa.float64()),
        "close": pa.array([r["close"] for r in records], type=pa.float64()),
        "volume": pa.array([r["volume"] for r in records], type=pa.float64()),
    })
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


SAMPLE_RECORDS = [
    {"timestamp": "2024-01-01", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0, "volume": 1000.0},
    {"timestamp": "2024-01-02", "open": 105.0, "high": 115.0, "low": 95.0, "close": 110.0, "volume": 1200.0},
]


def _mock_minio_client():
    """Create a mock MinIO client with standard stubs."""
    client = MagicMock()
    client.bucket_exists.return_value = True
    return client


def _make_storage(client):
    """Create MinIOStorage with a pre-mocked client."""
    with patch("src.storage.minio.Minio", return_value=client):
        from src.storage.minio import MinIOStorage
        return MinIOStorage()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMinIOStorageInit:
    def test_creates_bucket_if_missing(self):
        client = _mock_minio_client()
        client.bucket_exists.return_value = False
        _make_storage(client)
        client.make_bucket.assert_called_once_with("portfolio-data")

    def test_skips_bucket_if_exists(self):
        client = _mock_minio_client()
        client.bucket_exists.return_value = True
        _make_storage(client)
        client.make_bucket.assert_not_called()


class TestSaveRaw:
    def test_save_raw_uploads_parquet(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        result = storage.save_raw({"BTCUSDT": SAMPLE_RECORDS})

        assert "raw/klines" in result
        client.put_object.assert_called_once()
        call_args = client.put_object.call_args
        assert call_args[0][1] == "raw/klines/BTCUSDT.parquet"

    def test_save_raw_empty_raises(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        with pytest.raises(StorageError, match="No data provided"):
            storage.save_raw({})

    def test_save_raw_skips_empty_records(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        storage.save_raw({"BTCUSDT": SAMPLE_RECORDS, "ETHUSDT": []})
        assert client.put_object.call_count == 1

    def test_save_raw_with_metadata(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        storage.save_raw({"BTCUSDT": SAMPLE_RECORDS}, metadata={"source": "test"})
        client.put_object.assert_called_once()


class TestLoadRaw:
    def test_load_raw_single_symbol(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        parquet_bytes = _make_klines_parquet(SAMPLE_RECORDS)

        # stat_object succeeds -> object exists
        client.stat_object.return_value = MagicMock()

        # get_object returns response with .read()
        response = MagicMock()
        response.read.return_value = parquet_bytes
        client.get_object.return_value = response

        result = storage.load_raw(["BTCUSDT"])

        assert "BTCUSDT" in result
        assert len(result["BTCUSDT"]) == 2
        assert result["BTCUSDT"][0]["close"] == 105.0

    def test_load_raw_missing_symbol_skipped(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        # First symbol missing, second exists
        def stat_side_effect(bucket, key):
            if "MISSING" in key:
                raise S3Error("NoSuchKey", "Not found", "", "", "", "")
            return MagicMock()

        client.stat_object.side_effect = stat_side_effect

        parquet_bytes = _make_klines_parquet(SAMPLE_RECORDS)
        response = MagicMock()
        response.read.return_value = parquet_bytes
        client.get_object.return_value = response

        result = storage.load_raw(["MISSING", "BTCUSDT"])
        assert "BTCUSDT" in result
        assert "MISSING" not in result

    def test_load_raw_no_symbols_raises(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        client.list_objects.return_value = []

        with pytest.raises(StorageError, match="No raw data found"):
            storage.load_raw()


class TestSaveLoadProcessed:
    def test_save_and_load_matrix(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        matrix_data = {
            "symbols": ["BTC", "ETH"],
            "matrix": [[1.0, 0.5], [0.5, 1.0]],
        }

        # Capture uploaded bytes
        uploaded = {}

        def capture_put(bucket, key, data, length, content_type="application/octet-stream"):
            uploaded[key] = data.read()

        client.put_object.side_effect = capture_put

        storage.save_processed(matrix_data, "correlation")

        # Now load it back
        client.stat_object.return_value = MagicMock()
        response = MagicMock()
        response.read.return_value = uploaded["processed/correlation.parquet"]
        client.get_object.return_value = response

        result = storage.load_processed("correlation")
        assert result["symbols"] == ["BTC", "ETH"]
        assert result["matrix"][0][1] == 0.5

    def test_save_and_load_timeseries(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        ts_data = {
            "symbols": ["BTC"],
            "dates": ["2024-01-01", "2024-01-02"],
            "values": [[0.05, -0.02]],
        }

        uploaded = {}

        def capture_put(bucket, key, data, length, content_type="application/octet-stream"):
            uploaded[key] = data.read()

        client.put_object.side_effect = capture_put

        storage.save_processed(ts_data, "returns")

        client.stat_object.return_value = MagicMock()
        response = MagicMock()
        response.read.return_value = uploaded["processed/returns.parquet"]
        client.get_object.return_value = response

        result = storage.load_processed("returns")
        assert result["symbols"] == ["BTC"]
        assert result["values"][0] == [0.05, -0.02]

    def test_save_processed_empty_raises(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        with pytest.raises(StorageError, match="No data provided"):
            storage.save_processed({}, "test")

    def test_load_processed_not_found_raises(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        client.stat_object.side_effect = S3Error("NoSuchKey", "Not found", "", "", "", "")

        with pytest.raises(StorageError, match="not found"):
            storage.load_processed("missing")


class TestSaveLoadOutput:
    def test_save_and_load_output(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        output_data = {"weights": {"BTC": 0.6, "ETH": 0.4}, "sharpe": 1.5}

        uploaded = {}

        def capture_put(bucket, key, data, length, content_type="application/octet-stream"):
            uploaded[key] = data.read()

        client.put_object.side_effect = capture_put

        storage.save_output(output_data, "weights")

        client.stat_object.return_value = MagicMock()
        response = MagicMock()
        response.read.return_value = uploaded["output/weights.json"]
        client.get_object.return_value = response

        result = storage.load_output("weights")
        assert result["weights"]["BTC"] == 0.6
        assert "_metadata" not in result

    def test_save_output_empty_raises(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        with pytest.raises(StorageError, match="No data provided"):
            storage.save_output({}, "test")

    def test_load_output_not_found_raises(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        client.stat_object.side_effect = S3Error("NoSuchKey", "Not found", "", "", "", "")

        with pytest.raises(StorageError, match="not found"):
            storage.load_output("missing")


class TestListOperations:
    def test_list_raw_symbols(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        obj1 = MagicMock()
        obj1.object_name = "raw/klines/BTCUSDT.parquet"
        obj2 = MagicMock()
        obj2.object_name = "raw/klines/ETHUSDT.parquet"
        client.list_objects.return_value = [obj1, obj2]

        result = storage.list_raw_symbols()
        assert result == ["BTCUSDT", "ETHUSDT"]

    def test_list_processed(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        obj1 = MagicMock()
        obj1.object_name = "processed/returns.parquet"
        client.list_objects.return_value = [obj1]

        result = storage.list_processed()
        assert result == ["returns"]

    def test_list_outputs(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        obj1 = MagicMock()
        obj1.object_name = "output/weights.json"
        client.list_objects.return_value = [obj1]

        result = storage.list_outputs()
        assert result == ["weights"]

    def test_list_empty(self):
        client = _mock_minio_client()
        storage = _make_storage(client)

        client.list_objects.return_value = []

        assert storage.list_raw_symbols() == []
        assert storage.list_processed() == []
        assert storage.list_outputs() == []


class TestRegistration:
    def test_minio_registered_in_factory(self):
        import importlib
        import src.storage as storage_pkg

        # Re-import after minio mock is in sys.modules
        importlib.reload(storage_pkg)
        assert "minio" in storage_pkg.list_available_backends()

    def test_config_has_minio_fields(self):
        from src.config import load_config

        load_config.cache_clear()
        cfg = load_config()
        assert cfg.minio_endpoint == "localhost:9000"
        assert cfg.minio_bucket == "portfolio-data"
