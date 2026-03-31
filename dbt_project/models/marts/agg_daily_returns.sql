-- Aggregate: daily log returns per symbol

WITH prices AS (
    SELECT
        symbol,
        timestamp,
        close_price,
        LAG(close_price) OVER (PARTITION BY symbol ORDER BY timestamp) AS prev_close
    FROM {{ ref('fact_prices') }}
)

SELECT
    symbol,
    timestamp,
    close_price,
    prev_close,
    {{ log_return('close_price', 'prev_close') }} AS log_return
FROM prices
WHERE prev_close IS NOT NULL AND prev_close > 0
