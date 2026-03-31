"""
Data volume metrics for governance and monitoring.

Computes record counts, file sizes, partition counts, and freshness
across all data lake zones. Useful for demonstrating data governance
and monitoring capabilities at scale.

Usage:
    >>> from src.pipeline.data_metrics import compute_data_metrics
    >>> metrics = compute_data_metrics(storage)
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.storage import Storage

logger = logging.getLogger(__name__)


class DataMetricsError(Exception):
    """Custom exception for data metrics operations."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


def _count_parquet_files(directory: Path) -> int:
    """Count all .parquet files recursively."""
    if not directory.exists():
        return 0
    return sum(1 for _ in directory.rglob("*.parquet"))


def _measure_dir_size(directory: Path) -> int:
    """Sum byte sizes of all files in a directory tree."""
    if not directory.exists():
        return 0
    return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())


def compute_data_metrics(
    storage: Storage,
    data_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Compute comprehensive data volume metrics.

    Args:
        storage: Storage backend to query for record counts.
        data_dir: Base data directory. Defaults to project data/ dir.

    Returns:
        Dict with total_records, total_symbols, per-symbol breakdown,
        zone sizes, partition counts, and freshness.
    """
    if data_dir is None:
        data_dir = Path(__file__).parent.parent.parent / "data"
    else:
        data_dir = Path(data_dir)

    # Load raw data to compute per-symbol metrics
    try:
        raw_data = storage.load_raw()
    except Exception as e:
        raise DataMetricsError(
            f"Failed to load raw data: {e}", operation="compute_data_metrics"
        ) from e

    total_records = 0
    symbols_info: dict[str, dict[str, Any]] = {}

    for symbol, records in raw_data.items():
        n = len(records)
        total_records += n

        dates = [r["timestamp"] for r in records]
        sorted_dates = sorted(dates)

        symbols_info[symbol] = {
            "records": n,
            "first_date": sorted_dates[0] if sorted_dates else None,
            "last_date": sorted_dates[-1] if sorted_dates else None,
        }

    # File sizes per zone
    raw_dir = data_dir / "raw"
    processed_dir = data_dir / "processed"
    output_dir = data_dir / "output"

    raw_size = _measure_dir_size(raw_dir)
    processed_size = _measure_dir_size(processed_dir)
    output_size = _measure_dir_size(output_dir)
    total_size = raw_size + processed_size + output_size

    # Per-symbol file sizes (scan raw directory)
    for symbol in symbols_info:
        symbol_dir = raw_dir / "klines" / f"symbol={symbol}"
        if symbol_dir.exists():
            symbols_info[symbol]["size_bytes"] = _measure_dir_size(symbol_dir)
        else:
            # Legacy flat file
            flat_file = raw_dir / "klines" / f"{symbol}.parquet"
            if flat_file.exists():
                symbols_info[symbol]["size_bytes"] = flat_file.stat().st_size
            else:
                symbols_info[symbol]["size_bytes"] = 0

    # Zone record counts
    raw_records = total_records
    try:
        processed_names = storage.list_processed()
        processed_count = len(processed_names)
    except Exception:
        processed_count = 0
    try:
        output_names = storage.list_outputs()
        output_count = len(output_names)
    except Exception:
        output_count = 0

    # Partition count (Hive-style partitions in raw)
    partitions = _count_parquet_files(raw_dir)

    # Freshness: hours since most recent record
    freshness_hours: float | None = None
    if raw_data:
        all_dates: list[str] = []
        for records in raw_data.values():
            all_dates.extend(r["timestamp"] for r in records)
        if all_dates:
            latest = max(all_dates)
            try:
                # Try ISO 8601 first (intraday)
                latest_dt = datetime.fromisoformat(latest).replace(tzinfo=UTC)
            except ValueError:
                try:
                    latest_dt = datetime.strptime(latest, "%Y-%m-%d").replace(tzinfo=UTC)
                except ValueError:
                    latest_dt = None

            if latest_dt:
                delta = datetime.now(UTC) - latest_dt
                freshness_hours = round(delta.total_seconds() / 3600, 2)

    return {
        "total_records": total_records,
        "total_symbols": len(symbols_info),
        "symbols": symbols_info,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "zones": {
            "raw": {"records": raw_records, "size_bytes": raw_size},
            "processed": {"count": processed_count, "size_bytes": processed_size},
            "output": {"count": output_count, "size_bytes": output_size},
        },
        "partitions": partitions,
        "freshness_hours": freshness_hours,
        "method": "data_volume_metrics",
    }
