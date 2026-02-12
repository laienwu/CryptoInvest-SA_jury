"""
PostgreSQL database module for historical benchmarks.

Demonstrates C8 compliance: extraction from a relational database.

This module provides:
- Connection management to PostgreSQL
- SQL queries for benchmark data extraction
- Historical performance data storage

The benchmarks database stores:
- Historical portfolio performance
- Market indices (for comparison)
- Risk metrics over time

Example usage:
    >>> from src.pipeline.ingest_postgres import load_benchmarks
    >>> benchmarks = load_benchmarks()
    >>> print(benchmarks["sp500_return"])
"""

import logging
import os
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Database connection (from environment variables)
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "portfolio_benchmarks"),
    "user": os.getenv("POSTGRES_USER", "portfolio"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}


# =============================================================================
# Exceptions
# =============================================================================


class DatabaseError(Exception):
    """Exception for database errors."""

    def __init__(self, message: str, query: str | None = None):
        self.message = message
        self.query = query
        super().__init__(self.message)


# =============================================================================
# Connection Management
# =============================================================================


def _get_connection() -> Any:
    """
    Get a PostgreSQL connection.

    Returns:
        psycopg2 connection object.

    Raises:
        DatabaseError: If connection fails.
    """
    try:
        import psycopg2
    except ImportError as exc:
        raise DatabaseError("psycopg2 required: uv add psycopg2-binary") from exc

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        raise DatabaseError(f"Connection failed: {e}") from e


def test_connection() -> bool:
    """
    Test database connectivity.

    Returns:
        True if connection successful, False otherwise.
    """
    try:
        conn = _get_connection()
        conn.close()
        return True
    except DatabaseError:
        return False


# =============================================================================
# Schema Creation
# =============================================================================

SCHEMA_SQL = """
-- Historical benchmarks schema for portfolio optimization

-- Market indices (S&P 500, BTC index, etc.)
CREATE TABLE IF NOT EXISTS market_indices (
    index_id SERIAL PRIMARY KEY,
    index_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    base_currency VARCHAR(10) DEFAULT 'USD'
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
    UNIQUE (date, portfolio_name, benchmark_name)
);

-- Insert default indices
INSERT INTO market_indices (index_name, description, base_currency)
VALUES
    ('SP500', 'S&P 500 Index', 'USD'),
    ('BTC_INDEX', 'Bitcoin Index', 'USD'),
    ('CRYPTO_TOTAL', 'Total Crypto Market Cap', 'USD')
ON CONFLICT (index_name) DO NOTHING;
"""


def initialize_schema() -> None:
    """
    Create database schema if it doesn't exist.

    Creates tables for:
    - market_indices
    - index_daily
    - portfolio_snapshots
    - benchmark_comparison
    """
    logger.info("Initializing PostgreSQL schema")

    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(SCHEMA_SQL)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Schema initialized successfully")
    except DatabaseError as e:
        logger.error(f"Schema initialization failed: {e.message}")
        raise


# =============================================================================
# Data Insertion
# =============================================================================


def insert_index_data(
    index_name: str,
    data: list[dict[str, Any]],
) -> int:
    """
    Insert historical index data.

    Args:
        index_name: Name of the index (e.g., 'SP500').
        data: List of daily records with date, close_value, etc.

    Returns:
        Number of rows inserted.

    Example:
        >>> data = [{"date": "2024-01-01", "close_value": 4800.0}, ...]
        >>> insert_index_data("SP500", data)
    """
    conn = _get_connection()
    cursor = conn.cursor()

    # Get index_id
    cursor.execute(
        "SELECT index_id FROM market_indices WHERE index_name = %s",
        (index_name,)
    )
    result = cursor.fetchone()

    if not result:
        raise DatabaseError(f"Index not found: {index_name}")

    index_id = result[0]

    # Insert data
    insert_sql = """
        INSERT INTO index_daily (index_id, date, close_value, open_value, high_value, low_value, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (index_id, date) DO UPDATE SET
            close_value = EXCLUDED.close_value,
            open_value = EXCLUDED.open_value,
            high_value = EXCLUDED.high_value,
            low_value = EXCLUDED.low_value,
            volume = EXCLUDED.volume
    """

    rows_inserted = 0
    for record in data:
        cursor.execute(insert_sql, (
            index_id,
            record["date"],
            record.get("close_value") or record.get("close"),
            record.get("open_value") or record.get("open"),
            record.get("high_value") or record.get("high"),
            record.get("low_value") or record.get("low"),
            record.get("volume"),
        ))
        rows_inserted += 1

    conn.commit()
    cursor.close()
    conn.close()

    return rows_inserted


