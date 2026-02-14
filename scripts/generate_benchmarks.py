#!/usr/bin/env python3
"""
Generate sample benchmark data for the PostgreSQL benchmarks database.

This is a demo/testing script — it creates realistic but synthetic data
for S&P 500 and BTC indices, then inserts it via the production write path
(``BenchmarkRepository.insert_index_data``).

Prerequisites:
    - PostgreSQL benchmarks container running (``docker compose --profile benchmarks up -d``)
    - Schema initialized via ``scripts/init-benchmarks.sql`` (automatic on first start)

Usage:
    python scripts/generate_benchmarks.py
"""

import random
from datetime import date, timedelta
from typing import Any

from src.pipeline.ingest_postgres import BenchmarkRepository


def _generate_index_series(
    start_value: float,
    mean: float,
    std: float,
    days: int,
) -> list[dict[str, Any]]:
    """Generate a synthetic daily price series via random walk."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    data: list[dict[str, Any]] = []
    value = start_value
    current_date = start_date

    while current_date <= end_date:
        daily_return = random.gauss(mean, std)
        value *= 1 + daily_return
        data.append({
            "date": current_date,
            "close_value": round(value, 2),
        })
        current_date += timedelta(days=1)

    return data


if __name__ == "__main__":
    print("PostgreSQL Benchmark Data Generator")
    print("=" * 50)

    repo = BenchmarkRepository()

    print("\n[1] Testing connection...")
    if not repo.test_connection():
        print("  Connection failed. Is postgres-benchmarks running?")
        print("  Start it with: docker compose --profile benchmarks up -d")
        raise SystemExit(1)

    print("  Connection successful!")

    print("\n[2] Generating sample data...")
    sp500_data = _generate_index_series(4800.0, mean=0.0003, std=0.01, days=90)
    btc_data = _generate_index_series(90000.0, mean=0.001, std=0.03, days=90)

    # Single connection, atomic transaction
    with BenchmarkRepository() as repo:
        repo.insert_index_data("SP500", sp500_data)
        print(f"  Inserted {len(sp500_data)} S&P 500 records")

        repo.insert_index_data("BTC_INDEX", btc_data)
        print(f"  Inserted {len(btc_data)} BTC index records")

    print("\n[3] Loading benchmarks to verify...")
    repo = BenchmarkRepository()
    benchmarks = repo.load_benchmarks()

    print("\n" + "=" * 50)
    print("BENCHMARK SUMMARY")
    print("=" * 50)
    summary = repo.get_benchmark_summary()
    for index_name, stats in summary.items():
        print(f"\n{index_name}:")
        print(f"  Data points: {stats['data_points']}")
        print(f"  Range: {stats['first_date']} to {stats['last_date']}")
        print(f"  Value range: {stats['min_value']:.2f} - {stats['max_value']:.2f}")

    print("\nDone.")
