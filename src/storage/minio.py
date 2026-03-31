"""
MinIO (S3-compatible) storage implementation for the portfolio optimization project.

This module implements the Storage interface using MinIO as an S3-compatible
object storage backend. It demonstrates cloud-native data lake patterns
without requiring AWS credentials or costs.

Data structure (S3 buckets/prefixes):
    portfolio-data/
    ├── raw/klines/BTCUSDT.parquet
    ├── processed/returns.parquet
    └── output/weights.json

Example usage:
    >>> from src.storage.minio import MinIOStorage
    >>> storage = MinIOStorage(endpoint="localhost:9000")
    >>> storage.save_raw(data)
    >>> loaded = storage.load_raw(["BTCUSDT"])
"""

import io
import json
import logging
from datetime import datetime
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

from ._utils import KLINES_SCHEMA
from .base import Storage, StorageError

logger = logging.getLogger(__name__)

# Default bucket name for all portfolio data
DEFAULT_BUCKET = "portfolio-data"


class MinIOStorage(Storage):
    """
    MinIO (S3-compatible) storage implementation.

    Stores data as objects in MinIO buckets:
    - Raw klines: raw/klines/{symbol}.parquet
    - Processed data: processed/{name}.parquet
    - Output data: output/{name}.json

    Args:
        endpoint: MinIO server endpoint (host:port).
        access_key: MinIO access key.
        secret_key: MinIO secret key.
        bucket: Bucket name for all portfolio data.
        secure: Whether to use HTTPS.
    """

    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        bucket: str = DEFAULT_BUCKET,
        secure: bool = False,
    ):
        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info(f"Created bucket: {self._bucket}")
        except S3Error as e:
            raise StorageError(
                f"Failed to ensure bucket '{self._bucket}': {e}",
                operation="init",
            ) from e

    def _raw_key(self, symbol: str) -> str:
        return f"raw/klines/{symbol}.parquet"

    def _processed_key(self, name: str) -> str:
        return f"processed/{name}.parquet"

    def _output_key(self, name: str) -> str:
        return f"output/{name}.json"

    def _put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Upload bytes to MinIO."""
        buf = io.BytesIO(data)
        self._client.put_object(
            self._bucket, key, buf, length=len(data), content_type=content_type,
        )

    def _get_bytes(self, key: str) -> bytes:
        """Download bytes from MinIO."""
        response = self._client.get_object(self._bucket, key)
        try:
            return bytes(response.read())
        finally:
            response.close()
            response.release_conn()

    def _object_exists(self, key: str) -> bool:
        """Check if an object exists in MinIO."""
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except S3Error:
            return False

    # -------------------------------------------------------------------------
    # Raw Data Operations
    # -------------------------------------------------------------------------

    def save_raw(
        self, data: dict[str, list[dict[str, Any]]], metadata: dict[str, Any] | None = None
    ) -> str:
        if not data:
            raise StorageError("No data provided to save", operation="save_raw")

        saved_count = 0
        for symbol, records in data.items():
            if not records:
                logger.debug(f"Skipping {symbol}: no records")
                continue

            try:
                arrays = {
                    "timestamp": pa.array([r["timestamp"] for r in records], type=pa.string()),
                    "open": pa.array([r["open"] for r in records], type=pa.float64()),
                    "high": pa.array([r["high"] for r in records], type=pa.float64()),
                    "low": pa.array([r["low"] for r in records], type=pa.float64()),
                    "close": pa.array([r["close"] for r in records], type=pa.float64()),
                    "volume": pa.array([r["volume"] for r in records], type=pa.float64()),
                }
                table = pa.table(arrays, schema=KLINES_SCHEMA)

                if metadata:
                    meta = {
                        b"storage_metadata": json.dumps(metadata).encode(),
                        b"saved_at": datetime.now().isoformat().encode(),
                        b"symbol": symbol.encode(),
                    }
                    table = table.replace_schema_metadata(meta)

                buf = io.BytesIO()
                pq.write_table(table, buf, compression="snappy")
                self._put_bytes(self._raw_key(symbol), buf.getvalue())
                saved_count += 1
                logger.debug(f"Saved {symbol}: {len(records)} records to MinIO")

            except S3Error as e:
                raise StorageError(
                    f"Failed to save {symbol}: {e}", operation="save_raw"
                ) from e

        logger.info(f"Saved raw data for {saved_count} symbols to MinIO")
        return f"s3://{self._bucket}/raw/klines/"

    def load_raw(
        self, symbols: list[str] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        if symbols is None:
            symbols = self.list_raw_symbols()

        if not symbols:
            raise StorageError("No raw data found in MinIO", operation="load_raw")

        result: dict[str, list[dict[str, Any]]] = {}

        for symbol in symbols:
            key = self._raw_key(symbol)
            if not self._object_exists(key):
                logger.warning(f"No data found for {symbol}")
                continue

            try:
                data = self._get_bytes(key)
                table = pq.read_table(io.BytesIO(data))

                records = []
                for i in range(table.num_rows):
                    records.append({
                        "timestamp": table["timestamp"][i].as_py(),
                        "open": table["open"][i].as_py(),
                        "high": table["high"][i].as_py(),
                        "low": table["low"][i].as_py(),
                        "close": table["close"][i].as_py(),
                        "volume": table["volume"][i].as_py(),
                    })

                result[symbol] = records
                logger.debug(f"Loaded {symbol}: {len(records)} records from MinIO")

            except S3Error as e:
                raise StorageError(
                    f"Failed to load {symbol}: {e}", operation="load_raw"
                ) from e

        if not result:
            raise StorageError(
                f"No data loaded for requested symbols: {symbols}",
                operation="load_raw",
            )

        logger.info(f"Loaded raw data for {len(result)} symbols from MinIO")
        return result

    # -------------------------------------------------------------------------
    # Processed Data Operations
    # -------------------------------------------------------------------------

    def save_processed(self, data: dict[str, Any], name: str) -> str:
        if not data:
            raise StorageError(f"No data provided for {name}", operation="save_processed")

        try:
            if "matrix" in data and "symbols" in data:
                table = self._create_matrix_table(data)
            elif "values" in data and "symbols" in data and "dates" in data:
                table = self._create_timeseries_table(data)
            else:
                table = self._create_generic_table(data)

            meta = {
                b"data_type": name.encode(),
                b"saved_at": datetime.now().isoformat().encode(),
            }
            table = table.replace_schema_metadata(meta)

            buf = io.BytesIO()
            pq.write_table(table, buf, compression="snappy")
            self._put_bytes(self._processed_key(name), buf.getvalue())

            logger.info(f"Saved processed data '{name}' to MinIO")
            return f"s3://{self._bucket}/processed/{name}.parquet"

        except S3Error as e:
            raise StorageError(
                f"Failed to save processed data '{name}': {e}",
                operation="save_processed",
            ) from e

    def load_processed(self, name: str) -> dict[str, Any]:
        key = self._processed_key(name)
        if not self._object_exists(key):
            raise StorageError(
                f"Processed data '{name}' not found in MinIO",
                operation="load_processed",
            )

        try:
            data = self._get_bytes(key)
            table = pq.read_table(io.BytesIO(data))
            columns = table.column_names

            if "symbol_row" in columns and "symbol_col" in columns:
                return self._load_matrix_table(table)
            elif "date" in columns and "symbol" in columns and "value" in columns:
                return self._load_timeseries_table(table)
            elif "data" in columns:
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

    # -------------------------------------------------------------------------
    # Output Data Operations
    # -------------------------------------------------------------------------

    def save_output(self, data: dict[str, Any], name: str) -> str:
        if not data:
            raise StorageError(f"No data provided for output '{name}'", operation="save_output")

        try:
            output_data = {
                "_metadata": {
                    "name": name,
                    "saved_at": datetime.now().isoformat(),
                },
                **data,
            }

            payload = json.dumps(output_data, indent=2, ensure_ascii=False).encode("utf-8")
            self._put_bytes(self._output_key(name), payload, content_type="application/json")

            logger.info(f"Saved output '{name}' to MinIO")
            return f"s3://{self._bucket}/output/{name}.json"

        except S3Error as e:
            raise StorageError(
                f"Failed to save output '{name}': {e}", operation="save_output"
            ) from e

    def load_output(self, name: str) -> dict[str, Any]:
        key = self._output_key(name)
        if not self._object_exists(key):
            raise StorageError(
                f"Output '{name}' not found in MinIO", operation="load_output"
            )

        try:
            raw = self._get_bytes(key)
            data: dict[str, Any] = json.loads(raw.decode("utf-8"))

            if "_metadata" in data:
                del data["_metadata"]

            logger.debug(f"Loaded output '{name}' from MinIO")
            return data

        except json.JSONDecodeError as e:
            raise StorageError(
                f"Invalid JSON in output '{name}': {e}", operation="load_output"
            ) from e
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Failed to load output '{name}': {e}", operation="load_output"
            ) from e

    # -------------------------------------------------------------------------
    # List Operations
    # -------------------------------------------------------------------------

    def list_raw_symbols(self) -> list[str]:
        symbols = []
        try:
            for obj in self._client.list_objects(self._bucket, prefix="raw/klines/"):
                name = obj.object_name
                if name.endswith(".parquet"):
                    symbol = name.removeprefix("raw/klines/").removesuffix(".parquet")
                    if symbol:
                        symbols.append(symbol)
        except S3Error:
            return []
        return sorted(symbols)

    def list_processed(self) -> list[str]:
        names = []
        try:
            for obj in self._client.list_objects(self._bucket, prefix="processed/"):
                name = obj.object_name
                if name.endswith(".parquet"):
                    metric = name.removeprefix("processed/").removesuffix(".parquet")
                    if metric:
                        names.append(metric)
        except S3Error:
            return []
        return sorted(names)

    def list_outputs(self) -> list[str]:
        names = []
        try:
            for obj in self._client.list_objects(self._bucket, prefix="output/"):
                name = obj.object_name
                if name.endswith(".json"):
                    output = name.removeprefix("output/").removesuffix(".json")
                    if output:
                        names.append(output)
        except S3Error:
            return []
        return sorted(names)

    # -------------------------------------------------------------------------
    # Table helpers (same logic as ParquetStorage)
    # -------------------------------------------------------------------------

    def _create_matrix_table(self, data: dict[str, Any]) -> pa.Table:
        symbols = data["symbols"]
        matrix = data["matrix"]
        rows = []
        for i, sym_i in enumerate(symbols):
            for j, sym_j in enumerate(symbols):
                rows.append((sym_i, sym_j, float(matrix[i][j])))
        return pa.table({
            "symbol_row": pa.array([r[0] for r in rows], type=pa.string()),
            "symbol_col": pa.array([r[1] for r in rows], type=pa.string()),
            "value": pa.array([r[2] for r in rows], type=pa.float64()),
        })

    def _create_timeseries_table(self, data: dict[str, Any]) -> pa.Table:
        symbols = data["symbols"]
        dates = data["dates"]
        values = data["values"]
        rows = []
        for i, symbol in enumerate(symbols):
            for j, date in enumerate(dates):
                rows.append((date, symbol, float(values[i][j])))
        return pa.table({
            "date": pa.array([r[0] for r in rows], type=pa.string()),
            "symbol": pa.array([r[1] for r in rows], type=pa.string()),
            "value": pa.array([r[2] for r in rows], type=pa.float64()),
        })

    def _create_generic_table(self, data: dict[str, Any]) -> pa.Table:
        return pa.table({
            "data": pa.array([json.dumps(data)], type=pa.string()),
        })

    def _load_matrix_table(self, table: pa.Table) -> dict[str, Any]:
        symbols_seen: list[str] = []
        for sym in table["symbol_row"]:
            s = sym.as_py()
            if s not in symbols_seen:
                symbols_seen.append(s)
        n = len(symbols_seen)
        symbol_to_idx = {s: i for i, s in enumerate(symbols_seen)}
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(table.num_rows):
            row_sym = table["symbol_row"][i].as_py()
            col_sym = table["symbol_col"][i].as_py()
            value = table["value"][i].as_py()
            matrix[symbol_to_idx[row_sym]][symbol_to_idx[col_sym]] = value
        return {"symbols": symbols_seen, "matrix": matrix}

    def _load_timeseries_table(self, table: pa.Table) -> dict[str, Any]:
        dates_seen: list[str] = []
        symbols_seen: list[str] = []
        for i in range(table.num_rows):
            d = table["date"][i].as_py()
            s = table["symbol"][i].as_py()
            if d not in dates_seen:
                dates_seen.append(d)
            if s not in symbols_seen:
                symbols_seen.append(s)
        date_to_idx = {d: i for i, d in enumerate(dates_seen)}
        symbol_to_idx = {s: i for i, s in enumerate(symbols_seen)}
        values = [[0.0] * len(dates_seen) for _ in range(len(symbols_seen))]
        for i in range(table.num_rows):
            date = table["date"][i].as_py()
            symbol = table["symbol"][i].as_py()
            value = table["value"][i].as_py()
            values[symbol_to_idx[symbol]][date_to_idx[date]] = value
        return {"symbols": symbols_seen, "dates": dates_seen, "values": values}