def insert_portfolio_snapshot(
    portfolio_name: str,
    snapshot_date: date,
    total_value: float,
    metrics: dict[str, float],
) -> None:
    """
    Insert a portfolio performance snapshot.

    Args:
        portfolio_name: Name of the portfolio.
        snapshot_date: Date of the snapshot.
        total_value: Total portfolio value.
        metrics: Performance metrics (daily_return, volatility, etc.).
    """
    conn = _get_connection()
    cursor = conn.cursor()

    insert_sql = """
        INSERT INTO portfolio_snapshots
            (snapshot_date, portfolio_name, total_value, daily_return,
             cumulative_return, volatility_30d, sharpe_30d, max_drawdown)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_date, portfolio_name) DO UPDATE SET
            total_value = EXCLUDED.total_value,
            daily_return = EXCLUDED.daily_return,
            cumulative_return = EXCLUDED.cumulative_return,
            volatility_30d = EXCLUDED.volatility_30d,
            sharpe_30d = EXCLUDED.sharpe_30d,
            max_drawdown = EXCLUDED.max_drawdown
    """

    cursor.execute(insert_sql, (
        snapshot_date,
        portfolio_name,
        total_value,
        metrics.get("daily_return"),
        metrics.get("cumulative_return"),
        metrics.get("volatility_30d"),
        metrics.get("sharpe_30d"),
        metrics.get("max_drawdown"),
    ))

    conn.commit()
    cursor.close()
    conn.close()


# =============================================================================
# Data Extraction (C8 - Database source)
# =============================================================================


