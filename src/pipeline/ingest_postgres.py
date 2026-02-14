"""
PostgreSQL database module for historical benchmarks.

Demonstrates C8 compliance: extraction from a relational database.

This module provides:
- ``BenchmarkRepository``: connection-managed repository for all DB operations
- Module-level convenience functions (``load_benchmarks``, etc.) for backwards compat

Schema creation is handled by ``scripts/init-benchmarks.sql`` via Docker
entrypoint — this module only reads and writes data.

Example usage::

    # Quick one-shot (creates and closes its own connection):
    from src.pipeline.ingest_postgres import load_benchmarks
    benchmarks = load_benchmarks()

    # Connection reuse + atomic transaction:
    from src.pipeline.ingest_postgres import BenchmarkRepository
    from src.config import DatabaseConfig

    with BenchmarkRepository(DatabaseConfig(host="db")) as repo:
        repo.insert_index_data("SP500", data)
        repo.insert_portfolio_snapshot("crypto", today, 100_000, metrics)
        # single commit on exit
"""

from __future__ import annotations

import logging
import random
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any, Self

from src.config import DatabaseConfig, load_db_config

logger = logging.getLogger(__name__)


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
# Repository
# =============================================================================


class BenchmarkRepository:
    """Connection-managed repository for PostgreSQL benchmark operations.

    Accepts a ``DatabaseConfig`` at construction time (dependency injection).
    When no config is provided, falls back to ``load_db_config()`` which reads
    TOML + environment variables.

    Can be used two ways:

    **One-shot** — each method opens and closes its own connection::

        repo = BenchmarkRepository()
        data = repo.load_benchmarks()

    **Context manager** — single connection, atomic transaction::

        with BenchmarkRepository(config) as repo:
            repo.insert_index_data("SP500", sp500_data)
            repo.insert_portfolio_snapshot("crypto", today, 100_000, metrics)
            # commits on success, rolls back on exception
    """

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self._config = config or load_db_config()
        self._conn: Any = None

    # -- Context manager protocol ---------------------------------------------

    def __enter__(self) -> Self:
        self._conn = self._open_connection()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._conn is not None:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._conn.close()
            self._conn = None

    # -- Internal connection helpers ------------------------------------------

    def _open_connection(self) -> Any:
        """Create a new psycopg2 connection from the stored config."""
        try:
            import psycopg2
        except ImportError as exc:
            raise DatabaseError("psycopg2 required: uv add psycopg2-binary") from exc

        try:
            return psycopg2.connect(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.user,
                password=self._config.password,
            )
        except psycopg2.Error as e:
            raise DatabaseError(f"Connection failed: {e}") from e

    @contextmanager
    def _connect(self) -> Generator[Any]:
        """Yield a connection.

        When inside a ``with BenchmarkRepository() as repo:`` block, reuses
        the persistent connection (no commit — the outer ``__exit__`` handles
        that).  Otherwise, creates a temporary connection that commits on
        success and rolls back on exception.
        """
        if self._conn is not None:
            yield self._conn
        else:
            conn = self._open_connection()
            try:
                with conn:  # psycopg2: commit on success, rollback on exception
                    yield conn
            finally:
                conn.close()

    # -- Public API -----------------------------------------------------------

    def test_connection(self) -> bool:
        """Test database connectivity.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            with self._connect():
                return True
        except DatabaseError:
            return False

    def insert_index_data(
        self,
        index_name: str,
        data: list[dict[str, Any]],
    ) -> int:
        """Insert historical index data.

        Args:
            index_name: Name of the index (e.g., 'SP500').
            data: List of daily records with date, close_value, etc.

        Returns:
            Number of rows inserted.

        Raises:
            DatabaseError: If the index is not found or insertion fails.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT index_id FROM market_indices WHERE index_name = %s",
                (index_name,),
            )
            result = cur.fetchone()

            if not result:
                raise DatabaseError(f"Index not found: {index_name}")

            index_id = result[0]

            insert_sql = """
                INSERT INTO index_daily
                    (index_id, date, close_value, open_value,
                     high_value, low_value, volume)
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
                cur.execute(insert_sql, (
                    index_id,
                    record["date"],
                    record.get("close_value") or record.get("close"),
                    record.get("open_value") or record.get("open"),
                    record.get("high_value") or record.get("high"),
                    record.get("low_value") or record.get("low"),
                    record.get("volume"),
                ))
                rows_inserted += 1

        return rows_inserted

    def insert_portfolio_snapshot(
        self,
        portfolio_name: str,
        snapshot_date: date,
        total_value: float,
        metrics: dict[str, float],
    ) -> None:
        """Insert a portfolio performance snapshot.

        Args:
            portfolio_name: Name of the portfolio.
            snapshot_date: Date of the snapshot.
            total_value: Total portfolio value.
            metrics: Performance metrics (daily_return, volatility, etc.).
        """
        with self._connect() as conn, conn.cursor() as cur:
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

            cur.execute(insert_sql, (
                snapshot_date,
                portfolio_name,
                total_value,
                metrics.get("daily_return"),
                metrics.get("cumulative_return"),
                metrics.get("volatility_30d"),
                metrics.get("sharpe_30d"),
                metrics.get("max_drawdown"),
            ))

    def load_benchmarks(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Load benchmark data from PostgreSQL.

        This is the main function demonstrating database extraction for C8.

        Args:
            start_date: Start date for data range. Defaults to 90 days ago.
            end_date: End date for data range. Defaults to today.

        Returns:
            Dictionary containing benchmark data with keys:
            ``indices``, ``portfolio_history``, ``comparisons``, ``source``.

        Raises:
            DatabaseError: If query fails.
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
            with self._connect() as conn, conn.cursor() as cur:
                # Load index data
                logger.info("Loading market indices")
                cur.execute("""
                    SELECT mi.index_name, id.date, id.close_value
                    FROM index_daily id
                    JOIN market_indices mi ON id.index_id = mi.index_id
                    WHERE id.date BETWEEN %s AND %s
                    ORDER BY mi.index_name, id.date
                """, (start_date, end_date))

                indices: dict[str, list[dict[str, Any]]] = {}
                for row in cur.fetchall():
                    idx_name, dt, close_value = row
                    if idx_name not in indices:
                        indices[idx_name] = []
                    indices[idx_name].append({
                        "date": dt.isoformat(),
                        "close": float(close_value),
                    })

                result["indices"] = indices
                logger.info(f"Loaded {len(indices)} indices")

                # Load portfolio history
                logger.info("Loading portfolio history")
                cur.execute("""
                    SELECT snapshot_date, portfolio_name, total_value,
                           daily_return, cumulative_return, volatility_30d,
                           sharpe_30d, max_drawdown
                    FROM portfolio_snapshots
                    WHERE snapshot_date BETWEEN %s AND %s
                    ORDER BY portfolio_name, snapshot_date
                """, (start_date, end_date))

                portfolio_history: list[dict[str, Any]] = []
                for row in cur.fetchall():
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
                cur.execute("""
                    SELECT date, portfolio_name, benchmark_name,
                           portfolio_return, benchmark_return, alpha, beta
                    FROM benchmark_comparison
                    WHERE date BETWEEN %s AND %s
                    ORDER BY date DESC
                    LIMIT 100
                """, (start_date, end_date))

                comparisons: list[dict[str, Any]] = []
                for row in cur.fetchall():
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

            return result

        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Query failed: {e}") from e

    def load_index_returns(
        self,
        index_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Load daily returns for a specific index.

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

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id.date, id.close_value,
                       (id.close_value - LAG(id.close_value) OVER (ORDER BY id.date))
                       / LAG(id.close_value) OVER (ORDER BY id.date) as daily_return
                FROM index_daily id
                JOIN market_indices mi ON id.index_id = mi.index_id
                WHERE mi.index_name = %s AND id.date BETWEEN %s AND %s
                ORDER BY id.date
            """, (index_name, start_date, end_date))

            results = []
            for row in cur.fetchall():
                results.append({
                    "date": row[0].isoformat(),
                    "close": float(row[1]),
                    "daily_return": float(row[2]) if row[2] else None,
                })

        return results

    def get_benchmark_summary(self) -> dict[str, Any]:
        """Get summary statistics for all benchmarks.

        Returns:
            Summary statistics for each index.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
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
            for row in cur.fetchall():
                summary[row[0]] = {
                    "first_date": row[1].isoformat() if row[1] else None,
                    "last_date": row[2].isoformat() if row[2] else None,
                    "data_points": row[3],
                    "min_value": float(row[4]) if row[4] else None,
                    "max_value": float(row[5]) if row[5] else None,
                    "avg_value": float(row[6]) if row[6] else None,
                }

        return summary


# =============================================================================
# Fallback: In-memory simulation (no DB needed)
# =============================================================================


def load_benchmarks_fallback() -> dict[str, Any]:
    """Fallback when PostgreSQL is not available.

    Returns simulated benchmark data from memory.
    Useful for testing without database setup.

    Uses a local RNG instance to avoid mutating global random state.
    """
    logger.warning("Using fallback benchmark data (PostgreSQL not available)")

    rng = random.Random(42)

    end_date = date.today()
    start_date = end_date - timedelta(days=90)

    sp500_data = []
    sp500_value = 4800.0
    current_date = start_date

    while current_date <= end_date:
        daily_return = rng.gauss(0.0003, 0.01)
        sp500_value *= 1 + daily_return
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
# Module-level convenience functions (backwards compatibility)
# =============================================================================


def load_benchmarks(
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """Load benchmarks via a one-shot ``BenchmarkRepository``.

    Convenience wrapper that preserves the original module-level API.
    For connection reuse, instantiate ``BenchmarkRepository`` directly.
    """
    return BenchmarkRepository().load_benchmarks(start_date, end_date)


def test_connection() -> bool:
    """Test connectivity via a one-shot ``BenchmarkRepository``."""
    return BenchmarkRepository().test_connection()
