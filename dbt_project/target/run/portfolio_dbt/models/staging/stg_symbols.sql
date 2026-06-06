
  
  create view "warehouse"."main"."stg_symbols__dbt_tmp" as (
    -- Staging: extract unique symbols with basic metadata

WITH klines AS (
    SELECT * FROM "warehouse"."main"."stg_klines"
)

SELECT
    symbol,
    MIN(timestamp)   AS first_date,
    MAX(timestamp)   AS last_date,
    COUNT(*)         AS record_count
FROM klines
GROUP BY symbol
ORDER BY symbol
  );