def load_benchmarks(
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Load benchmark data from PostgreSQL.

    This is the main function demonstrating database extraction for C8.

    Args:
        start_date: Start date for data range. Defaults to 90 days ago.
        end_date: End date for data range. Defaults to today.

    Returns:
        Dictionary containing benchmark data:
        {
            "indices": {...},
            "portfolio_history": [...],
            "comparison": {...},
            "source": "postgresql"
        }

    Raises:
        DatabaseError: If query fails.

    Example:
        >>> benchmarks = load_benchmarks()
        >>> print(benchmarks["indices"]["SP500"])
    """
    logger.info("Loading benchmarks from PostgreSQL")

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=90)

    result: dict[str, Any] = {
        "source": "postgresql",
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
    }

    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # Load index data
        logger.info("Loading market indices")
        cursor.execute("""
            SELECT mi.index_name, id.date, id.close_value
            FROM index_daily id
            JOIN market_indices mi ON id.index_id = mi.index_id
            WHERE id.date BETWEEN %s AND %s
            ORDER BY mi.index_name, id.date
        """, (start_date, end_date))

        indices: dict[str, list[dict[str, Any]]] = {}
        for row in cursor.fetchall():
            index_name, dt, close_value = row
            if index_name not in indices:
                indices[index_name] = []
            indices[index_name].append({
                "date": dt.isoformat(),
                "close": float(close_value),
            })

        result["indices"] = indices
        logger.info(f"Loaded {len(indices)} indices")

        # Load portfolio history
        logger.info("Loading portfolio history")
        cursor.execute("""
            SELECT snapshot_date, portfolio_name, total_value,
                   daily_return, cumulative_return, volatility_30d,
                   sharpe_30d, max_drawdown
            FROM portfolio_snapshots
            WHERE snapshot_date BETWEEN %s AND %s
            ORDER BY portfolio_name, snapshot_date
        """, (start_date, end_date))

        portfolio_history: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            portfolio_history.append({
                "date": row[0].isoformat(),
                "portfolio": row[1],
                "total_value": float(row[2]) if row[2] else None,
                "daily_return": float(row[3]) if row[3] else None,
                "cumulative_return": float(row[4]) if row[4] else None,
                "volatility_30d": float(row[5]) if row[5] else None,
                "sharpe_30d": float(row[6]) if row[6] else None,
                "max_drawdown": float(row[7]) if row[7] else None,
            })

        result["portfolio_history"] = portfolio_history
        logger.info(f"Loaded {len(portfolio_history)} snapshots")

        # Load benchmark comparison
        logger.info("Loading benchmark comparisons")
        cursor.execute("""
            SELECT date, portfolio_name, benchmark_name,
                   portfolio_return, benchmark_return, alpha, beta
            FROM benchmark_comparison
            WHERE date BETWEEN %s AND %s
            ORDER BY date DESC
            LIMIT 100
        """, (start_date, end_date))

        comparisons: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            comparisons.append({
                "date": row[0].isoformat(),
                "portfolio": row[1],
                "benchmark": row[2],
                "portfolio_return": float(row[3]) if row[3] else None,
                "benchmark_return": float(row[4]) if row[4] else None,
                "alpha": float(row[5]) if row[5] else None,
                "beta": float(row[6]) if row[6] else None,
            })

        result["comparisons"] = comparisons
        logger.info(f"Loaded {len(comparisons)} comparisons")

        cursor.close()
        conn.close()

        return result

    except DatabaseError:
        raise
    except Exception as e:
        raise DatabaseError(f"Query failed: {e}") from e


def load_index_returns(
    index_name: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Load daily returns for a specific index.

    Args:
        index_name: Name of the index.
        start_date: Start date.
        end_date: End date.

    Returns:
        List of daily returns.
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=90)

    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id.date, id.close_value,
               (id.close_value - LAG(id.close_value) OVER (ORDER BY id.date))
               / LAG(id.close_value) OVER (ORDER BY id.date) as daily_return
        FROM index_daily id
        JOIN market_indices mi ON id.index_id = mi.index_id
        WHERE mi.index_name = %s AND id.date BETWEEN %s AND %s
        ORDER BY id.date
    """, (index_name, start_date, end_date))

    results = []
    for row in cursor.fetchall():
        results.append({
            "date": row[0].isoformat(),
            "close": float(row[1]),
            "daily_return": float(row[2]) if row[2] else None,
        })

    cursor.close()
    conn.close()

    return results


def get_benchmark_summary() -> dict[str, Any]:
    """
    Get summary statistics for all benchmarks.

    Returns:
        Summary statistics for each index.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            mi.index_name,
            MIN(id.date) as first_date,
            MAX(id.date) as last_date,
            COUNT(*) as data_points,
            MIN(id.close_value) as min_value,
            MAX(id.close_value) as max_value,
            AVG(id.close_value) as avg_value
        FROM index_daily id
        JOIN market_indices mi ON id.index_id = mi.index_id
        GROUP BY mi.index_name
    """)

    summary = {}
    for row in cursor.fetchall():
        summary[row[0]] = {
            "first_date": row[1].isoformat() if row[1] else None,
            "last_date": row[2].isoformat() if row[2] else None,
            "data_points": row[3],
            "min_value": float(row[4]) if row[4] else None,
            "max_value": float(row[5]) if row[5] else None,
            "avg_value": float(row[6]) if row[6] else None,
        }

    cursor.close()
    conn.close()

    return summary


# =============================================================================
# Sample Data Generation (for testing)
# =============================================================================


