"""
Delta Lake storage backend for the portfolio optimization project.

This module implements the Storage interface using Delta Lake format
via the deltalake (delta-rs) Python binding. It provides ACID
transactions, time travel, and schema enforcement on top of Parquet.

No JVM required — uses the pure-Rust delta-rs implementation.

Data structure:
    data/delta/
    ├── raw/
    │   └── klines/
    │       └── _delta_log/   (Delta Lake transaction log)
    ├── processed/
    │   └── <name>/
    │       └── _delta_log/
    └── output/
        └── <name>.json

Example usage:
    >>> from src.storage.delta import DeltaStorage
    >>> storage = DeltaStorage()
    >>> storage.save_raw(data)
    >>> loaded = storage.load_raw(["BTCUSDT"])
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa

from .base import Storage, StorageError

logger = logging.getLogger(__name__)

# Default base data directory
DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data"


class DeltaStorageError(Exception):
    """Custom exception for Delta Lake storage operations."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


def _get_deltalake() -> Any:
    """Lazy import of deltalake to allow module loading without the package."""
    try:
        import deltalake
        return deltalake
    except ImportError as e:
        raise DeltaStorageError(
            "deltalake package not installed. Install with: pip install deltalake",
            operation="import",
        ) from e


class DeltaStorage(Storage):
    """
    Delta Lake storage backend.

    Provides ACID transactions, time travel, and schema enforcement
    on top of Parquet files using the delta-rs Rust engine.
    """

    def __init__(self, data_dir: str | Path | None = None):
        self._data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR / "delta"
        self._raw_dir = self._data_dir / "raw" / "klines"
        self._processed_dir = self._data_dir / "processed"
        self._output_dir = self._data_dir / "output"

        for d in (self._raw_dir, self._processed_dir, self._output_dir):
            d.mkdir(parents=True, exist_ok=True)

    def save_raw(
        self,
        data: dict[str, list[dict[str, Any]]],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save raw klines to a Delta table, partitioned by symbol."""
        dl = _get_deltalake()

        all_records: list[dict[str, Any]] = []
        for symbol, records in data.items():
            if not records:
                continue
            for r in records:
                all_records.append({
                    "symbol": symbol,
                    "timestamp": str(r["timestamp"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"]),
                })

        if not all_records:
            logger.warning("No records to save")
            return str(self._raw_dir)

        schema = pa.schema([
            pa.field("symbol", pa.string(), nullable=False),
            pa.field("timestamp", pa.string(), nullable=False),
            pa.field("open", pa.float64(), nullable=False),
            pa.field("high", pa.float64(), nullable=False),
            pa.field("low", pa.float64(), nullable=False),
            pa.field("close", pa.float64(), nullable=False),
            pa.field("volume", pa.float64(), nullable=False),
        ])

        table = pa.table({
            "symbol": pa.array([r["symbol"] for r in all_records], type=pa.string()),
            "timestamp": pa.array([r["timestamp"] for r in all_records], type=pa.string()),
            "open": pa.array([r["open"] for r in all_records], type=pa.float64()),
            "high": pa.array([r["high"] for r in all_records], type=pa.float64()),
            "low": pa.array([r["low"] for r in all_records], type=pa.float64()),
            "close": pa.array([r["close"] for r in all_records], type=pa.float64()),
            "volume": pa.array([r["volume"] for r in all_records], type=pa.float64()),
        }, schema=schema)

        table_path = str(self._raw_dir)
        try:
            dl.write_deltalake(
                table_path,
                table,
                mode="overwrite",
                partition_by=["symbol"],
            )
        except Exception as e:
            raise DeltaStorageError(
                f"Failed to write Delta table: {e}", operation="save_raw"
            ) from e

        n_symbols = len(data)
        n_records = len(all_records)
        logger.info("Saved %d records for %d symbols to Delta Lake", n_records, n_symbols)
        return table_path

    def load_raw(
        self, symbols: list[str] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """Load raw data from the Delta table."""
        dl = _get_deltalake()
        table_path = str(self._raw_dir)

        try:
            dt = dl.DeltaTable(table_path)
        except Exception:
            logger.warning("No Delta table found at %s", table_path)
            return {}

        table = dt.to_pyarrow_table()

        if symbols:
            mask = pa.compute.is_in(table.column("symbol"), value_set=pa.array(symbols))
            table = table.filter(mask)

        result: dict[str, list[dict[str, Any]]] = {}
        symbols_col = table.column("symbol").to_pylist()
        timestamps = table.column("timestamp").to_pylist()
        opens = table.column("open").to_pylist()
        highs = table.column("high").to_pylist()
        lows = table.column("low").to_pylist()
        closes = table.column("close").to_pylist()
        volumes = table.column("volume").to_pylist()

        for i in range(len(table)):
            sym = symbols_col[i]
            if sym not in result:
                result[sym] = []
            result[sym].append({
                "timestamp": timestamps[i],
                "open": opens[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "volume": volumes[i],
            })

        return result

    def save_processed(self, data: dict[str, Any], name: str) -> str:
        """Save processed data as a Delta table (JSON-encoded values)."""
        dl = _get_deltalake()
        table_dir = self._processed_dir / name
        table_dir.mkdir(parents=True, exist_ok=True)

        keys = list(data.keys())
        values = [json.dumps(data[k]) for k in keys]

        table = pa.table({
            "key": pa.array(keys, type=pa.string()),
            "value": pa.array(values, type=pa.string()),
        })

        try:
            dl.write_deltalake(str(table_dir), table, mode="overwrite")
        except Exception as e:
            raise DeltaStorageError(
                f"Failed to save processed '{name}': {e}",
                operation="save_processed",
            ) from e

        logger.info("Saved processed '%s' to Delta Lake (%d keys)", name, len(keys))
        return str(table_dir)

    def load_processed(self, name: str) -> dict[str, Any]:
        """Load processed data from a Delta table."""
        dl = _get_deltalake()
        table_dir = self._processed_dir / name

        try:
            dt = dl.DeltaTable(str(table_dir))
        except Exception as err:
            raise StorageError(
                f"Processed data '{name}' not found", operation="load_processed"
            ) from err

        table = dt.to_pyarrow_table()
        keys = table.column("key").to_pylist()
        values = table.column("value").to_pylist()

        return {k: json.loads(v) for k, v in zip(keys, values)}

    def save_output(self, data: dict[str, Any], name: str) -> str:
        """Save output data as JSON (same as Parquet backend)."""
        output_path = self._output_dir / f"{name}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            **data,
            "_saved_at": datetime.now().isoformat(),
        }
        output_path.write_text(json.dumps(payload, indent=2, default=str))
        logger.info("Saved output '%s' to %s", name, output_path)
        return str(output_path)

    def load_output(self, name: str) -> dict[str, Any]:
        """Load output data from JSON."""
        output_path = self._output_dir / f"{name}.json"

        if not output_path.exists():
            raise StorageError(
                f"Output '{name}' not found at {output_path}",
                operation="load_output",
            )

        result: dict[str, Any] = json.loads(output_path.read_text())
        return result

    def list_raw_symbols(self) -> list[str]:
        """List symbols available in the Delta table."""
        dl = _get_deltalake()

        try:
            dt = dl.DeltaTable(str(self._raw_dir))
        except Exception:
            return []

        table = dt.to_pyarrow_table(columns=["symbol"])
        import pyarrow.compute as pc
        symbols: list[str] = pc.unique(table.column("symbol")).to_pylist()
        return symbols

    def list_processed(self) -> list[str]:
        """List available processed datasets."""
        if not self._processed_dir.exists():
            return []
        return sorted(
            d.name for d in self._processed_dir.iterdir()
            if d.is_dir() and (d / "_delta_log").exists()
        )

    def list_outputs(self) -> list[str]:
        """List available output datasets."""
        if not self._output_dir.exists():
            return []
        return sorted(
            f.stem for f in self._output_dir.glob("*.json")
        )
