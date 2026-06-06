-- Summary metrics for the entire portfolio dataset

SELECT
    COUNT(DISTINCT symbol)  AS n_symbols,
    COUNT(*)                AS n_records,
    MIN(timestamp)          AS first_date,
    MAX(timestamp)          AS last_date,
    SUM(volume)             AS total_volume
FROM "warehouse"."main"."fact_prices"