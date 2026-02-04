-- Portfolio Benchmarks Database Initialization
-- This script runs automatically when the postgres-benchmarks container starts

-- Market indices (S&P 500, BTC index, etc.)
CREATE TABLE IF NOT EXISTS market_indices (
    index_id SERIAL PRIMARY KEY,
    index_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    base_currency VARCHAR(10) DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Daily index values
CREATE TABLE IF NOT EXISTS index_daily (
    index_id INTEGER REFERENCES market_indices(index_id),
    date DATE NOT NULL,
    open_value DECIMAL(18,4),
    high_value DECIMAL(18,4),
    low_value DECIMAL(18,4),
    close_value DECIMAL(18,4) NOT NULL,
    volume DECIMAL(24,4),
    PRIMARY KEY (index_id, date)
);

-- Portfolio snapshots (historical performance)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    portfolio_name VARCHAR(100) NOT NULL,
    total_value DECIMAL(18,4) NOT NULL,
    daily_return DECIMAL(10,6),
    cumulative_return DECIMAL(10,6),
    volatility_30d DECIMAL(10,6),
    sharpe_30d DECIMAL(10,6),
    max_drawdown DECIMAL(10,6),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (snapshot_date, portfolio_name)
);

-- Benchmark comparison metrics
CREATE TABLE IF NOT EXISTS benchmark_comparison (
    comparison_id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    portfolio_name VARCHAR(100) NOT NULL,
    benchmark_name VARCHAR(50) NOT NULL,
    portfolio_return DECIMAL(10,6),
    benchmark_return DECIMAL(10,6),
    alpha DECIMAL(10,6),
    beta DECIMAL(10,6),
    tracking_error DECIMAL(10,6),
    information_ratio DECIMAL(10,6),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (date, portfolio_name, benchmark_name)
);

-- Insert default indices
INSERT INTO market_indices (index_name, description, base_currency)
VALUES
    ('SP500', 'S&P 500 Index - US Large Cap', 'USD'),
    ('BTC_INDEX', 'Bitcoin Price Index', 'USD'),
    ('ETH_INDEX', 'Ethereum Price Index', 'USD'),
    ('CRYPTO_TOTAL', 'Total Crypto Market Cap Index', 'USD'),
    ('NASDAQ', 'NASDAQ Composite Index', 'USD')
ON CONFLICT (index_name) DO NOTHING;

-- Insert sample historical data for S&P 500 (last 90 days simulation)
-- Using a procedural approach with generate_series
DO $$
DECLARE
    sp500_id INTEGER;
    btc_id INTEGER;
    start_date DATE := CURRENT_DATE - INTERVAL '90 days';
    current_date DATE;
    sp500_value DECIMAL := 4800.0;
    btc_value DECIMAL := 90000.0;
    daily_return DECIMAL;
BEGIN
    -- Get index IDs
    SELECT index_id INTO sp500_id FROM market_indices WHERE index_name = 'SP500';
    SELECT index_id INTO btc_id FROM market_indices WHERE index_name = 'BTC_INDEX';

    -- Generate S&P 500 data
    FOR current_date IN SELECT generate_series(start_date, CURRENT_DATE, '1 day'::interval)::date
    LOOP
        -- Random walk with slight upward bias
        daily_return := (random() - 0.48) * 0.02;  -- -0.96% to +1.04%
        sp500_value := sp500_value * (1 + daily_return);

        INSERT INTO index_daily (index_id, date, close_value, open_value, high_value, low_value)
        VALUES (
            sp500_id,
            current_date,
            ROUND(sp500_value, 2),
            ROUND(sp500_value * (1 - random() * 0.005), 2),
            ROUND(sp500_value * (1 + random() * 0.01), 2),
            ROUND(sp500_value * (1 - random() * 0.01), 2)
        )
        ON CONFLICT (index_id, date) DO NOTHING;
    END LOOP;

    -- Generate BTC data (higher volatility)
    FOR current_date IN SELECT generate_series(start_date, CURRENT_DATE, '1 day'::interval)::date
    LOOP
        daily_return := (random() - 0.47) * 0.06;  -- Higher volatility
        btc_value := btc_value * (1 + daily_return);

        INSERT INTO index_daily (index_id, date, close_value, open_value, high_value, low_value)
        VALUES (
            btc_id,
            current_date,
            ROUND(btc_value, 2),
            ROUND(btc_value * (1 - random() * 0.01), 2),
            ROUND(btc_value * (1 + random() * 0.03), 2),
            ROUND(btc_value * (1 - random() * 0.03), 2)
        )
        ON CONFLICT (index_id, date) DO NOTHING;
    END LOOP;
END $$;

-- Create useful views
CREATE OR REPLACE VIEW v_index_returns AS
SELECT
    mi.index_name,
    id.date,
    id.close_value,
    LAG(id.close_value) OVER (PARTITION BY id.index_id ORDER BY id.date) as prev_close,
    (id.close_value - LAG(id.close_value) OVER (PARTITION BY id.index_id ORDER BY id.date))
        / NULLIF(LAG(id.close_value) OVER (PARTITION BY id.index_id ORDER BY id.date), 0) as daily_return
FROM index_daily id
JOIN market_indices mi ON id.index_id = mi.index_id;

CREATE OR REPLACE VIEW v_index_stats AS
SELECT
    mi.index_name,
    COUNT(*) as data_points,
    MIN(id.date) as first_date,
    MAX(id.date) as last_date,
    MIN(id.close_value) as min_value,
    MAX(id.close_value) as max_value,
    AVG(id.close_value) as avg_value,
    STDDEV(id.close_value) as stddev_value
FROM index_daily id
JOIN market_indices mi ON id.index_id = mi.index_id
GROUP BY mi.index_name;

-- Grant permissions (if needed for app user)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO portfolio;

-- Log completion
DO $$ BEGIN RAISE NOTICE 'Benchmarks database initialized successfully'; END $$;