def generate_sample_data() -> None:
    """
    Generate sample benchmark data for testing.

    Creates realistic historical data for:
    - S&P 500 index
    - BTC index
    - Sample portfolio snapshots
    """
    import random

    logger.info("Generating sample benchmark data")

    # Generate 90 days of index data
    end_date = date.today()
    start_date = end_date - timedelta(days=90)

    # S&P 500 data (starting around 4800)
    sp500_data = []
    sp500_value = 4800.0
    current_date = start_date

    while current_date <= end_date:
        # Random daily return between -2% and +2%
        daily_return = random.gauss(0.0003, 0.01)  # Slight positive bias
        sp500_value *= (1 + daily_return)

        sp500_data.append({
            "date": current_date,
            "close_value": round(sp500_value, 2),
        })
        current_date += timedelta(days=1)

    # BTC index data (starting around 90000)
    btc_data = []
    btc_value = 90000.0
    current_date = start_date

    while current_date <= end_date:
        # Higher volatility for crypto
        daily_return = random.gauss(0.001, 0.03)
        btc_value *= (1 + daily_return)

        btc_data.append({
            "date": current_date,
            "close_value": round(btc_value, 2),
        })
        current_date += timedelta(days=1)

    # Insert data
    insert_index_data("SP500", sp500_data)
    logger.info(f"Inserted {len(sp500_data)} S&P 500 records")

    insert_index_data("BTC_INDEX", btc_data)
    logger.info(f"Inserted {len(btc_data)} BTC index records")

    logger.info("Sample data generation complete")


# =============================================================================
# Fallback: File-based simulation
# =============================================================================


def load_benchmarks_fallback() -> dict[str, Any]:
    """
    Fallback when PostgreSQL is not available.

    Returns simulated benchmark data from memory.
    Useful for testing without database setup.
    """
    logger.warning("Using fallback benchmark data (PostgreSQL not available)")

    import random
    random.seed(42)  # Reproducible

    end_date = date.today()
    start_date = end_date - timedelta(days=90)

    # Generate S&P 500 simulation
    sp500_data = []
    sp500_value = 4800.0
    current_date = start_date

    while current_date <= end_date:
        daily_return = random.gauss(0.0003, 0.01)
        sp500_value *= (1 + daily_return)
        sp500_data.append({
            "date": current_date.isoformat(),
            "close": round(sp500_value, 2),
        })
        current_date += timedelta(days=1)

    return {
        "source": "fallback_simulation",
        "indices": {
            "SP500": sp500_data,
        },
        "portfolio_history": [],
        "comparisons": [],
    }


# =============================================================================
# Main execution (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Testing PostgreSQL benchmark module...")
    print("=" * 50)

    # Test connection
    print("\n[1] Testing connection...")
    if test_connection():
        print("  Connection successful!")

        # Initialize schema
        print("\n[2] Initializing schema...")
        initialize_schema()

        # Generate sample data
        print("\n[3] Generating sample data...")
        generate_sample_data()

        # Load benchmarks
        print("\n[4] Loading benchmarks...")
        benchmarks = load_benchmarks()

        print("\n" + "=" * 50)
        print("BENCHMARK SUMMARY")
        print("=" * 50)
        summary = get_benchmark_summary()
        for index_name, stats in summary.items():
            print(f"\n{index_name}:")
            print(f"  Data points: {stats['data_points']}")
            print(f"  Range: {stats['first_date']} to {stats['last_date']}")
            print(f"  Value range: {stats['min_value']:.2f} - {stats['max_value']:.2f}")

    else:
        print("  Connection failed, using fallback...")
        benchmarks = load_benchmarks_fallback()

        print("\n" + "=" * 50)
        print("FALLBACK DATA")
        print("=" * 50)
        print(f"  Source: {benchmarks['source']}")
        print(f"  Indices: {list(benchmarks['indices'].keys())}")
