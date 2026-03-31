-- Custom test: all volumes must be non-negative

SELECT
    symbol,
    timestamp,
    volume
FROM {{ ref('fact_prices') }}
WHERE volume < 0
