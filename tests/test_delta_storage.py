"""Tests for Delta Lake storage backend."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.storage.delta import DeltaStorageError


class TestDeltaStorageError:
    def test_message(self):
        err = DeltaStorageError("fail")
        assert err.message == "fail"
        assert err.operation is None

    def test_message_and_operation(self):
        err = DeltaStorageError("fail", operation="save_raw")
        assert err.message == "fail"
        assert err.operation == "save_raw"

    def test_str(self):
        err = DeltaStorageError("broken")
        assert str(err) == "broken"


# Skip all remaining tests if deltalake is not installed
deltalake = pytest.importorskip("deltalake")


class TestDeltaStorage:
    """Integration tests — require the deltalake package."""

    @pytest.fixture()
    def storage(self, tmp_path):
        from src.storage.delta import DeltaStorage
        return DeltaStorage(data_dir=tmp_path)

    @pytest.fixture()
    def sample_data(self):
        return {
            "BTCUSDT": [
                {"timestamp": "2024-01-01", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 100.0},
                {"timestamp": "2024-01-02", "open": 42500.0, "high": 44000.0, "low": 42000.0, "close": 43500.0, "volume": 150.0},
            ],
            "ETHUSDT": [
                {"timestamp": "2024-01-01", "open": 2200.0, "high": 2300.0, "low": 2100.0, "close": 2250.0, "volume": 500.0},
            ],
        }

    def test_save_and_load_raw(self, storage, sample_data):
        storage.save_raw(sample_data)
        loaded = storage.load_raw()
        assert "BTCUSDT" in loaded
        assert "ETHUSDT" in loaded
        assert len(loaded["BTCUSDT"]) == 2
        assert len(loaded["ETHUSDT"]) == 1

    def test_load_raw_filter_symbols(self, storage, sample_data):
        storage.save_raw(sample_data)
        loaded = storage.load_raw(symbols=["BTCUSDT"])
        assert "BTCUSDT" in loaded
        assert "ETHUSDT" not in loaded

    def test_load_raw_empty(self, storage):
        loaded = storage.load_raw()
        assert loaded == {}

    def test_save_raw_empty_data(self, storage):
        result = storage.save_raw({})
        assert isinstance(result, str)

    def test_save_raw_empty_records(self, storage):
        result = storage.save_raw({"BTCUSDT": []})
        assert isinstance(result, str)

    def test_raw_data_roundtrip_values(self, storage, sample_data):
        storage.save_raw(sample_data)
        loaded = storage.load_raw()
        btc = sorted(loaded["BTCUSDT"], key=lambda r: r["timestamp"])
        assert btc[0]["open"] == 42000.0
        assert btc[0]["close"] == 42500.0
        assert btc[1]["volume"] == 150.0

    def test_list_raw_symbols(self, storage, sample_data):
        storage.save_raw(sample_data)
        symbols = storage.list_raw_symbols()
        assert sorted(symbols) == ["BTCUSDT", "ETHUSDT"]

    def test_list_raw_symbols_empty(self, storage):
        assert storage.list_raw_symbols() == []

    def test_save_and_load_processed(self, storage):
        data = {"symbols": ["BTC", "ETH"], "matrix": [[1.0, 0.5], [0.5, 1.0]]}
        storage.save_processed(data, "correlation")
        loaded = storage.load_processed("correlation")
        assert loaded["symbols"] == ["BTC", "ETH"]
        assert loaded["matrix"] == [[1.0, 0.5], [0.5, 1.0]]

    def test_load_processed_not_found(self, storage):
        from src.storage.base import StorageError
        with pytest.raises(StorageError):
            storage.load_processed("nonexistent")

    def test_list_processed(self, storage):
        data = {"key": "value"}
        storage.save_processed(data, "returns")
        storage.save_processed(data, "volatility")
        names = storage.list_processed()
        assert "returns" in names
        assert "volatility" in names

    def test_list_processed_empty(self, storage):
        assert storage.list_processed() == []

    def test_save_and_load_output(self, storage):
        data = {"weights": {"BTC": 0.6, "ETH": 0.4}, "sharpe": 1.5}
        storage.save_output(data, "portfolio")
        loaded = storage.load_output("portfolio")
        assert loaded["weights"]["BTC"] == 0.6
        assert loaded["sharpe"] == 1.5

    def test_load_output_not_found(self, storage):
        from src.storage.base import StorageError
        with pytest.raises(StorageError):
            storage.load_output("nonexistent")

    def test_list_outputs(self, storage):
        storage.save_output({"a": 1}, "result1")
        storage.save_output({"b": 2}, "result2")
        outputs = storage.list_outputs()
        assert "result1" in outputs
        assert "result2" in outputs

    def test_list_outputs_empty(self, storage):
        assert storage.list_outputs() == []

    def test_overwrite_raw(self, storage, sample_data):
        storage.save_raw(sample_data)
        new_data = {"BTCUSDT": [
            {"timestamp": "2024-02-01", "open": 50000.0, "high": 51000.0, "low": 49000.0, "close": 50500.0, "volume": 200.0},
        ]}
        storage.save_raw(new_data)
        loaded = storage.load_raw()
        assert "BTCUSDT" in loaded
        assert len(loaded["BTCUSDT"]) == 1
        assert loaded["BTCUSDT"][0]["open"] == 50000.0

    def test_directory_creation(self, tmp_path):
        from src.storage.delta import DeltaStorage
        deep_path = tmp_path / "a" / "b" / "c"
        storage = DeltaStorage(data_dir=deep_path)
        assert (deep_path / "raw" / "klines").exists()
        assert (deep_path / "processed").exists()
        assert (deep_path / "output").exists()
