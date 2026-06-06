-- Aggregate: daily log returns per symbol

WITH prices AS (
    SELECT
        symbol,
        timestamp,
        close_price,
        LAG(close_price) OVER (PARTITION BY symbol ORDER BY timestamp) AS prev_close
    FROM "warehouse"."main"."fact_prices"
)

SELECT
    symbol,
    timestamp,
    close_price,
    prev_close,
    
    CASE
        WHEN prev_close IS NOT NULL AND prev_close > 0
        THEN LN(close_price / prev_close)
        ELSE NULL
    END
 AS log_return
FROM prices
WHERE prev_close IS NOT NULL AND prev_close > 0