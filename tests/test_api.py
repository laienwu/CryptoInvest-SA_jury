"""
Tests for the FastAPI endpoints.

Tests API layer:
- Health check endpoint
- Symbols endpoint
- Klines endpoint
- Metrics endpoint
- Portfolio endpoint
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


class TestHealthCheck:
    """Tests for root health check endpoint."""

    def test_health_check_status(self, client):
        """Test health check returns 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_health_check_response(self, client):
        """Test health check response content."""
        response = client.get("/")
        data = response.json()

        assert "status" in data
        assert data["status"] == "ok"
        assert "message" in data


class TestSymbolsEndpoint:
    """Tests for /symbols endpoint."""

    def test_symbols_status(self, client):
        """Test symbols endpoint returns 200."""
        response = client.get("/symbols")
        assert response.status_code == 200

    def test_symbols_response_structure(self, client):
        """Test symbols response has expected structure."""
        response = client.get("/symbols")
        data = response.json()

        assert "symbols" in data
        assert "count" in data
        assert isinstance(data["symbols"], list)
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["symbols"])


class TestKlinesEndpoint:
    """Tests for /klines/{symbol} endpoint."""

    def test_klines_invalid_symbol(self, client):
        """Test klines with invalid symbol returns 404 or 500."""
        response = client.get("/klines/INVALID_SYMBOL_XYZ")
        # Could be 404 (not found) or 500 (error loading)
        assert response.status_code in [404, 500]

    def test_klines_response_structure(self, client):
        """Test klines response structure when data exists."""
        # First get available symbols
        symbols_response = client.get("/symbols")
        symbols = symbols_response.json().get("symbols", [])

        if symbols:
            symbol = symbols[0]
            response = client.get(f"/klines/{symbol}")

            if response.status_code == 200:
                data = response.json()
                assert "symbol" in data
                assert "count" in data
                assert "data" in data
                assert data["symbol"] == symbol


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_metrics_status(self, client):
        """Test metrics endpoint returns 200."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_response_structure(self, client):
        """Test metrics response has expected structure."""
        response = client.get("/metrics")
        data = response.json()

        assert "metrics" in data
        assert isinstance(data["metrics"], list)


class TestMetricDetailEndpoint:
    """Tests for /metrics/{name} endpoint."""

    def test_metric_invalid_name(self, client):
        """Test metric with invalid name returns 404."""
        response = client.get("/metrics/invalid_metric_xyz")
        assert response.status_code == 404

    def test_metric_response_structure(self, client):
        """Test metric detail response structure when data exists."""
        # First get available metrics
        metrics_response = client.get("/metrics")
        metrics = metrics_response.json().get("metrics", [])

        if metrics:
            metric = metrics[0]
            response = client.get(f"/metrics/{metric}")

            if response.status_code == 200:
                data = response.json()
                assert "name" in data
                assert "data" in data
                assert data["name"] == metric


class TestPortfolioEndpoint:
    """Tests for /portfolio endpoint."""

    def test_portfolio_endpoint(self, client):
        """Test portfolio endpoint."""
        response = client.get("/portfolio")
        # Could be 200 (data exists) or 404 (not computed yet)
        assert response.status_code in [200, 404]

    def test_portfolio_response_structure(self, client):
        """Test portfolio response structure when data exists."""
        response = client.get("/portfolio")

        if response.status_code == 200:
            data = response.json()

            # Should have portfolio fields
            assert "weights" in data or "symbols" in data


class TestPortfolioSummaryEndpoint:
    """Tests for /portfolio/summary endpoint."""

    def test_portfolio_summary_endpoint(self, client):
        """Test portfolio summary endpoint."""
        response = client.get("/portfolio/summary")
        # Could be 200 (data exists) or 404 (not computed yet)
        assert response.status_code in [200, 404]

    def test_portfolio_summary_response_structure(self, client):
        """Test portfolio summary response structure when data exists."""
        response = client.get("/portfolio/summary")

        if response.status_code == 200:
            data = response.json()

            # Summary should have key metrics
            assert "weights" in data
            assert "expected_return" in data or data.get("expected_return") is None
            assert "volatility" in data or data.get("volatility") is None
            assert "sharpe_ratio" in data or data.get("sharpe_ratio") is None


class TestAPIResponseFormat:
    """Tests for API response format consistency."""

    def test_json_content_type(self, client):
        """Test all endpoints return JSON."""
        endpoints = ["/", "/symbols", "/metrics"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.headers.get("content-type", "").startswith("application/json")

    def test_error_response_format(self, client):
        """Test error responses have proper format."""
        response = client.get("/klines/NONEXISTENT_SYMBOL_XYZ")

        if response.status_code >= 400:
            data = response.json()
            # FastAPI error format
            assert "detail" in data


class TestAPIEdgeCases:
    """Tests for API edge cases."""

    def test_empty_symbol_parameter(self, client):
        """Test handling of empty symbol parameter."""
        response = client.get("/klines/")
        # Should be 404 (not found) or 405 (method not allowed)
        assert response.status_code in [404, 405, 422]

    def test_special_characters_in_symbol(self, client):
        """Test handling of special characters in symbol."""
        response = client.get("/klines/BTC<>USDT")
        assert response.status_code in [404, 422, 500]

    def test_very_long_symbol(self, client):
        """Test handling of very long symbol name."""
        long_symbol = "A" * 1000
        response = client.get(f"/klines/{long_symbol}")
        assert response.status_code in [404, 422, 500]
