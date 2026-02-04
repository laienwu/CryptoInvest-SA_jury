# ADR-002: DuckDB as Data Warehouse Engine

**Status:** Accepted
**Date:** 2025-01-08
**Deciders:** [Your Name] (Data Engineer), Sophie Bernard (Data Analyst)
**Technical Story:** US-008

---

## Context

We need a SQL interface for analytical queries on our Data Lake. Requirements:

- SQL support for business users (Sophie, analysts)
- Star schema support (facts and dimensions)
- Integration with existing Parquet files
- Low operational overhead (certification project)
- Fast enough for interactive queries

Options considered:
1. PostgreSQL
2. DuckDB
3. SQLite
4. Apache Spark SQL
5. ClickHouse

---

## Decision

**We will use DuckDB as the embedded Data Warehouse engine.**

---

## Rationale

### Comparison matrix:

| Criterion | PostgreSQL | DuckDB | SQLite | Spark SQL | ClickHouse |
|-----------|------------|--------|--------|-----------|------------|
| Setup complexity | Medium | Zero | Zero | High | Medium |
| Parquet native | No | Yes | No | Yes | Limited |
| OLAP optimized | No | Yes | No | Yes | Yes |
| Embedded mode | No | Yes | Yes | No | No |
| Memory efficiency | Good | Excellent | Good | Poor | Good |
| Learning curve | Low | Low | Low | High | Medium |

### Key factors:

1. **Zero infrastructure**: DuckDB runs in-process, no server to manage. Perfect for certification project scope.

2. **Parquet-native**: Queries Parquet files directly without ETL:
   ```sql
   SELECT * FROM 'data/raw/klines/*.parquet'
   ```

3. **OLAP-optimized**: Columnar engine designed for analytical queries (aggregations, joins on large tables).

4. **Familiar SQL**: Standard SQL syntax, easy for Sophie and business users.

5. **Python integration**: Works seamlessly with PyArrow tables.

### Why not PostgreSQL:
- Requires server management (Docker container, backups, monitoring)
- Data must be loaded into tables (ETL step)
- Row-based storage less efficient for analytics
- Overkill for single-user analytical workload

### Why not Spark:
- Massive overhead for small data (~MB scale)
- Cluster management complexity
- Slow startup time
- Would be appropriate at TB scale

---

## Consequences

### Positive
- Zero operational overhead
- Query Parquet directly (no ETL)
- Fast analytical queries (vectorized execution)
- Single file database (portable)
- Excellent Python/PyArrow integration

### Negative
- Not suitable for concurrent write workloads
- No built-in replication/HA
- Less tooling ecosystem than PostgreSQL
- Relatively new (less battle-tested)

### Neutral
- Star schema implemented in code, not database constraints
- No foreign key enforcement (handled in ETL)

---

## Compliance

| Requirement | Status |
|-------------|--------|
| C9 - SQL extraction queries | Full SQL support |
| C13 - Facts/dimensions modeling | Star schema implemented |
| C14 - Create warehouse | DuckDB = analytical warehouse |
| C15 - ETL integration | Read from Parquet, write to DuckDB |

---

## Implementation

### Star Schema

```
        ┌──────────────┐
        │  dim_date    │
        │──────────────│
        │ date_key (PK)│
        │ full_date    │
        │ year         │
        │ month        │
        │ day_of_week  │
        └──────┬───────┘
               │
┌──────────────┼──────────────┐
│              │              │
│       ┌──────┴───────┐      │
│       │ fact_prices  │      │
│       │──────────────│      │
│       │ symbol (FK)  │──────┼──────┐
│       │ date_key (FK)│      │      │
│       │ open         │      │      │
│       │ high         │      │      │
│       │ low          │      │      │
│       │ close        │      │      │
│       │ volume       │      │      │
│       └──────────────┘      │      │
│                             │      │
└─────────────────────────────┘      │
                                     │
                              ┌──────┴───────┐
                              │  dim_symbol  │
                              │──────────────│
                              │ symbol (PK)  │
                              │ name         │
                              │ sector       │
                              │ category     │
                              └──────────────┘
```

### Code Example

```python
import duckdb

# Query Parquet files directly
conn = duckdb.connect("data/warehouse.duckdb")

# Create star schema
conn.execute("""
    CREATE TABLE IF NOT EXISTS fact_prices AS
    SELECT * FROM 'data/processed/klines/*.parquet'
""")

# Analytical query
result = conn.execute("""
    SELECT
        d.month,
        s.sector,
        AVG(f.close) as avg_price,
        SUM(f.volume) as total_volume
    FROM fact_prices f
    JOIN dim_date d ON f.date_key = d.date_key
    JOIN dim_symbol s ON f.symbol = s.symbol
    GROUP BY d.month, s.sector
    ORDER BY d.month
""").fetchall()
```

---

## References

- [DuckDB Documentation](https://duckdb.org/docs/)
- [DuckDB Star Schema Example](https://duckdb.org/docs/guides/star_schema)
- [Why DuckDB (Hacker News)](https://news.ycombinator.com/item?id=29658553)

---

*Reviewed by: Sophie Bernard (Data Analyst)*
*Approved by: Marie Dupont (Product Owner)*
