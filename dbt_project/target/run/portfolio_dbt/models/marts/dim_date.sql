
  
  create view "warehouse"."main"."dim_date__dbt_tmp" as (
    -- Dimension: date spine from min to max date

WITH date_range AS (
    SELECT
        MIN(timestamp)::DATE AS min_date,
        MAX(timestamp)::DATE AS max_date
    FROM "warehouse"."main"."stg_klines"
),

dates AS (
    SELECT
        UNNEST(generate_series(min_date, max_date, INTERVAL '1 day'))::DATE AS date_key
    FROM date_range
)

SELECT
    date_key,
    EXTRACT(YEAR FROM date_key)::INT     AS year,
    EXTRACT(MONTH FROM date_key)::INT    AS month,
    EXTRACT(DAY FROM date_key)::INT      AS day,
    EXTRACT(DOW FROM date_key)::INT      AS day_of_week,
    CASE WHEN EXTRACT(DOW FROM date_key) IN (0, 6) THEN true ELSE false END AS is_weekend
FROM dates
ORDER BY date_key
  );
