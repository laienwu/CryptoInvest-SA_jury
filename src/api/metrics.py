"""
Custom Prometheus business metrics for the portfolio platform.

These gauges and counters are updated by pipeline steps and exposed
via the ``/prom/metrics`` endpoint added by
``prometheus-fastapi-instrumentator``.
"""

from prometheus_client import Counter, Gauge

pipeline_last_run = Gauge(
    "pipeline_last_run_timestamp",
    "Unix timestamp of the last successful pipeline run",
)

records_ingested = Counter(
    "records_ingested_total",
    "Total number of records ingested across all runs",
    ["source"],
)

portfolio_sharpe = Gauge(
    "portfolio_sharpe_ratio",
    "Sharpe ratio of the current optimal portfolio",
)
