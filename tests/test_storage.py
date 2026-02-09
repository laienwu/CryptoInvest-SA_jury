"""
Tests for the storage module.

Tests storage layer:
- Storage factory function
- ParquetStorage implementation
- DuckDBStorage implementation
- Abstract interface compliance
"""


import pytest

from src.storage import (
    ParquetStorage,
    Storage,
    StorageError,
    get_storage,
    list_available_backends,
    register_storage,
)


class TestStorageFactory:
    """Tests for get_storage factory function."""

    def test_default_storage(self):
        """Test that default storage is parquet."""
        storage = get_storage()
        assert isinstance(storage, ParquetStorage)

    def test_explicit_parquet(self):
        """Test explicit parquet storage request."""
        storage = get_storage("parquet")
        assert isinstance(storage, ParquetStorage)

    def test_explicit_duckdb(self):
        """Test explicit duckdb storage request."""
        storage = get_storage("duckdb")
        # Should not raise, returns DuckDBStorage
        assert storage is not None

    def test_invalid_backend_raises(self):
        """Test that invalid backend raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_storage("invalid_backend")
        assert "Unknown storage backend" in str(exc_info.value)

    def test_custom_data_dir(self, temp_data_dir):
        """Test storage with custom data directory."""
        storage = get_storage("parquet", data_dir=temp_data_dir)
        assert storage.data_dir == temp_data_dir


class TestListAvailableBackends:
    """Tests for list_available_backends function."""

    def test_includes_parquet(self):
        """Test that parquet is in available backends."""
        backends = list_available_backends()
        assert "parquet" in backends

    def test_includes_duckdb(self):
        """Test that duckdb is in available backends."""
        backends = list_available_backends()
        assert "duckdb" in backends

    def test_returns_list(self):
        """Test that function returns a list."""
        backends = list_available_backends()
        assert isinstance(backends, list)


class TestRegisterStorage:
    """Tests for register_storage function."""

    def test_register_valid_storage(self):
        """Test registering a valid storage class."""

        class TestStorage(Storage):
            def save_raw(self, data, metadata=None):
                pass

            def load_raw(self, symbols=None):
                return {}

            def list_raw_symbols(self):
                return []

            def save_processed(self, data, name, metadata=None):
                pass

            def load_processed(self, name):
                return {}

            def list_processed(self):
                return []

            def save_output(self, data, name, metadata=None):
                pass

            def load_output(self, name):
                return {}

        register_storage("test_storage", TestStorage)
        assert "test_storage" in list_available_backends()

    def test_register_invalid_class_raises(self):
        """Test that registering non-Storage class raises TypeError."""

        class NotAStorage:
            pass

        with pytest.raises(TypeError):
            register_storage("not_storage", NotAStorage)


class TestParquetStorage:
    """Tests for ParquetStorage implementation."""

    def test_initialization(self, temp_data_dir):
        """Test ParquetStorage initialization."""
        storage = ParquetStorage(data_dir=temp_data_dir)
        assert storage.data_dir == temp_data_dir

    def test_save_and_load_raw(self, temp_data_dir, sample_raw_data):
        """Test saving and loading raw data."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        # Save
        storage.save_raw(sample_raw_data)

        # Load
        loaded = storage.load_raw(["BTCUSDT", "ETHUSDT"])

        assert "BTCUSDT" in loaded
        assert "ETHUSDT" in loaded
        assert len(loaded["BTCUSDT"]) == len(sample_raw_data["BTCUSDT"])

    def test_list_raw_symbols(self, temp_data_dir, sample_raw_data):
        """Test listing raw symbols."""
        storage = ParquetStorage(data_dir=temp_data_dir)
        storage.save_raw(sample_raw_data)

        symbols = storage.list_raw_symbols()

        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

    def test_save_and_load_processed(self, temp_data_dir):
        """Test saving and loading processed data."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        data = {
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "values": [0.45, 0.55],
        }

        # Save
        storage.save_processed(data, "volatility")

        # Load
        loaded = storage.load_processed("volatility")

        assert loaded["symbols"] == data["symbols"]
        assert loaded["values"] == pytest.approx(data["values"])

    def test_list_processed(self, temp_data_dir):
        """Test listing processed metrics."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        data = {"symbols": ["BTC"], "values": [0.5]}
        storage.save_processed(data, "test_metric")

        metrics = storage.list_processed()

        assert "test_metric" in metrics

    def test_save_and_load_output(self, temp_data_dir, sample_portfolio_result):
        """Test saving and loading output data."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        # Save
        storage.save_output(sample_portfolio_result, "weights")

        # Load
        loaded = storage.load_output("weights")

        assert loaded["symbols"] == sample_portfolio_result["symbols"]
        assert loaded["expected_return"] == pytest.approx(
            sample_portfolio_result["expected_return"]
        )

    def test_load_nonexistent_raw(self, temp_data_dir):
        """Test loading nonexistent raw data."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        # Should return empty dict or raise exception for nonexistent symbols
        try:
            loaded = storage.load_raw(["NONEXISTENT"])
            # If it returns, should be empty or not contain the symbol
            assert loaded == {} or "NONEXISTENT" not in loaded
        except Exception:
            # Also acceptable to raise an exception
            pass

    def test_load_nonexistent_processed(self, temp_data_dir):
        """Test loading nonexistent processed metric."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        with pytest.raises(Exception):  # StorageError or FileNotFoundError
            storage.load_processed("nonexistent_metric")

    def test_load_nonexistent_output(self, temp_data_dir):
        """Test loading nonexistent output."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        with pytest.raises(Exception):  # StorageError or FileNotFoundError
            storage.load_output("nonexistent")


