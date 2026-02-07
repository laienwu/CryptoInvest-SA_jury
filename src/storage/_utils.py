"""
Shared storage utilities.

Contains schema definitions and helper functions used by multiple
storage implementations to avoid code duplication.
"""

import json
from datetime import datetime
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path


# =============================================================================
# Schema Definitions (single source of truth)
# =============================================================================

KLINES_SCHEMA = pa.schema(
    [
        pa.field("timestamp", pa.string(), nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("volume", pa.float64(), nullable=False),
    ]
)


# =============================================================================
# Shared Parquet I/O
# =============================================================================


def write_klines_parquet(
    symbol: str,
    records: list[dict[str, Any]],
    file_path: Path,
    metadata: dict | None = None,
    compression: str = "snappy",
) -> None:
    """
    Write klines records to a Parquet file.

    Args:
        symbol: Symbol name (used in Parquet metadata).
        records: List of OHLCV dicts.
        file_path: Destination path.
        metadata: Optional metadata to embed in Parquet schema.
        compression: Parquet compression codec.
    """
    arrays = {
        "timestamp": pa.array(
            [r["timestamp"] for r in records], type=pa.string()
        ),
        "open": pa.array(
            [r["open"] for r in records], type=pa.float64()
        ),
        "high": pa.array(
            [r["high"] for r in records], type=pa.float64()
        ),
        "low": pa.array(
            [r["low"] for r in records], type=pa.float64()
        ),
        "close": pa.array(
            [r["close"] for r in records], type=pa.float64()
        ),
        "volume": pa.array(
            [r["volume"] for r in records], type=pa.float64()
        ),
    }

    table = pa.table(arrays, schema=KLINES_SCHEMA)

    if metadata:
        existing_meta = table.schema.metadata or {}
        new_meta = {
            **existing_meta,
            b"storage_metadata": json.dumps(metadata).encode(),
            b"saved_at": datetime.now().isoformat().encode(),
            b"symbol": symbol.encode(),
        }
        table = table.replace_schema_metadata(new_meta)

    pq.write_table(table, file_path, compression=compression)
