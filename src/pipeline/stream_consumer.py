"""
Kafka consumer for real-time kline ingestion into Bronze zone.

Reads kline events from a Kafka topic and writes micro-batch Parquet
files to the Bronze layer (data/raw/klines/).

Usage:
    python -m src.pipeline.stream_consumer

Architecture:
    Kafka topic (klines-raw) → stream_consumer → Bronze Parquet
"""

import json
import logging
import os
import signal
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from kafka import KafkaConsumer

from src.config import load_config
from src.storage._utils import write_klines_parquet

logger = logging.getLogger(__name__)

# Flush buffer every N records or T seconds, whichever comes first
FLUSH_INTERVAL_SECONDS = 60
FLUSH_BATCH_SIZE = 100


def _load_existing_timestamps(parquet_path: Path) -> set[str]:
    """Load existing timestamps from a Parquet file to avoid duplicates."""
    if not parquet_path.exists():
        return set()
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(parquet_path, columns=["timestamp"])
        return set(table.column("timestamp").to_pylist())
    except Exception:
        return set()


def _flush_buffer(
    buffer: dict[str, list[dict[str, Any]]],
    data_dir: Path,
) -> int:
    """Write buffered records to Parquet, deduplicating with existing data."""
    flushed = 0
    klines_dir = data_dir / "raw" / "klines"
    klines_dir.mkdir(parents=True, exist_ok=True)

    for symbol, records in buffer.items():
        if not records:
            continue

        parquet_path = klines_dir / f"{symbol}.parquet"
        existing_ts = _load_existing_timestamps(parquet_path)

        # Deduplicate: only keep records with new timestamps
        new_records = [r for r in records if r["timestamp"] not in existing_ts]
        if not new_records:
            logger.debug("%s: all %d records already exist, skipping", symbol, len(records))
            continue

        # If file exists, merge with existing data
        if parquet_path.exists():
            try:
                import pyarrow.parquet as pq

                table = pq.read_table(parquet_path)
                existing_records = [
                    {
                        "timestamp": str(table.column("timestamp")[i].as_py()),
                        "open": float(table.column("open")[i].as_py()),
                        "high": float(table.column("high")[i].as_py()),
                        "low": float(table.column("low")[i].as_py()),
                        "close": float(table.column("close")[i].as_py()),
                        "volume": float(table.column("volume")[i].as_py()),
                    }
                    for i in range(len(table))
                ]
                all_records = existing_records + new_records
            except Exception as e:
                logger.warning("Failed to read existing %s, writing new only: %s", symbol, e)
                all_records = new_records
        else:
            all_records = new_records

        # Sort by timestamp and deduplicate
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for r in sorted(all_records, key=lambda x: x["timestamp"]):
            if r["timestamp"] not in seen:
                seen.add(r["timestamp"])
                merged.append(r)

        # Write — strip event_time (not in Parquet schema)
        clean_records = [
            {k: v for k, v in r.items() if k != "event_time"}
            for r in merged
        ]
        write_klines_parquet(symbol, clean_records, parquet_path)
        flushed += len(new_records)
        logger.info("%s: flushed %d new records (total %d)", symbol, len(new_records), len(merged))

    return flushed


def run_consumer(
    bootstrap_servers: str | None = None,
    topic: str | None = None,
) -> None:
    """
    Run the Kafka consumer: Kafka topic → Bronze Parquet.

    Args:
        bootstrap_servers: Kafka broker address.
        topic: Kafka topic name.
    """
    cfg = load_config()
    data_dir = Path(cfg.data_dir)

    if bootstrap_servers is None:
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    if topic is None:
        topic = os.environ.get("KAFKA_TOPIC", "klines-raw")

    logger.info("Starting consumer: %s → %s", topic, data_dir / "raw" / "klines")

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        group_id="klines-consumer",
        consumer_timeout_ms=5000,
    )

    running = True

    def _shutdown(*_args):
        nonlocal running
        running = False
        logger.info("Shutdown signal received")

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    buffer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    buffer_count = 0
    last_flush = time.time()
    total_flushed = 0

    while running:
        try:
            for message in consumer:
                if not running:
                    break

                record = message.value
                symbol = record.get("symbol", "UNKNOWN")
                buffer[symbol].append(record)
                buffer_count += 1

                # Flush if batch size or time interval reached
                elapsed = time.time() - last_flush
                if buffer_count >= FLUSH_BATCH_SIZE or elapsed >= FLUSH_INTERVAL_SECONDS:
                    flushed = _flush_buffer(buffer, data_dir)
                    total_flushed += flushed
                    buffer.clear()
                    buffer_count = 0
                    last_flush = time.time()

        except Exception as e:
            logger.error("Consumer error: %s", e)
            if running:
                time.sleep(2)

    # Final flush
    if buffer_count > 0:
        flushed = _flush_buffer(buffer, data_dir)
        total_flushed += flushed

    consumer.close()
    logger.info("Consumer stopped. Total flushed: %d records", total_flushed)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    run_consumer()
