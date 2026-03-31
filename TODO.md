# TODO — Batch 4: Massive Data Infrastructure

## Batch 3 (carried over)
- [x] 1. Strategy Showdown module
- [x] 2. Multi-strategy backtest
- [ ] 3. Update soutenance slides
- [ ] 4. Boost test coverage to 70%+
- [ ] 5. Integration test
- [ ] 6. Correlation regime analysis
- [ ] 7. Final sync

## Batch 4: Massive Data
- [x] 1. Expand symbols — 51 crypto pairs + 33 trad assets in config. Updated `PipelineConfig` defaults.
- [x] 2. Paginated ingestion — `fetch_klines` loops with 1000-record pages via `startTime`/`closeTime`.
- [x] 3. Switch to 1-minute candles — default interval `1m`, ISO 8601 timestamps (`%Y-%m-%dT%H:%M:%S`).
- [x] 4. Partition Parquet — Hive-style `symbol=X/year=Y/month=M/` layout in parquet storage.
- [x] 5. Delta Lake — `DeltaStorage` backend (`src/storage/delta.py`), registered in factory. ADR-006. Tests.
- [x] 6. Order book snapshots — Binance depth WebSocket → Kafka `orderbook-depth` → Parquet consumer. Tests.
- [x] 7. PySpark transforms — `src/pipeline/spark_transforms.py` (rolling corr, vol surface, volume). Dockerfile.spark. Tests.
- [x] 8. dbt SQL transforms — `dbt_project/` with staging + marts models on DuckDB. ADR-007. Airflow dbt_run task. Tests.
- [x] 9. Data volume metrics — `src/pipeline/data_metrics.py`. API endpoint `GET /data/metrics`. Tests.
