# ADR-007: dbt for SQL-Based Data Warehouse Transforms

## Status
Accepted

## Context
The data warehouse layer uses DuckDB with a star schema (fact_prices, dim_symbol, dim_date). Currently, all transformations are implemented in Python (PyArrow). While this works well for the pipeline, SQL-based transforms offer:
- **Declarative data modeling**: SQL is the lingua franca for analytics
- **Built-in testing**: dbt provides schema tests, data tests, and freshness checks
- **Data lineage**: Automatic DAG of model dependencies
- **Documentation**: Auto-generated data catalog from schema YAML

## Decision
Add a **dbt project** using `dbt-duckdb` adapter for warehouse-layer transformations. The dbt models complement (not replace) the existing Python pipeline.

### Project structure:
- `staging/`: Read raw Parquet files, cast types, clean data
- `marts/`: Star schema tables (fact_prices, dim_symbol, dim_date)
- `marts/`: Aggregates (daily returns, portfolio summary)
- `tests/`: Custom data quality assertions
- `macros/`: Reusable SQL (log returns)

### Integration:
- dbt runs as an Airflow BashOperator task after the Python ETL pipeline
- Uses the same DuckDB warehouse file (`data/warehouse.duckdb`)

## Consequences

### Positive
- SQL-native transforms for analytics team members
- Built-in data testing and documentation
- Automatic lineage graph via `dbt docs generate`
- Standard practice in modern data engineering stacks

### Negative
- Additional dependency (`dbt-core`, `dbt-duckdb`)
- Two transformation systems (Python pipeline + dbt) to maintain
- Requires understanding of both paradigms

### Neutral
- dbt operates on the warehouse layer only — Bronze/Silver zones remain Python
- Can be run independently or via Airflow
