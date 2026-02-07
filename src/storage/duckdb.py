"""
DuckDB storage implementation for the portfolio optimization project.

Covers:
- C9: SQL queries for extraction
- C13: Star schema (faits/dimensions)
- C14: Data warehouse creation

DuckDB queries Parquet files directly - no data duplication.

Star Schema:
- dim_symbol: symbol dimension
- dim_date: date dimension
- fact_prices: OHLCV facts

Example usage:
    >>> from src.storage import get_storage
    >>> storage = get_storage("duckdb")
    >>> storage.query("SELECT * FROM fact_prices LIMIT 10")
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import Storage, StorageError

# DuckDB import with availability check
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    duckdb = None


DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data"


class DuckDBStorage(Storage):
    """
    DuckDB-based storage with SQL capabilities.

    Reads existing Parquet files via SQL queries.
    Provides star schema views for analytical queries.
    """

    def __init__(self, data_dir: str | Path | None = None):
        if not DUCKDB_AVAILABLE:
            raise StorageError("DuckDB not installed. Run: uv add duckdb")

        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self._ensure_directories()
        self.conn = duckdb.connect(":memory:")
        self._setup_views()

    def _ensure_directories(self) -> None:
        (self.data_dir / "raw" / "klines").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "processed").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "output").mkdir(parents=True, exist_ok=True)

    def _setup_views(self) -> None:
        """Create star schema views on Parquet files."""
        klines_dir = self.data_dir / "raw" / "klines"

        # Create fact_prices view from all klines parquet files
        parquet_files = list(klines_dir.glob("*.parquet"))
        if parquet_files:
            # Union all symbol files with symbol column
            unions = []
            for f in parquet_files:
                symbol = f.stem
                unions.append(f"""
                    SELECT
                        '{symbol}' as symbol,
                        timestamp,
                        open, high, low, close, volume
                    FROM read_parquet('{f.as_posix()}')
                """)

            union_sql = " UNION ALL ".join(unions)
            self.conn.execute(f"""
                CREATE OR REPLACE VIEW fact_prices AS {union_sql}
            """)

            # dim_symbol: unique symbols
            self.conn.execute("""
                CREATE OR REPLACE VIEW dim_symbol AS
                SELECT symbol, ROW_NUMBER() OVER (ORDER BY symbol) as symbol_id
                FROM (SELECT DISTINCT symbol FROM fact_prices)
            """)

            # dim_date: unique dates
            self.conn.execute("""
                CREATE OR REPLACE VIEW dim_date AS
                SELECT DISTINCT
                       timestamp as date,
                       ROW_NUMBER() OVER (ORDER BY timestamp) as date_id,
                       EXTRACT(YEAR FROM CAST(timestamp AS DATE)) as year,
                       EXTRACT(MONTH FROM CAST(timestamp AS DATE)) as month,
                       EXTRACT(DAY FROM CAST(timestamp AS DATE)) as day,
                       EXTRACT(DOW FROM CAST(timestamp AS DATE)) as day_of_week
                FROM fact_prices
            """)

    def query(self, sql: str) -> list[dict]:
        """
        Execute SQL query and return results as list of dicts.

        This is the key method for C9 (SQL extraction).

        Args:
            sql: SQL query string

        Returns:
            List of dictionaries (one per row)
        """
        try:
            result = self.conn.execute(sql).fetchall()
            columns = [desc[0] for desc in self.conn.description]
            return [dict(zip(columns, row)) for row in result]
        except Exception as e:
            raise StorageError(f"Query failed: {e}", operation="query")

    def query_df(self, sql: str):
        """Execute SQL and return DuckDB relation (for chaining)."""
        return self.conn.execute(sql)

    # -------------------------------------------------------------------------
    # Raw Data Operations (delegate to Parquet, add SQL layer)
    # -------------------------------------------------------------------------

    def save_raw(self, data: dict[str, list[dict]], metadata: dict | None = None) -> str:
        """Save raw data as Parquet files, then refresh SQL views."""
        from ._utils import write_klines_parquet

        if not data:
            raise StorageError("No data provided", operation="save_raw")

        klines_dir = self.data_dir / "raw" / "klines"
        for symbol, records in data.items():
            if not records:
                continue
            write_klines_parquet(
                symbol, records, klines_dir / f"{symbol}.parquet", metadata
            )

        # Refresh views after new data
        self._setup_views()
        return str(klines_dir)

    def load_raw(self, symbols: list[str] | None = None) -> dict[str, list[dict]]:
        """Load raw data via SQL query."""
        if symbols:
            symbols_str = ", ".join(f"'{s}'" for s in symbols)
            sql = f"SELECT * FROM fact_prices WHERE symbol IN ({symbols_str})"
        else:
            sql = "SELECT * FROM fact_prices"

        rows = self.query(sql)

        # Group by symbol
        result: dict[str, list[dict]] = {}
        for row in rows:
            symbol = row.pop("symbol")
            if symbol not in result:
                result[symbol] = []
            result[symbol].append(row)

        if not result:
            raise StorageError("No raw data found", operation="load_raw")
        return result

    # -------------------------------------------------------------------------
    # Processed Data Operations
    # -------------------------------------------------------------------------

    def save_processed(self, data: dict[str, Any], name: str) -> str:
        """Save processed data as Parquet."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        file_path = self.data_dir / "processed" / f"{name}.parquet"

        if "matrix" in data and "symbols" in data:
            symbols = data["symbols"]
            matrix = data["matrix"]
            rows = [(s1, s2, float(matrix[i][j]))
                    for i, s1 in enumerate(symbols)
                    for j, s2 in enumerate(symbols)]
            table = pa.table({
                "symbol_row": [r[0] for r in rows],
                "symbol_col": [r[1] for r in rows],
                "value": [r[2] for r in rows],
            })
        elif "values" in data and "symbols" in data and "dates" in data:
            rows = [(d, s, float(data["values"][i][j]))
                    for i, s in enumerate(data["symbols"])
                    for j, d in enumerate(data["dates"])]
            table = pa.table({
                "date": [r[0] for r in rows],
                "symbol": [r[1] for r in rows],
                "value": [r[2] for r in rows],
            })
        else:
            table = pa.table({"data": [json.dumps(data)]})

        pq.write_table(table, file_path)
        return str(file_path)

    def load_processed(self, name: str) -> dict[str, Any]:
        """Load processed data via SQL."""
        file_path = self.data_dir / "processed" / f"{name}.parquet"
        if not file_path.exists():
            raise StorageError(f"Not found: {name}", operation="load_processed")

        # Query the parquet file directly
        rows = self.query(f"SELECT * FROM read_parquet('{file_path.as_posix()}')")

        if not rows:
            raise StorageError(f"Empty: {name}", operation="load_processed")

        # Detect structure
        if "symbol_row" in rows[0]:
            symbols = list(dict.fromkeys(r["symbol_row"] for r in rows))
            n = len(symbols)
            idx = {s: i for i, s in enumerate(symbols)}
            matrix = [[0.0] * n for _ in range(n)]
            for r in rows:
                matrix[idx[r["symbol_row"]]][idx[r["symbol_col"]]] = r["value"]
            return {"symbols": symbols, "matrix": matrix}
        elif "date" in rows[0] and "symbol" in rows[0]:
            dates = list(dict.fromkeys(r["date"] for r in rows))
            symbols = list(dict.fromkeys(r["symbol"] for r in rows))
            values = [[0.0] * len(dates) for _ in range(len(symbols))]
            d_idx = {d: i for i, d in enumerate(dates)}
            s_idx = {s: i for i, s in enumerate(symbols)}
            for r in rows:
                values[s_idx[r["symbol"]]][d_idx[r["date"]]] = r["value"]
            return {"symbols": symbols, "dates": dates, "values": values}
        elif "data" in rows[0]:
            return json.loads(rows[0]["data"])

        raise StorageError(f"Unknown structure: {name}", operation="load_processed")

    # -------------------------------------------------------------------------
    # Output Operations (JSON, same as Parquet)
    # -------------------------------------------------------------------------

    def save_output(self, data: dict[str, Any], name: str) -> str:
        file_path = self.data_dir / "output" / f"{name}.json"
        with open(file_path, "w") as f:
            json.dump({"_metadata": {"saved_at": datetime.now().isoformat()}, **data}, f, indent=2)
        return str(file_path)

    def load_output(self, name: str) -> dict[str, Any]:
        file_path = self.data_dir / "output" / f"{name}.json"
        if not file_path.exists():
            raise StorageError(f"Not found: {name}", operation="load_output")
        with open(file_path) as f:
            data = json.load(f)
        data.pop("_metadata", None)
        return data

    # -------------------------------------------------------------------------
    # List Operations
    # -------------------------------------------------------------------------

    def list_raw_symbols(self) -> list[str]:
        try:
            rows = self.query("SELECT DISTINCT symbol FROM dim_symbol ORDER BY symbol")
            return [r["symbol"] for r in rows]
        except (StorageError, Exception):
            return []

    def list_processed(self) -> list[str]:
        return sorted(f.stem for f in (self.data_dir / "processed").glob("*.parquet"))

    def list_outputs(self) -> list[str]:
        return sorted(f.stem for f in (self.data_dir / "output").glob("*.json"))

    # -------------------------------------------------------------------------
    # Star Schema Queries (C13 - faits/dimensions)
    # -------------------------------------------------------------------------

    def get_prices_by_symbol(self, symbol: str) -> list[dict]:
        """Get all prices for a symbol (fact query with dimension filter)."""
        return self.query(f"""
            SELECT f.*, d.year, d.month, d.day_of_week
            FROM fact_prices f
            JOIN dim_date d ON f.timestamp = d.date
            WHERE f.symbol = '{symbol}'
            ORDER BY f.timestamp
        """)

    def get_daily_returns(self) -> list[dict]:
        """Calculate daily returns using SQL (C9 demo)."""
        return self.query("""
            SELECT
                symbol,
                timestamp,
                close,
                (close - LAG(close) OVER (PARTITION BY symbol ORDER BY timestamp))
                    / LAG(close) OVER (PARTITION BY symbol ORDER BY timestamp) as daily_return
            FROM fact_prices
            ORDER BY symbol, timestamp
        """)

    def get_summary_stats(self) -> list[dict]:
        """Aggregate stats per symbol (analytical query demo)."""
        return self.query("""
            SELECT
                symbol,
                COUNT(*) as num_records,
                MIN(timestamp) as start_date,
                MAX(timestamp) as end_date,
                AVG(close) as avg_close,
                MIN(close) as min_close,
                MAX(close) as max_close,
                AVG(volume) as avg_volume
            FROM fact_prices
            GROUP BY symbol
            ORDER BY symbol
        """)
