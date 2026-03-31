-- Staging: extract unique symbols with basic metadata

WITH klines AS (
    SELECT * FROM {{ ref('stg_klines') }}
)

SELECT
    symbol,
    MIN(timestamp)   AS first_date,
    MAX(timestamp)   AS last_date,
    COUNT(*)         AS record_count
FROM klines
GROUP BY symbol
ORDER BY symbol
