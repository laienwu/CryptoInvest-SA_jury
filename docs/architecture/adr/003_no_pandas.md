# ADR-003: PyArrow Instead of Pandas

**Status:** Accepted
**Date:** 2025-01-08
**Deciders:** [Your Name] (Data Engineer)
**Technical Story:** Performance optimization

---

## Context

Data manipulation library choice for ETL pipeline. The pipeline processes OHLCV data with operations:

- Type conversions
- Column transformations
- Aggregations (mean, std, correlation)
- File I/O (Parquet read/write)

Options considered:
1. Pandas
2. PyArrow (Apache Arrow)
3. Polars
4. Pure Python + NumPy

---

## Decision

**We will use PyArrow directly for data manipulation, avoiding Pandas dependency.**

---

## Rationale

### Comparison:

| Criterion | Pandas | PyArrow | Polars |
|-----------|--------|---------|--------|
| Memory efficiency | Poor | Excellent | Excellent |
| Parquet native | Via PyArrow | Native | Native |
| Type safety | Weak | Strong | Strong |
| API complexity | Low | Medium | Medium |
| Ecosystem maturity | Excellent | Good | Growing |
| Dependency weight | Heavy | Light | Light |

### Key factors:

1. **Memory efficiency**: PyArrow uses zero-copy reads and columnar memory layout. For our 450-record dataset:
   - Pandas: ~2MB memory overhead
   - PyArrow: ~50KB actual data size

2. **Type safety**: Arrow schema enforces types at read time, preventing silent type coercion bugs common in Pandas.

3. **Parquet native**: PyArrow is the underlying Parquet library. Using it directly avoids conversion overhead:
   ```python
   # Pandas (2 conversions)
   df = pd.read_parquet("file.parquet")  # Arrow → Pandas
   df.to_parquet("out.parquet")          # Pandas → Arrow

   # PyArrow (0 conversions)
   table = pq.read_table("file.parquet")  # Native Arrow
   pq.write_table(table, "out.parquet")   # Native Arrow
   ```

4. **Lighter dependency**: PyArrow ~30MB vs Pandas ~50MB (includes NumPy).

5. **DuckDB integration**: DuckDB can query Arrow tables with zero-copy, impossible with Pandas DataFrames.

### Why not Polars:
- Adds another dependency
- Less mature ecosystem
- Team more familiar with Arrow/Pandas concepts
- Would be good choice for larger datasets

### Trade-off accepted:
- PyArrow API more verbose than Pandas for some operations
- Fewer "convenience" methods
- Less Stack Overflow coverage

---

## Consequences

### Positive
- 10-50x lower memory usage
- Faster Parquet I/O (no conversion)
- Stronger type guarantees
- Zero-copy DuckDB integration
- Lighter Docker image

### Negative
- More verbose code for transformations
- Team learning curve
- Fewer tutorials/examples online
- Some operations need manual implementation

### Neutral
- NumPy still used for numerical computations (correlation, covariance)
- Can convert to Pandas if absolutely needed: `table.to_pandas()`

---

## Compliance

| Requirement | Status |
|-------------|--------|
| C10 - Aggregation rules | Implemented with PyArrow compute |
| C19 - Component integration | Native integration with DuckDB |

---

## Implementation Examples

### Reading Parquet
```python
import pyarrow.parquet as pq

# Read with schema validation
table = pq.read_table(
    "data/raw/klines/BTCUSDT.parquet",
    columns=["timestamp", "close", "volume"]
)
```

### Column Transformation
```python
import pyarrow.compute as pc

# Calculate log returns
closes = table.column("close")
returns = pc.subtract(
    pc.ln(closes[1:]),
    pc.ln(closes[:-1])
)
```

### Aggregation
```python
# Mean and standard deviation
mean_price = pc.mean(table.column("close")).as_py()
std_price = pc.stddev(table.column("close")).as_py()
```

### Type-Safe Schema
```python
schema = pa.schema([
    ("symbol", pa.string()),
    ("timestamp", pa.timestamp("ms")),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.float64()),
])

# This will raise if data doesn't match schema
table = pa.Table.from_pydict(data, schema=schema)
```

---

## Migration Path

If we ever need Pandas functionality:

```python
# One-way conversion (last resort)
df = table.to_pandas()

# Or use DuckDB for complex transformations
result = duckdb.query("""
    SELECT
        symbol,
        AVG(close) OVER (PARTITION BY symbol ORDER BY timestamp
                         ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as ma7
    FROM table
""").arrow()
```

---

## References

- [Apache Arrow Python Documentation](https://arrow.apache.org/docs/python/)
- [Why Arrow over Pandas](https://towardsdatascience.com/stop-using-pandas-and-start-using-arrow-7e12e63c2fca)
- [PyArrow Compute Functions](https://arrow.apache.org/docs/python/compute.html)

---

*Reviewed by: Sophie Bernard (Data Analyst)*
*Approved by: [Your Name] (Data Engineer)*
