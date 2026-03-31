"""
PySpark transforms for large-scale portfolio analytics.

Provides distributed computation for rolling correlations, volatility
surfaces, and volume analysis using PySpark in local mode.

These complement the core PyArrow pipeline with Spark-based alternatives
suitable for larger datasets that benefit from parallel processing.

Usage:
    >>> from src.pipeline.spark_transforms import spark_rolling_correlation
    >>> result = spark_rolling_correlation(storage, window=30)
"""

import logging
from typing import Any

from src.storage import Storage

logger = logging.getLogger(__name__)

_spark_session = None


class SparkTransformError(Exception):
    """Custom exception for PySpark transform operations."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


def _get_spark() -> Any:
    """Get or create a local SparkSession (lazy singleton)."""
    global _spark_session
    if _spark_session is not None:
        return _spark_session

    try:
        from pyspark.sql import SparkSession
    except ImportError as e:
        raise SparkTransformError(
            "pyspark not installed. Install with: pip install pyspark",
            operation="import",
        ) from e

    _spark_session = (
        SparkSession.builder
        .master("local[*]")
        .appName("PortfolioAnalytics")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    return _spark_session


def _stop_spark() -> None:
    """Stop the SparkSession if active."""
    global _spark_session
    if _spark_session is not None:
        _spark_session.stop()
        _spark_session = None


def _load_prices_df(storage: Storage, spark: Any) -> Any:
    """Load raw data from storage into a Spark DataFrame."""
    from pyspark.sql.types import DoubleType, StringType, StructField, StructType

    raw = storage.load_raw()
    if not raw:
        raise SparkTransformError("No raw data in storage", operation="load")

    rows = []
    for symbol, records in raw.items():
        for r in records:
            rows.append((
                symbol,
                str(r["timestamp"]),
                float(r["close"]),
                float(r.get("volume", 0.0)),
            ))

    schema = StructType([
        StructField("symbol", StringType(), False),
        StructField("timestamp", StringType(), False),
        StructField("close", DoubleType(), False),
        StructField("volume", DoubleType(), False),
    ])

    return spark.createDataFrame(rows, schema)


def spark_rolling_correlation(
    storage: Storage, window: int = 30
) -> dict[str, Any]:
    """
    Compute rolling pairwise correlation using PySpark window functions.

    Args:
        storage: Storage backend to load data from.
        window: Rolling window size in periods.

    Returns:
        Dict with keys: pairs, window, n_periods.
    """
    spark = _get_spark()
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    df = _load_prices_df(storage, spark)

    # Compute log returns
    w = Window.partitionBy("symbol").orderBy("timestamp")
    df = df.withColumn("prev_close", F.lag("close").over(w))
    df = df.withColumn(
        "log_return",
        F.when(F.col("prev_close") > 0, F.log(F.col("close") / F.col("prev_close")))
    ).filter(F.col("log_return").isNotNull())

    symbols = sorted([row.symbol for row in df.select("symbol").distinct().collect()])
    if len(symbols) < 2:
        raise SparkTransformError(
            f"Need at least 2 symbols, got {len(symbols)}",
            operation="rolling_correlation",
        )

    # Pivot to wide format and compute pairwise rolling correlations
    pivot_df = (
        df.select("timestamp", "symbol", "log_return")
        .groupBy("timestamp")
        .pivot("symbol", symbols)
        .agg(F.first("log_return"))
        .orderBy("timestamp")
    )

    pairs_result = []
    rolling_w = Window.orderBy("timestamp").rowsBetween(-(window - 1), 0)

    for i, sym_a in enumerate(symbols):
        for sym_b in symbols[i + 1:]:
            col_a = F.col(f"`{sym_a}`")
            col_b = F.col(f"`{sym_b}`")

            # Rolling means
            mean_a = F.avg(col_a).over(rolling_w)
            mean_b = F.avg(col_b).over(rolling_w)

            # Rolling correlation components
            cov_ab = F.avg((col_a - mean_a) * (col_b - mean_b)).over(rolling_w)
            std_a = F.sqrt(F.avg((col_a - mean_a) ** 2).over(rolling_w))
            std_b = F.sqrt(F.avg((col_b - mean_b) ** 2).over(rolling_w))

            corr_col = F.when(
                (std_a > 0) & (std_b > 0), cov_ab / (std_a * std_b)
            )

            corr_df = pivot_df.select(
                "timestamp", corr_col.alias("correlation")
            ).orderBy("timestamp")

            corr_values = [
                row.correlation for row in corr_df.collect()
            ]

            pairs_result.append({
                "pair": f"{sym_a}/{sym_b}",
                "symbol_a": sym_a,
                "symbol_b": sym_b,
                "correlations": corr_values,
            })

    n_periods = pivot_df.count()
    logger.info(
        "Spark rolling correlation: %d pairs, window=%d, %d periods",
        len(pairs_result), window, n_periods,
    )

    return {
        "pairs": pairs_result,
        "window": window,
        "n_periods": n_periods,
    }


def spark_volatility_surface(
    storage: Storage, windows: list[int] | None = None
) -> dict[str, Any]:
    """
    Compute multi-window volatility surface using PySpark.

    Args:
        storage: Storage backend.
        windows: List of rolling window sizes. Defaults to [7, 14, 30, 60, 90].

    Returns:
        Dict with keys: symbols, windows, surface (symbol → window → vol).
    """
    if windows is None:
        windows = [7, 14, 30, 60, 90]

    spark = _get_spark()
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    df = _load_prices_df(storage, spark)

    # Log returns
    w = Window.partitionBy("symbol").orderBy("timestamp")
    df = df.withColumn("prev_close", F.lag("close").over(w))
    df = df.withColumn(
        "log_return",
        F.when(F.col("prev_close") > 0, F.log(F.col("close") / F.col("prev_close")))
    ).filter(F.col("log_return").isNotNull())

    symbols = sorted([row.symbol for row in df.select("symbol").distinct().collect()])
    surface: dict[str, dict[int, float | None]] = {s: {} for s in symbols}

    for win in windows:
        rolling_w = Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-(win - 1), 0)
        vol_df = df.withColumn("rolling_vol", F.stddev("log_return").over(rolling_w))

        # Get the last volatility value per symbol
        last_w = Window.partitionBy("symbol").orderBy(F.col("timestamp").desc())
        last_vol = (
            vol_df.withColumn("rn", F.row_number().over(last_w))
            .filter(F.col("rn") == 1)
            .select("symbol", "rolling_vol")
            .collect()
        )

        for row in last_vol:
            surface[row.symbol][win] = row.rolling_vol

    logger.info("Spark volatility surface: %d symbols, %d windows", len(symbols), len(windows))

    return {
        "symbols": symbols,
        "windows": windows,
        "surface": surface,
    }


def spark_volume_analysis(storage: Storage) -> dict[str, Any]:
    """
    Compute volume-weighted metrics across all symbols using PySpark.

    Args:
        storage: Storage backend.

    Returns:
        Dict with per-symbol volume stats: total, mean, max, vwap.
    """
    spark = _get_spark()
    from pyspark.sql import functions as F

    df = _load_prices_df(storage, spark)

    stats = (
        df.groupBy("symbol")
        .agg(
            F.sum("volume").alias("total_volume"),
            F.avg("volume").alias("mean_volume"),
            F.max("volume").alias("max_volume"),
            F.min("volume").alias("min_volume"),
            F.count("*").alias("n_records"),
            # VWAP = sum(close * volume) / sum(volume)
            (F.sum(F.col("close") * F.col("volume")) / F.sum("volume")).alias("vwap"),
        )
        .orderBy("symbol")
        .collect()
    )

    per_symbol = {}
    for row in stats:
        per_symbol[row.symbol] = {
            "total_volume": row.total_volume,
            "mean_volume": row.mean_volume,
            "max_volume": row.max_volume,
            "min_volume": row.min_volume,
            "n_records": row.n_records,
            "vwap": row.vwap,
        }

    logger.info("Spark volume analysis: %d symbols", len(per_symbol))

    return {
        "per_symbol": per_symbol,
        "n_symbols": len(per_symbol),
        "method": "spark_volume_analysis",
    }
