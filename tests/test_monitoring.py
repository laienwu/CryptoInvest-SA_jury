"""
Tests for Prometheus monitoring integration.

Verifies that the /prom/metrics endpoint is exposed and that custom
business metrics are registered in the default Prometheus registry.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.main import app, get_storage_dep
from src.storage import Storage


@pytest.fixture
def mock_storage():
    """Create a mock storage backend (same pattern as test_api.py)."""
    storage = MagicMock(spec=Storage)
    storage.list_raw_symbols.return_value = ["BTCUSDT"]
    storage.list_processed.return_value = ["returns"]
    return storage


@pytest.fixture
def client(mock_storage):
    """Create test client with mocked storage dependency."""
    app.dependency_overrides[get_storage_dep] = lambda: mock_storage
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestPrometheusEndpoint:
    """Tests for the /prom/metrics Prometheus scrape endpoint."""

    def test_metrics_endpoint_returns_200(self, client):
        """The Prometheus scrape endpoint must be reachable."""
        response = client.get("/prom/metrics")
        assert response.status_code == 200

    def test_metrics_endpoint_content_type(self, client):
        """Prometheus expects text/plain or openmetrics content."""
        response = client.get("/prom/metrics")
        content_type = response.headers.get("content-type", "")
        # prometheus-fastapi-instrumentator returns text/plain or
        # application/openmetrics-text depending on Accept header.
        assert "text/plain" in content_type or "openmetrics" in content_type

    def test_metrics_contains_http_request_metric(self, client):
        """Standard HTTP metrics should be present after at least one request."""
        # Make a request first so the instrumentator records something
        client.get("/")
        response = client.get("/prom/metrics")
        body = response.text
        assert "http_request_duration_seconds" in body or "http_requests" in body


class TestCustomBusinessMetrics:
    """Tests that custom business metrics are registered in the Prometheus registry."""

    def test_pipeline_last_run_registered(self, client):
        """pipeline_last_run_timestamp gauge must appear in /prom/metrics."""
        response = client.get("/prom/metrics")
        assert "pipeline_last_run_timestamp" in response.text

    def test_records_ingested_registered(self, client):
        """records_ingested_total counter must appear in /prom/metrics."""
        response = client.get("/prom/metrics")
        assert "records_ingested_total" in response.text

    def test_portfolio_sharpe_registered(self, client):
        """portfolio_sharpe_ratio gauge must appear in /prom/metrics."""
        response = client.get("/prom/metrics")
        assert "portfolio_sharpe_ratio" in response.text


class TestExistingMetricsEndpointUnaffected:
    """Ensure the original /metrics endpoint (financial metrics) still works."""

    def test_financial_metrics_endpoint_still_works(self, client):
        """The /metrics endpoint must still return the processed metrics list."""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
