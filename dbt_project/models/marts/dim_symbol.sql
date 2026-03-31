-- Dimension: symbol metadata

SELECT
    symbol,
    first_date,
    last_date,
    record_count,
    CASE
        WHEN symbol LIKE '%USDT' THEN 'crypto'
        ELSE 'traditional'
    END AS asset_class
FROM {{ ref('stg_symbols') }}
