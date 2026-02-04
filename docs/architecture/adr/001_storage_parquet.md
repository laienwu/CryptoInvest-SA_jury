# ADR-001: Parquet as Primary Storage Format

**Status:** Accepted
**Date:** 2025-01-06
**Deciders:** [Your Name] (Data Engineer), Pierre Durand (DevOps)
**Technical Story:** US-001, US-002

---

## Context

We need to store time-series price data from multiple cryptocurrency sources. The storage format must support:

- Efficient columnar queries (aggregations, filtering by date)
- Schema enforcement for data quality
- Compression for cost efficiency
- Compatibility with our analytics stack (DuckDB, Python)

Options considered:
1. CSV files
2. JSON files
3. Apache Parquet
4. Delta Lake
5. PostgreSQL tables

---

## Decision

**We will use Apache Parquet as the primary storage format for the Data Lake.**

---

## Rationale

### Why Parquet over alternatives:

| Criterion | CSV | JSON | Parquet | Delta Lake | PostgreSQL |
|-----------|-----|------|---------|------------|------------|
| Columnar queries | Poor | Poor | Excellent | Excellent | Good |
| Compression | None | None | Snappy/Zstd | Snappy/Zstd | Limited |
| Schema enforcement | None | Partial | Strong | Strong | Strong |
| Tooling complexity | Low | Low | Low | Medium | Medium |
| Native DuckDB support | Yes | Yes | Excellent | Limited | External |
| File-based (no server) | Yes | Yes | Yes | Yes | No |

### Key factors in decision:

1. **Performance**: Parquet's columnar format is 10-100x faster for analytical queries (SELECT specific columns, aggregations) compared to row-based formats.

2. **Compression**: Snappy compression achieves 5-10x size reduction vs CSV while maintaining fast decompression.

3. **Schema**: Built-in schema prevents data type drift and documents structure.

4. **DuckDB native**: DuckDB reads Parquet directly with zero-copy, enabling SQL queries without ETL.

5. **Simplicity**: Unlike Delta Lake, Parquet requires no additional runtime or dependencies.

### Why not Delta Lake:
- Adds complexity (delta-rs dependency, transaction logs)
- ACID transactions not required for daily batch loads
- Would be overkill for current data volume (~50KB/day)

### Why not PostgreSQL for raw data:
- Requires server management
- Data Lake pattern prefers file-based storage
- DuckDB provides SQL without the operational overhead

---

## Consequences

### Positive
- Fast analytical queries via DuckDB
- Self-documenting schema in files
- 80% storage reduction vs CSV
- No database server to manage
- Easy backup (just copy files)

### Negative
- Not human-readable (unlike CSV/JSON)
- Requires PyArrow library
- No row-level updates (append-only pattern)
- Less familiar to some team members

### Neutral
- Learning curve for PyArrow API
- Need parquet-tools for file inspection

---

## Compliance

| Requirement | Status |
|-------------|--------|
| C11 - Database creation | Parquet schema = implicit DB schema |
| C18 - Data Lake architecture | File-based storage fits lake pattern |
| C19 - Component integration | Native DuckDB/PyArrow integration |

---

## Implementation

```python
# Writing Parquet with PyArrow
import pyarrow as pa
import pyarrow.parquet as pq

schema = pa.schema([
    ("symbol", pa.string()),
    ("timestamp", pa.timestamp("ms")),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.float64()),
])

table = pa.Table.from_pydict(data, schema=schema)
pq.write_table(table, "data/raw/klines/BTCUSDT.parquet")
```

---

## References

- [Apache Parquet Documentation](https://parquet.apache.org/)
- [DuckDB Parquet Support](https://duckdb.org/docs/data/parquet)
- [PyArrow Parquet Guide](https://arrow.apache.org/docs/python/parquet.html)

---

*Reviewed by: Pierre Durand (DevOps)*
*Approved by: Marie Dupont (Product Owner)*
