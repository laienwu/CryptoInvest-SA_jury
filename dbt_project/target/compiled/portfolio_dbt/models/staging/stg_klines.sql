-- Staging: read raw kline Parquet files and cast to proper types
-- Reads Hive-partitioned layout: klines/symbol=X/year=Y/month=M/data.parquet

WITH raw_klines AS (
    SELECT *
    FROM read_parquet(
        '../data/raw/klines/symbol=*/year=*/month=*/*.parquet',
        hive_partitioning=true,
        union_by_name=true
    )
)

SELECT
    symbol::VARCHAR                           AS symbol,
    timestamp::VARCHAR                        AS timestamp,
    CAST("open"  AS DOUBLE)                  AS open_price,
    CAST(high    AS DOUBLE)                  AS high_price,
    CAST(low     AS DOUBLE)                  AS low_price,
    CAST("close" AS DOUBLE)                  AS close_price,
    CAST(volume  AS DOUBLE)                  AS volume
FROM raw_klines
WHERE timestamp IS NOT NULL