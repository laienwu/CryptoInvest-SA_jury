-- Staging: read raw kline Parquet files and cast to proper types
-- Supports both Hive-partitioned and legacy flat file layouts

WITH raw_klines AS (
    SELECT
        *
    FROM read_parquet('../data/raw/klines/**/*.parquet', hive_partitioning=true, union_by_name=true)
)

SELECT
    COALESCE(symbol, 'UNKNOWN')::VARCHAR   AS symbol,
    timestamp::VARCHAR                      AS timestamp,
    CAST("open"  AS DOUBLE)                AS open_price,
    CAST(high    AS DOUBLE)                AS high_price,
    CAST(low     AS DOUBLE)                AS low_price,
    CAST("close" AS DOUBLE)                AS close_price,
    CAST(volume  AS DOUBLE)                AS volume
FROM raw_klines
WHERE timestamp IS NOT NULL