class TestStorageError:
    """Tests for StorageError exception."""

    def test_error_message(self):
        """Test error message."""
        error = StorageError("Test error", operation="save")
        assert error.message == "Test error"
        assert error.operation == "save"
        assert str(error) == "Test error"

    def test_error_without_operation(self):
        """Test error without operation."""
        error = StorageError("Simple error")
        assert error.message == "Simple error"
        assert error.operation is None


class TestStorageDataIntegrity:
    """Integration tests for storage data integrity."""

    def test_raw_data_roundtrip(self, temp_data_dir, sample_raw_data):
        """Test that raw data survives save/load cycle."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        storage.save_raw(sample_raw_data)
        loaded = storage.load_raw(list(sample_raw_data.keys()))

        for symbol in sample_raw_data:
            original = sample_raw_data[symbol]
            recovered = loaded[symbol]

            assert len(original) == len(recovered)

            for i in range(len(original)):
                assert original[i]["close"] == pytest.approx(recovered[i]["close"])
                assert original[i]["timestamp"] == recovered[i]["timestamp"]

    def test_matrix_data_roundtrip(self, temp_data_dir, sample_correlation_matrix):
        """Test that matrix data survives save/load cycle."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        data = {
            "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            "matrix": sample_correlation_matrix,
        }

        storage.save_processed(data, "correlation")
        loaded = storage.load_processed("correlation")

        assert loaded["symbols"] == data["symbols"]

        for i in range(len(data["matrix"])):
            for j in range(len(data["matrix"][i])):
                assert loaded["matrix"][i][j] == pytest.approx(data["matrix"][i][j])

    def test_json_output_roundtrip(self, temp_data_dir, sample_portfolio_result):
        """Test that JSON output survives save/load cycle."""
        storage = ParquetStorage(data_dir=temp_data_dir)

        storage.save_output(sample_portfolio_result, "weights")
        loaded = storage.load_output("weights")

        # Check all fields
        assert loaded["symbols"] == sample_portfolio_result["symbols"]
        assert loaded["weights"] == sample_portfolio_result["weights"]
        assert loaded["expected_return"] == pytest.approx(
            sample_portfolio_result["expected_return"]
        )
        assert loaded["volatility"] == pytest.approx(
            sample_portfolio_result["volatility"]
        )
        assert loaded["sharpe_ratio"] == pytest.approx(
            sample_portfolio_result["sharpe_ratio"]
        )
        assert loaded["method"] == sample_portfolio_result["method"]
