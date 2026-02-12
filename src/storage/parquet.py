"""
Parquet storage implementation for the portfolio optimization project.

This module implements the Storage interface using Apache Parquet format
via the pyarrow library. It provides efficient columnar storage for
time-series financial data.

Features:
- One Parquet file per symbol for raw klines data
- Columnar storage optimized for analytical queries
- No pandas dependency - uses pyarrow directly
- Metadata support via Parquet schema metadata

Data structure:
    data/
    ├── raw/
    │   └── klines/
    │       ├── BTCUSDT.parquet
    │       ├── ETHUSDT.parquet
    │       └── ...
    ├── processed/
    │   ├── returns.parquet
    │   ├── correlation.parquet
    │   └── ...
    └── output/
        └── weights.json

Example usage:
    >>> from src.storage.parquet import ParquetStorage
    >>> storage = ParquetStorage()
    >>> storage.save_raw(data)
    >>> loaded = storage.load_raw(["BTCUSDT", "ETHUSDT"])
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ._utils import write_klines_parquet
from .base import Storage, StorageError

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Default base data directory (relative to project root)
DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data"


# =============================================================================
# ParquetStorage Implementation
# =============================================================================


class ParquetStorage(Storage):
    """
    Parquet-based storage implementation.

    Stores data as Parquet files on the local filesystem:
    - Raw klines: one file per symbol in data/raw/klines/
    - Processed data: one file per metric in data/processed/
    - Output data: JSON files in data/output/

    Args:
        data_dir: Base directory for data storage. Defaults to project's data/ folder.
    """

    def __init__(self, data_dir: str | Path | None = None):
        """Initialize ParquetStorage with the specified data directory."""
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create required directory structure if it doesn't exist."""
        (self.data_dir / "raw" / "klines").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "processed").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "output").mkdir(parents=True, exist_ok=True)

    def _get_raw_path(self, symbol: str) -> Path:
        """Get the file path for a symbol's raw klines data."""
        return self.data_dir / "raw" / "klines" / f"{symbol}.parquet"

    def _get_processed_path(self, name: str) -> Path:
        """Get the file path for processed data."""
        return self.data_dir / "processed" / f"{name}.parquet"

    def _get_output_path(self, name: str) -> Path:
        """Get the file path for output data (JSON format)."""
        return self.data_dir / "output" / f"{name}.json"

    # -------------------------------------------------------------------------
    # Raw Data Operations
    # -------------------------------------------------------------------------

    def save_raw(
        self, data: dict[str, list[dict[str, Any]]], metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Save raw ingested klines data to Parquet files.

        Each symbol gets its own Parquet file with OHLCV columns.

        Args:
            data: Dictionary mapping symbol to list of OHLCV records.
            metadata: Optional metadata (stored in Parquet schema metadata).

        Returns:
            Path to the raw klines directory.

        Raises:
            StorageError: If save operation fails.
        """
        if not data:
            raise StorageError("No data provided to save", operation="save_raw")

        saved_count = 0
        klines_dir = self.data_dir / "raw" / "klines"

        for symbol, records in data.items():
            if not records:
                logger.debug(f"Skipping {symbol}: no records")
                continue

            try:
                file_path = self._get_raw_path(symbol)
                write_klines_parquet(symbol, records, file_path, metadata)
                saved_count += 1
                logger.debug(f"Saved {symbol}: {len(records)} records to {file_path.name}")

            except Exception as e:
                raise StorageError(
                    f"Failed to save {symbol}: {e}", operation="save_raw"
                ) from e

        logger.info(f"Saved raw data for {saved_count} symbols to {klines_dir}")
        return str(klines_dir)

    def load_raw(
        self, symbols: list[str] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Load raw klines data from Parquet files.

        Args:
            symbols: List of symbols to load. If None, loads all available.

        Returns:
            Dictionary mapping symbol to list of OHLCV records.

        Raises:
            StorageError: If no data is found.
        """
        klines_dir = self.data_dir / "raw" / "klines"

        # Determine which symbols to load
        if symbols is None:
            symbols = self.list_raw_symbols()

        if not symbols:
            raise StorageError(
                f"No raw data found in {klines_dir}", operation="load_raw"
            )

        result: dict[str, list[dict[str, Any]]] = {}

        for symbol in symbols:
            file_path = self._get_raw_path(symbol)

            if not file_path.exists():
                logger.warning(f"No data found for {symbol}")
                continue

            try:
                # Read Parquet file
                table = pq.read_table(file_path)

                # Convert to list of dicts (row-oriented format)
                records = []
                for i in range(table.num_rows):
                    records.append(
                        {
                            "timestamp": table["timestamp"][i].as_py(),
                            "open": table["open"][i].as_py(),
                            "high": table["high"][i].as_py(),
                            "low": table["low"][i].as_py(),
                            "close": table["close"][i].as_py(),
                            "volume": table["volume"][i].as_py(),
                        }
                    )

                result[symbol] = records
                logger.debug(f"Loaded {symbol}: {len(records)} records")

            except Exception as e:
                raise StorageError(
                    f"Failed to load {symbol}: {e}", operation="load_raw"
                ) from e

        if not result:
            raise StorageError(
                f"No data loaded for requested symbols: {symbols}",
                operation="load_raw",
            )

        logger.info(f"Loaded raw data for {len(result)} symbols")
        return result

    # -------------------------------------------------------------------------
    # Processed Data Operations
    # -------------------------------------------------------------------------

    def save_processed(self, data: dict[str, Any], name: str) -> str:
        """
        Save processed data to a Parquet file.

        Processed data can have various structures (returns, correlation matrices, etc.).
        This method handles different data types and converts them appropriately.

        Args:
            data: Dictionary containing processed data.
                  Expected keys depend on the type of data:
                  - For returns: {"symbols": [...], "dates": [...], "values": [[...], ...]}
                  - For matrices: {"symbols": [...], "matrix": [[...], ...]}
            name: Identifier for the processed data.

        Returns:
            Path to the saved file.

        Raises:
            StorageError: If save operation fails.
        """
        if not data:
            raise StorageError(
                f"No data provided for {name}", operation="save_processed"
            )

        file_path = self._get_processed_path(name)

        try:
            # Determine the structure of the data and create appropriate table
            if "matrix" in data and "symbols" in data:
                # Matrix data (e.g., correlation, covariance)
                table = self._create_matrix_table(data)
            elif "values" in data and "symbols" in data and "dates" in data:
                # Time series data (e.g., returns per symbol per date)
                table = self._create_timeseries_table(data)
            else:
                # Generic key-value data - store as JSON in metadata
                table = self._create_generic_table(data)

            # Add metadata
            meta = {
                b"data_type": name.encode(),
                b"saved_at": datetime.now().isoformat().encode(),
            }
            table = table.replace_schema_metadata(meta)

            pq.write_table(table, file_path, compression="snappy")
            logger.info(f"Saved processed data '{name}' to {file_path}")
            return str(file_path)

        except Exception as e:
            raise StorageError(
                f"Failed to save processed data '{name}': {e}",
                operation="save_processed",
            ) from e

    def _create_matrix_table(self, data: dict[str, Any]) -> pa.Table:
        """Create a table for matrix data (correlation, covariance)."""
        symbols = data["symbols"]
        matrix = data["matrix"]

        # Store matrix as: symbol_row, symbol_col, value
        rows = []
        for i, sym_i in enumerate(symbols):
            for j, sym_j in enumerate(symbols):
                rows.append((sym_i, sym_j, float(matrix[i][j])))

        arrays = {
            "symbol_row": pa.array([r[0] for r in rows], type=pa.string()),
            "symbol_col": pa.array([r[1] for r in rows], type=pa.string()),
            "value": pa.array([r[2] for r in rows], type=pa.float64()),
        }

        return pa.table(arrays)

    def _create_timeseries_table(self, data: dict[str, Any]) -> pa.Table:
        """Create a table for time series data (returns, volatility)."""
        symbols = data["symbols"]
        dates = data["dates"]
        values = data["values"]  # 2D: [symbols][dates]

        # Store as: date, symbol, value
        rows = []
        for i, symbol in enumerate(symbols):
            for j, date in enumerate(dates):
                rows.append((date, symbol, float(values[i][j])))

        arrays = {
            "date": pa.array([r[0] for r in rows], type=pa.string()),
            "symbol": pa.array([r[1] for r in rows], type=pa.string()),
            "value": pa.array([r[2] for r in rows], type=pa.float64()),
        }

        return pa.table(arrays)

    def _create_generic_table(self, data: dict[str, Any]) -> pa.Table:
        """Create a table for generic key-value data."""
        # Store as JSON string in a single-row table
        arrays = {
            "data": pa.array([json.dumps(data)], type=pa.string()),
        }
        return pa.table(arrays)

    def load_processed(self, name: str) -> dict[str, Any]:
        """
        Load processed data from a Parquet file.

        Args:
            name: Identifier of the processed data to load.

        Returns:
            Dictionary containing the processed data.

        Raises:
            StorageError: If data not found or load fails.
        """
        file_path = self._get_processed_path(name)

        if not file_path.exists():
            raise StorageError(
                f"Processed data '{name}' not found at {file_path}",
                operation="load_processed",
            )

        try:
            table = pq.read_table(file_path)
            columns = table.column_names

            # Determine data structure from columns
            if "symbol_row" in columns and "symbol_col" in columns:
                # Matrix data
                return self._load_matrix_table(table)
            elif "date" in columns and "symbol" in columns and "value" in columns:
                # Time series data
                return self._load_timeseries_table(table)
            elif "data" in columns:
                # Generic JSON data
                result: dict[str, Any] = json.loads(table["data"][0].as_py())
                return result
            else:
                raise StorageError(
                    f"Unknown data structure in '{name}'", operation="load_processed"
                )

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Failed to load processed data '{name}': {e}",
                operation="load_processed",
            ) from e

    def _load_matrix_table(self, table: pa.Table) -> dict[str, Any]:
        """Load matrix data from table."""
        # Get unique symbols (preserving order)
        symbols_seen: list[str] = []
        for sym in table["symbol_row"]:
            s = sym.as_py()
            if s not in symbols_seen:
                symbols_seen.append(s)

        symbols = symbols_seen
        n = len(symbols)
        symbol_to_idx = {s: i for i, s in enumerate(symbols)}

        # Initialize matrix
        matrix = [[0.0] * n for _ in range(n)]

        # Fill matrix
        for i in range(table.num_rows):
            row_sym = table["symbol_row"][i].as_py()
            col_sym = table["symbol_col"][i].as_py()
            value = table["value"][i].as_py()
            matrix[symbol_to_idx[row_sym]][symbol_to_idx[col_sym]] = value

        return {"symbols": symbols, "matrix": matrix}

    def _load_timeseries_table(self, table: pa.Table) -> dict[str, Any]:
        """Load time series data from table."""
        # Get unique dates and symbols (preserving order)
        dates_seen: list[str] = []
        symbols_seen: list[str] = []

        for i in range(table.num_rows):
            d = table["date"][i].as_py()
            s = table["symbol"][i].as_py()
            if d not in dates_seen:
                dates_seen.append(d)
            if s not in symbols_seen:
                symbols_seen.append(s)

        dates = dates_seen
        symbols = symbols_seen
        date_to_idx = {d: i for i, d in enumerate(dates)}
        symbol_to_idx = {s: i for i, s in enumerate(symbols)}

        # Initialize values array
        values = [[0.0] * len(dates) for _ in range(len(symbols))]

        # Fill values
        for i in range(table.num_rows):
            date = table["date"][i].as_py()
            symbol = table["symbol"][i].as_py()
            value = table["value"][i].as_py()
            values[symbol_to_idx[symbol]][date_to_idx[date]] = value

        return {"symbols": symbols, "dates": dates, "values": values}

    # -------------------------------------------------------------------------
    # Output Data Operations
    # -------------------------------------------------------------------------

    def save_output(self, data: dict[str, Any], name: str) -> str:
        """
        Save output data to a JSON file.

        Output data (like portfolio weights) is stored as JSON for
        easy human readability and interoperability.

        Args:
            data: Dictionary containing output data.
            name: Identifier for the output.

        Returns:
            Path to the saved file.

        Raises:
            StorageError: If save operation fails.
        """
        if not data:
            raise StorageError(f"No data provided for output '{name}'", operation="save_output")

        file_path = self._get_output_path(name)

        try:
            # Add metadata
            output_data = {
                "_metadata": {
                    "name": name,
                    "saved_at": datetime.now().isoformat(),
                },
                **data,
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved output '{name}' to {file_path}")
            return str(file_path)

        except Exception as e:
            raise StorageError(
                f"Failed to save output '{name}': {e}", operation="save_output"
            ) from e

    def load_output(self, name: str) -> dict[str, Any]:
        """
        Load output data from a JSON file.

        Args:
            name: Identifier of the output to load.

        Returns:
            Dictionary containing the output data.

        Raises:
            StorageError: If output not found or load fails.
        """
        file_path = self._get_output_path(name)

        if not file_path.exists():
            raise StorageError(
                f"Output '{name}' not found at {file_path}", operation="load_output"
            )

        try:
            with open(file_path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)

            # Remove internal metadata from returned data
            if "_metadata" in data:
                del data["_metadata"]

            logger.debug(f"Loaded output '{name}' from {file_path}")
            return data

        except json.JSONDecodeError as e:
            raise StorageError(
                f"Invalid JSON in output '{name}': {e}", operation="load_output"
            ) from e
        except Exception as e:
            raise StorageError(
                f"Failed to load output '{name}': {e}", operation="load_output"
            ) from e

    # -------------------------------------------------------------------------
    # List Operations
    # -------------------------------------------------------------------------

    def list_raw_symbols(self) -> list[str]:
        """
        List all symbols that have stored raw data.

        Returns:
            List of symbol names (without .parquet extension).
        """
        klines_dir = self.data_dir / "raw" / "klines"
        if not klines_dir.exists():
            return []

        symbols = []
        for file_path in klines_dir.glob("*.parquet"):
            symbols.append(file_path.stem)

        return sorted(symbols)

    def list_processed(self) -> list[str]:
        """
        List all available processed data names.

        Returns:
            List of processed data identifiers.
        """
        processed_dir = self.data_dir / "processed"
        if not processed_dir.exists():
            return []

        names = []
        for file_path in processed_dir.glob("*.parquet"):
            names.append(file_path.stem)

        return sorted(names)

    def list_outputs(self) -> list[str]:
        """
        List all available output data names.

        Returns:
            List of output identifiers.
        """
        output_dir = self.data_dir / "output"
        if not output_dir.exists():
            return []

        names = []
        for file_path in output_dir.glob("*.json"):
            names.append(file_path.stem)

        return sorted(names)


# =============================================================================
# Main execution (for testing)
# =============================================================================

if __name__ == "__main__":
    import sys

    print("Testing ParquetStorage...")
    print("=" * 50)

    # Create storage instance
    storage = ParquetStorage()
    print(f"Data directory: {storage.data_dir}")

    # Test with sample data
    sample_data = {
        "BTCUSDT": [
            {"timestamp": "2024-01-01", "open": 42000.0, "high": 43000.0, "low": 41000.0, "close": 42500.0, "volume": 1000.0},
            {"timestamp": "2024-01-02", "open": 42500.0, "high": 44000.0, "low": 42000.0, "close": 43500.0, "volume": 1200.0},
        ],
        "ETHUSDT": [
            {"timestamp": "2024-01-01", "open": 2500.0, "high": 2600.0, "low": 2400.0, "close": 2550.0, "volume": 5000.0},
            {"timestamp": "2024-01-02", "open": 2550.0, "high": 2700.0, "low": 2500.0, "close": 2650.0, "volume": 5500.0},
        ],
    }

    # Test save_raw
    print("\nTest 1: save_raw")
    try:
        path = storage.save_raw(sample_data, metadata={"source": "test"})
        print(f"  OK: Saved to {path}")
    except StorageError as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # Test list_raw_symbols
    print("\nTest 2: list_raw_symbols")
    symbols = storage.list_raw_symbols()
    print(f"  Found symbols: {symbols}")

    # Test load_raw
    print("\nTest 3: load_raw")
    try:
        loaded = storage.load_raw()
        for symbol, records in loaded.items():
            print(f"  {symbol}: {len(records)} records")
            print(f"    First: {records[0]}")
    except StorageError as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # Test load_raw with filter
    print("\nTest 4: load_raw with filter")
    try:
        loaded = storage.load_raw(["BTCUSDT"])
        print(f"  Loaded symbols: {list(loaded.keys())}")
    except StorageError as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # Test save/load processed (matrix)
    print("\nTest 5: save/load processed (matrix)")
    matrix_data = {
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "matrix": [[1.0, 0.8], [0.8, 1.0]],
    }
    try:
        storage.save_processed(matrix_data, "test_correlation")
        loaded_matrix = storage.load_processed("test_correlation")
        print(f"  Loaded: {loaded_matrix}")
    except StorageError as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # Test save/load processed (timeseries)
    print("\nTest 6: save/load processed (timeseries)")
    ts_data = {
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "dates": ["2024-01-01", "2024-01-02"],
        "values": [[0.01, 0.02], [0.015, 0.025]],
    }
    try:
        storage.save_processed(ts_data, "test_returns")
        loaded_ts = storage.load_processed("test_returns")
        print(f"  Loaded symbols: {loaded_ts['symbols']}")
        print(f"  Loaded dates: {loaded_ts['dates']}")
    except StorageError as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # Test save/load output
    print("\nTest 7: save/load output")
    weights = {"BTCUSDT": 0.4, "ETHUSDT": 0.3, "BNBUSDT": 0.3}
    try:
        storage.save_output({"weights": weights, "expected_return": 0.15}, "test_weights")
        loaded_weights = storage.load_output("test_weights")
        print(f"  Loaded: {loaded_weights}")
    except StorageError as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # Test list operations
    print("\nTest 8: list operations")
    print(f"  Raw symbols: {storage.list_raw_symbols()}")
    print(f"  Processed: {storage.list_processed()}")
    print(f"  Outputs: {storage.list_outputs()}")

    print("\n" + "=" * 50)
    print("All tests passed!")
