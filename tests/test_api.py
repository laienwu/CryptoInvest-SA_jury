"""
Tests for the FastAPI endpoints.

Uses dependency injection override to mock the storage backend,
making tests deterministic and independent of real data files.
"""

import pytest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.main import app, get_storage_dep
from src.storage import Storage


@pytest.fixture
def mock_storage():
    """Create a mock storage backend with realistic test data."""
    storage = MagicMock(spec=Storage)
    storage.list_raw_symbols.return_value = ["BTCUSDT", "ETHUSDT"]
    storage.list_processed.return_value = ["returns", "volatility"]
    storage.load_raw.return_value = {
        "BTCUSDT": [
            {
                "timestamp": "2024-01-01",
                "open": 42000.0,
                "high": 43000.0,
                "low": 41000.0,
                "close": 42500.0,
                "volume": 1000.0,
            }
        ]
    }
    storage.load_processed.return_value = {
        "BTCUSDT": [0.01, 0.02, -0.01],
        "ETHUSDT": [0.02, -0.01, 0.03],
    }
    storage.load_output.return_value = {
        "weights": {"BTCUSDT": 0.6, "ETHUSDT": 0.4},
        "expected_return": 0.15,
        "volatility": 0.20,
        "sharpe_ratio": 0.75,
    }
    return storage


@pytest.fixture
def client(mock_storage):
    """Create test client with mocked storage dependency."""
    app.dependency_overrides[get_storage_dep] = lambda: mock_storage
    yield TestClient(app)
    app.dependency_overrides.clear()


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

        assert data["status"] == "ok"
        assert data["message"] == "Portfolio API"


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

        assert data["symbols"] == ["BTCUSDT", "ETHUSDT"]
        assert data["count"] == 2


class TestKlinesEndpoint:
    """Tests for /klines/{symbol} endpoint."""

    def test_klines_valid_symbol(self, client):
        """Test klines with valid symbol returns data."""
        response = client.get("/klines/BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTCUSDT"
        assert data["count"] == 1
        assert data["data"][0]["close"] == 42500.0

    def test_klines_invalid_symbol(self, client, mock_storage):
        """Test klines with invalid symbol returns 404 or 500."""
        mock_storage.load_raw.return_value = {}
        response = client.get("/klines/INVALID_SYMBOL_XYZ")
        assert response.status_code in [404, 500]

    def test_klines_response_structure(self, client):
        """Test klines response structure."""
        response = client.get("/klines/BTCUSDT")
        data = response.json()

        assert "symbol" in data
        assert "count" in data
        assert "data" in data
        assert data["symbol"] == "BTCUSDT"


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

        assert data["metrics"] == ["returns", "volatility"]


class TestMetricDetailEndpoint:
    """Tests for /metrics/{name} endpoint."""

    def test_metric_valid_name(self, client):
        """Test metric with valid name returns data."""
        response = client.get("/metrics/returns")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "returns"
        assert "data" in data

    def test_metric_invalid_name(self, client, mock_storage):
        """Test metric with invalid name returns 404."""
        mock_storage.load_processed.side_effect = FileNotFoundError("not found")
        response = client.get("/metrics/invalid_metric_xyz")
        assert response.status_code == 404

    def test_metric_response_structure(self, client):
        """Test metric detail response structure."""
        response = client.get("/metrics/returns")
        data = response.json()

        assert "name" in data
        assert "data" in data
        assert data["name"] == "returns"


class TestPortfolioEndpoint:
    """Tests for /portfolio endpoint."""

    def test_portfolio_endpoint(self, client):
        """Test portfolio endpoint returns data."""
        response = client.get("/portfolio")
        assert response.status_code == 200
        data = response.json()
        assert "weights" in data

    def test_portfolio_not_found(self, client, mock_storage):
        """Test portfolio returns 404 when not computed."""
        mock_storage.load_output.side_effect = FileNotFoundError("not found")
        response = client.get("/portfolio")
        assert response.status_code == 404


class TestPortfolioSummaryEndpoint:
    """Tests for /portfolio/summary endpoint."""

    def test_portfolio_summary_endpoint(self, client):
        """Test portfolio summary endpoint returns data."""
        response = client.get("/portfolio/summary")
        assert response.status_code == 200

    def test_portfolio_summary_response_structure(self, client):
        """Test portfolio summary response structure."""
        response = client.get("/portfolio/summary")
        data = response.json()

        assert data["weights"] == {"BTCUSDT": 0.6, "ETHUSDT": 0.4}
        assert data["expected_return"] == 0.15
        assert data["volatility"] == 0.20
        assert data["sharpe_ratio"] == 0.75

    def test_portfolio_summary_not_found(self, client, mock_storage):
        """Test portfolio summary returns 404 when not computed."""
        mock_storage.load_output.side_effect = FileNotFoundError("not found")
        response = client.get("/portfolio/summary")
        assert response.status_code == 404


class TestAPIResponseFormat:
    """Tests for API response format consistency."""

    def test_json_content_type(self, client):
        """Test all endpoints return JSON."""
        endpoints = ["/", "/symbols", "/metrics"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.headers.get("content-type", "").startswith("application/json")

    def test_error_response_format(self, client, mock_storage):
        """Test error responses have proper format."""
        mock_storage.load_raw.return_value = {}
        response = client.get("/klines/NONEXISTENT_SYMBOL_XYZ")

        if response.status_code >= 400:
            data = response.json()
            assert "detail" in data


class TestAPIEdgeCases:
    """Tests for API edge cases."""

    def test_empty_symbol_parameter(self, client):
        """Test handling of empty symbol parameter."""
        response = client.get("/klines/")
        assert response.status_code in [404, 405, 422]

    def test_special_characters_in_symbol(self, client, mock_storage):
        """Test handling of special characters in symbol."""
        mock_storage.load_raw.return_value = {}
        response = client.get("/klines/BTC<>USDT")
        assert response.status_code in [404, 422, 500]

    def test_very_long_symbol(self, client, mock_storage):
        """Test handling of very long symbol name."""
        mock_storage.load_raw.return_value = {}
        long_symbol = "A" * 1000
        response = client.get(f"/klines/{long_symbol}")
        assert response.status_code in [404, 422, 500]
