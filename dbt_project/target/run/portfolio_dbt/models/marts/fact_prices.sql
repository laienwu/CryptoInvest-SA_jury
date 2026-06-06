
  
  create view "warehouse"."main"."fact_prices__dbt_tmp" as (
    -- Fact table: OHLCV prices (deduplicated)

WITH stg AS (
    SELECT * FROM "warehouse"."main"."stg_klines"
)

SELECT
    symbol,
    timestamp,
    open_price,
    high_price,
    low_price,
    close_price,
    volume
FROM stg
QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol, timestamp ORDER BY timestamp) = 1
  );
