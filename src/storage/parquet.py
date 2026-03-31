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

    @property
    def _raw_dataset_dir(self) -> Path:
        """Root directory for the partitioned raw klines dataset."""
        return self.data_dir / "raw" / "klines"

    def _get_raw_path(self, symbol: str) -> Path:
        """Get the legacy flat-file path for a symbol's raw klines data."""
        return self.data_dir / "raw" / "klines" / f"{symbol}.parquet"

    def _is_partitioned(self) -> bool:
        """Check if the raw data uses Hive-style partitioning."""
        klines_dir = self._raw_dataset_dir
        return any(d.name.startswith("symbol=") for d in klines_dir.iterdir() if d.is_dir()) if klines_dir.exists() else False

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
        Save raw ingested klines data as a Hive-partitioned Parquet dataset.

        Partition layout: ``klines/symbol=X/year=Y/month=M/data.parquet``

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
        klines_dir = self._raw_dataset_dir

        for symbol, records in data.items():
            if not records:
                logger.debug("Skipping %s: no records", symbol)
                continue

            try:
                # Group records by year/month extracted from timestamp
                buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
                for rec in records:
                    ts = rec["timestamp"]
                    # Handle both "YYYY-MM-DD" and "YYYY-MM-DDTHH:MM:SS"
                    year = ts[:4]
                    month = ts[5:7]
                    buckets.setdefault((year, month), []).append(rec)

                for (year, month), bucket_records in buckets.items():
                    partition_dir = klines_dir / f"symbol={symbol}" / f"year={year}" / f"month={month}"
                    partition_dir.mkdir(parents=True, exist_ok=True)
                    file_path = partition_dir / "data.parquet"
                    write_klines_parquet(symbol, bucket_records, file_path, metadata)

                saved_count += 1
                logger.debug("Saved %s: %d records (%d partitions)", symbol, len(records), len(buckets))

            except Exception as e:
                raise StorageError(
                    f"Failed to save {symbol}: {e}", operation="save_raw"
                ) from e

        logger.info("Saved raw data for %d symbols to %s", saved_count, klines_dir)
        return str(klines_dir)

    def load_raw(
        self, symbols: list[str] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Load raw klines data from Hive-partitioned Parquet dataset.

        Falls back to legacy flat-file layout for backward compatibility.

        Args:
            symbols: List of symbols to load. If None, loads all available.

        Returns:
            Dictionary mapping symbol to list of OHLCV records.

        Raises:
            StorageError: If no data is found.
        """
        klines_dir = self._raw_dataset_dir

        if symbols is None:
            symbols = self.list_raw_symbols()

        if not symbols:
            raise StorageError(
                f"No raw data found in {klines_dir}", operation="load_raw"
            )

        result: dict[str, list[dict[str, Any]]] = {}

        for symbol in symbols:
            try:
                table = self._load_symbol_table(symbol)
                if table is None:
                    logger.warning("No data found for %s", symbol)
                    continue

                records = table.to_pydict()
                n = table.num_rows
                result[symbol] = [
                    {
                        "timestamp": records["timestamp"][i],
                        "open": records["open"][i],
                        "high": records["high"][i],
                        "low": records["low"][i],
                        "close": records["close"][i],
                        "volume": records["volume"][i],
                    }
                    for i in range(n)
                ]
                logger.debug("Loaded %s: %d records", symbol, n)

            except Exception as e:
                raise StorageError(
                    f"Failed to load {symbol}: {e}", operation="load_raw"
                ) from e

        if not result:
            raise StorageError(
                f"No data loaded for requested symbols: {symbols}",
                operation="load_raw",
            )

        logger.info("Loaded raw data for %d symbols", len(result))
        return result

    def _load_symbol_table(self, symbol: str) -> pa.Table | None:
        """Load all partitions for a single symbol into one Arrow table."""
        partition_dir = self._raw_dataset_dir / f"symbol={symbol}"
        if partition_dir.is_dir():
            parquet_files = list(partition_dir.rglob("*.parquet"))
            if parquet_files:
                tables = [pq.read_table(f) for f in sorted(parquet_files)]
                return pa.concat_tables(tables)

        # Fallback: legacy flat file
        flat_file = self._get_raw_path(symbol)
        if flat_file.exists():
            return pq.read_table(flat_file)

        return None

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

        Supports both Hive-partitioned (``symbol=X/``) and legacy flat layout.

        Returns:
            Sorted list of symbol names.
        """
        klines_dir = self._raw_dataset_dir
        if not klines_dir.exists():
            return []

        symbols: set[str] = set()

        # Hive partitions: symbol=BTCUSDT/
        for d in klines_dir.iterdir():
            if d.is_dir() and d.name.startswith("symbol="):
                symbols.add(d.name.split("=", 1)[1])

        # Legacy flat files: BTCUSDT.parquet
        for f in klines_dir.glob("*.parquet"):
            symbols.add(f.stem)

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
