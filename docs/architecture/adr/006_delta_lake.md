# ADR-006: Delta Lake for ACID Data Lake Storage

## Status
Accepted

## Context
The data lake stores raw, processed, and output data in plain Parquet files. While Parquet provides efficient columnar storage, it lacks:
- **ACID transactions**: Concurrent writes can corrupt data
- **Time travel**: No ability to query historical snapshots
- **Schema enforcement**: No built-in schema evolution guarantees
- **Atomic operations**: Partial writes leave inconsistent state

For a production-grade data engineering platform handling high-frequency ingestion (1-minute candles, order book streams), these guarantees become critical.

## Decision
Add **Delta Lake** as an optional storage backend using the `deltalake` Python package (delta-rs), which is a pure-Rust implementation requiring no JVM.

### Key design choices:
1. **Optional dependency**: Delta Lake coexists with the plain Parquet backend. Users choose via `storage_backend` config.
2. **Same Storage ABC**: `DeltaStorage` implements the existing `Storage` interface — no API changes.
3. **delta-rs (no JVM)**: The Rust-based `deltalake` package provides Delta Lake protocol support without Java/Spark dependency.
4. **Partition by symbol**: Raw data is partitioned by `symbol` for efficient per-asset queries.

## Consequences

### Positive
- ACID transactions prevent data corruption during concurrent pipeline runs
- Time travel enables auditing and debugging data quality issues
- Schema enforcement catches data drift at write time
- Seamless integration via existing Storage ABC factory pattern

### Negative
- Additional optional dependency (`deltalake` package)
- Slightly higher write latency due to transaction log management
- Delta Lake metadata (`_delta_log/`) adds storage overhead

### Neutral
- Plain Parquet remains the default backend — Delta Lake is opt-in
- No changes required to pipeline code (same Storage interface)
