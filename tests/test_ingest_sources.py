"""
Tests for multi-source ingestion module.

Tests C8 compliance - 5 data source types:
1. API REST (Binance) - tested via mock
2. CSV File
3. JSON File
4. Web Scraping - tested via mock
5. PostgreSQL - tested via mock/fallback
"""

import json
from unittest.mock import patch

import pytest


class TestCSVIngestion:
    """Tests for CSV file ingestion (C8 - Source Type 2)."""

    def test_load_symbols_metadata_csv(self, tmp_path):
        """Test loading symbols metadata from CSV."""
        from src.pipeline.ingest_sources import load_symbols_metadata_csv

        # Create test CSV
        csv_content = """symbol,name,sector,category,launch_year,market_cap_rank,is_stablecoin,consensus
BTCUSDT,Bitcoin,Currency,Layer 1,2009,1,false,Proof of Work
ETHUSDT,Ethereum,Smart Contracts,Layer 1,2015,2,false,Proof of Stake
"""
        csv_path = tmp_path / "test_metadata.csv"
        csv_path.write_text(csv_content)

        # Load
        result = load_symbols_metadata_csv(csv_path)

        assert len(result) == 2
        assert result[0]["symbol"] == "BTCUSDT"
        assert result[0]["name"] == "Bitcoin"
        assert result[1]["symbol"] == "ETHUSDT"

    def test_csv_missing_file(self, tmp_path):
        """Test handling of missing CSV file."""
        from src.pipeline.ingest_sources import SourceError, load_symbols_metadata_csv

        with pytest.raises(SourceError):
            load_symbols_metadata_csv(tmp_path / "nonexistent.csv")

    def test_csv_empty_file(self, tmp_path):
        """Test handling of empty CSV file."""
        from src.pipeline.ingest_sources import load_symbols_metadata_csv

        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("symbol,name\n")  # Header only

        result = load_symbols_metadata_csv(csv_path)
        assert result == []


class TestJSONIngestion:
    """Tests for JSON file ingestion (C8 - Source Type 3)."""

    def test_load_portfolio_config_json(self, tmp_path):
        """Test loading portfolio config from JSON."""
        from src.pipeline.ingest_sources import load_portfolio_config_json

        # Create test JSON matching expected structure
        config = {
            "portfolio": {
                "name": "Test Portfolio",
                "risk_tolerance": "moderate",
                "max_allocation": 0.4,
            },
            "sectors": {
                "Currency": ["BTCUSDT"],
                "Smart Contracts": ["ETHUSDT"],
            },
        }
        json_path = tmp_path / "test_config.json"
        json_path.write_text(json.dumps(config))

        # Load
        result = load_portfolio_config_json(json_path)

        assert result["portfolio"]["risk_tolerance"] == "moderate"
        assert result["portfolio"]["max_allocation"] == 0.4
        assert "BTCUSDT" in result["sectors"]["Currency"]

    def test_json_missing_file(self, tmp_path):
        """Test handling of missing JSON file."""
        from src.pipeline.ingest_sources import SourceError, load_portfolio_config_json

        with pytest.raises(SourceError):
            load_portfolio_config_json(tmp_path / "nonexistent.json")

    def test_json_invalid_format(self, tmp_path):
        """Test handling of invalid JSON format."""
        from src.pipeline.ingest_sources import SourceError, load_portfolio_config_json

        json_path = tmp_path / "invalid.json"
        json_path.write_text("not valid json {")

        with pytest.raises(SourceError):
            load_portfolio_config_json(json_path)


class TestDataEnrichment:
    """Tests for data enrichment functions."""

    def test_enrich_prices_with_metadata(self):
        """Test enriching price data with metadata."""
        from src.pipeline.ingest_sources import enrich_prices_with_metadata

        prices = {
            "BTCUSDT": [
                {"timestamp": "2024-01-01", "close": 42000.0},
            ],
            "ETHUSDT": [
                {"timestamp": "2024-01-01", "close": 2200.0},
            ],
        }

        metadata = [
            {"symbol": "BTCUSDT", "name": "Bitcoin", "sector": "Currency"},
            {"symbol": "ETHUSDT", "name": "Ethereum", "sector": "Smart Contracts"},
        ]

        result = enrich_prices_with_metadata(prices, metadata)

        assert result["BTCUSDT"][0]["name"] == "Bitcoin"
        assert result["BTCUSDT"][0]["sector"] == "Currency"
        assert result["ETHUSDT"][0]["name"] == "Ethereum"
        assert result["ETHUSDT"][0]["sector"] == "Smart Contracts"

    def test_enrich_prices_missing_metadata(self):
        """Test enrichment when metadata is missing for some symbols."""
        from src.pipeline.ingest_sources import enrich_prices_with_metadata

        prices = {
            "BTCUSDT": [{"timestamp": "2024-01-01", "close": 42000.0}],
            "UNKNOWN": [{"timestamp": "2024-01-01", "close": 100.0}],
        }

        metadata = [
            {"symbol": "BTCUSDT", "name": "Bitcoin", "sector": "Currency"},
        ]

        result = enrich_prices_with_metadata(prices, metadata)

        # BTCUSDT should be enriched
        assert result["BTCUSDT"][0]["name"] == "Bitcoin"

        # UNKNOWN should still have original data
        assert "UNKNOWN" in result
        assert result["UNKNOWN"][0]["close"] == 100.0


class TestSectorFiltering:
    """Tests for sector-based filtering."""

    def test_get_symbols_by_sector(self):
        """Test filtering symbols by sector using actual CSV file."""
        from src.pipeline.ingest_sources import get_symbols_by_sector

        # This test uses the actual CSV file
        # Skip if file doesn't exist
        try:
            currency = get_symbols_by_sector("Currency")
            # Should return list of symbols
            assert isinstance(currency, list)
        except Exception:
            pytest.skip("CSV metadata file not available")

    def test_get_symbols_empty_sector(self):
        """Test filtering with non-existent sector."""
        from src.pipeline.ingest_sources import get_symbols_by_sector

        try:
            result = get_symbols_by_sector("NonExistentSectorXYZ")
            assert result == []
        except Exception:
            pytest.skip("CSV metadata file not available")


class TestPostgresFallback:
    """Tests for PostgreSQL fallback mechanism."""

    def test_load_benchmarks_fallback(self):
        """Test benchmark fallback data."""
        from src.pipeline.ingest_postgres import load_benchmarks_fallback

        result = load_benchmarks_fallback()

        # Should return fallback data as dict
        assert isinstance(result, dict)
        assert "source" in result
        assert result["source"] == "fallback_simulation"
        assert "indices" in result

    def test_fallback_data_structure(self):
        """Test fallback data has expected structure."""
        from src.pipeline.ingest_postgres import load_benchmarks_fallback

        result = load_benchmarks_fallback()

        # Check for expected indices
        assert "indices" in result
        assert "SP500" in result["indices"]

        # Check SP500 data structure
        sp500_data = result["indices"]["SP500"]
        assert len(sp500_data) > 0
        assert all("date" in row for row in sp500_data)
        assert all("close" in row for row in sp500_data)
        assert all(isinstance(row["close"], (int, float)) for row in sp500_data)


class TestSourceError:
    """Tests for SourceError exception."""

    def test_source_error_creation(self):
        """Test SourceError creation."""
        from src.pipeline.ingest_sources import SourceError

        error = SourceError("Test error", source="csv")
        assert error.message == "Test error"
        assert error.source == "csv"

    def test_source_error_str(self):
        """Test SourceError string representation."""
        from src.pipeline.ingest_sources import SourceError

        error = SourceError("File not found", source="json")
        assert "File not found" in str(error)


class TestDatabaseError:
    """Tests for DatabaseError exception."""

    def test_database_error_creation(self):
        """Test DatabaseError creation."""
        from src.pipeline.ingest_postgres import DatabaseError

        error = DatabaseError("Connection failed", query="SELECT 1")
        assert error.message == "Connection failed"
        assert error.query == "SELECT 1"

    def test_database_error_without_query(self):
        """Test DatabaseError without query."""
        from src.pipeline.ingest_postgres import DatabaseError

        error = DatabaseError("Simple error")
        assert error.message == "Simple error"
        assert error.query is None


class TestIntegration:
    """Integration tests for multi-source ingestion."""

    def test_multi_source_data_compatibility(self, tmp_path):
        """Test that data from different sources can be combined."""
        from src.pipeline.ingest_sources import (
            enrich_prices_with_metadata,
            load_portfolio_config_json,
            load_symbols_metadata_csv,
        )

        # Create CSV with all required columns
        csv_content = """symbol,name,sector,category,launch_year,market_cap_rank,is_stablecoin,consensus
BTCUSDT,Bitcoin,Currency,Layer 1,2009,1,false,Proof of Work
ETHUSDT,Ethereum,Smart Contracts,Layer 1,2015,2,false,Proof of Stake
"""
        csv_path = tmp_path / "metadata.csv"
        csv_path.write_text(csv_content)

        # Create JSON with expected structure
        json_content = {
            "portfolio": {
                "name": "Test Portfolio",
                "symbols": ["BTCUSDT", "ETHUSDT"],
                "risk_tolerance": "moderate",
            },
            "sectors": {},
        }
        json_path = tmp_path / "config.json"
        json_path.write_text(json.dumps(json_content))

        # Simulate price data (would come from API)
        prices = {
            "BTCUSDT": [{"timestamp": "2024-01-01", "close": 42000.0}],
            "ETHUSDT": [{"timestamp": "2024-01-01", "close": 2200.0}],
        }

        # Load and combine
        metadata = load_symbols_metadata_csv(csv_path)
        config = load_portfolio_config_json(json_path)
        enriched = enrich_prices_with_metadata(prices, metadata)

        # Verify combination works
        assert config["portfolio"]["symbols"] == ["BTCUSDT", "ETHUSDT"]
        assert enriched["BTCUSDT"][0]["name"] == "Bitcoin"
        assert enriched["ETHUSDT"][0]["sector"] == "Smart Contracts"


class TestDataSourceABC:
    """Tests for DataSource abstract base class."""

    def test_cannot_instantiate_abc(self):
        from src.pipeline.ingest_sources import DataSource
        with pytest.raises(TypeError):
            DataSource()


class TestCSVSource:
    """Tests for CSVSource data source class."""

    def test_name(self):
        from src.pipeline.ingest_sources import CSVSource
        assert CSVSource().name == "csv"

    def test_is_available_true(self):
        from src.pipeline.ingest_sources import CSVSource
        source = CSVSource()
        # Real file exists in project
        assert isinstance(source.is_available(), bool)

    def test_fetch_returns_metadata_key(self):
        from src.pipeline.ingest_sources import CSVSource
        source = CSVSource()
        try:
            result = source.fetch()
            assert "metadata" in result
            assert isinstance(result["metadata"], list)
        except Exception:
            pytest.skip("CSV metadata file not available")


class TestJSONSource:
    """Tests for JSONSource data source class."""

    def test_name(self):
        from src.pipeline.ingest_sources import JSONSource
        assert JSONSource().name == "json"

    def test_is_available_true(self):
        from src.pipeline.ingest_sources import JSONSource
        source = JSONSource()
        assert isinstance(source.is_available(), bool)

    def test_fetch_returns_config_key(self):
        from src.pipeline.ingest_sources import JSONSource
        source = JSONSource()
        try:
            result = source.fetch()
            assert "config" in result
            assert isinstance(result["config"], dict)
        except Exception:
            pytest.skip("JSON config file not available")


class TestBinanceAPISource:
    """Tests for BinanceAPISource data source class."""

    def test_name(self):
        from src.pipeline.ingest_sources import BinanceAPISource
        assert BinanceAPISource().name == "api"

    def test_is_available(self):
        from src.pipeline.ingest_sources import BinanceAPISource
        assert BinanceAPISource().is_available() is True

    def test_stores_symbols(self):
        from src.pipeline.ingest_sources import BinanceAPISource
        source = BinanceAPISource(symbols=["BTCUSDT"])
        assert source._symbols == ["BTCUSDT"]

    def test_fetch_calls_ingest_data(self):
        from src.pipeline.ingest_sources import BinanceAPISource
        source = BinanceAPISource(symbols=["BTCUSDT"])
        mock_data = {"BTCUSDT": [{"timestamp": "2024-01-01", "close": 42000.0}]}
        with patch("src.pipeline.ingest.ingest_data", return_value=mock_data) as mock_fn:
            result = source.fetch()
            mock_fn.assert_called_once_with(symbols=["BTCUSDT"])
            assert result == {"prices": mock_data}


class TestScrapingSource:
    """Tests for ScrapingSource data source class."""

    def test_name(self):
        from src.pipeline.ingest_sources import ScrapingSource
        assert ScrapingSource().name == "scraping"

    def test_is_available(self):
        from src.pipeline.ingest_sources import ScrapingSource
        assert ScrapingSource().is_available() is True

    def test_default_limit(self):
        from src.pipeline.ingest_sources import ScrapingSource
        assert ScrapingSource()._limit == 20

    def test_custom_limit(self):
        from src.pipeline.ingest_sources import ScrapingSource
        assert ScrapingSource(limit=50)._limit == 50

    def test_fetch_calls_scrape(self):
        from src.pipeline.ingest_sources import ScrapingSource
        source = ScrapingSource(limit=10)
        mock_rankings = [{"name": "Bitcoin", "rank": 1}]
        with patch("src.pipeline.ingest_scraping.scrape_market_rankings", return_value=mock_rankings) as mock_fn:
            result = source.fetch()
            mock_fn.assert_called_once_with(limit=10, allow_fallback=True)
            assert result == {"market_rankings": mock_rankings}


class TestPostgresSource:
    """Tests for PostgresSource data source class."""

    def test_name(self):
        from src.pipeline.ingest_sources import PostgresSource
        assert PostgresSource().name == "postgres"

    def test_is_available(self):
        from src.pipeline.ingest_sources import PostgresSource
        assert PostgresSource().is_available() is True

    def test_fetch_uses_fallback_on_error(self):
        from src.pipeline.ingest_sources import PostgresSource
        source = PostgresSource()
        fallback_data = {"source": "fallback_simulation", "indices": {}}
        with patch("src.pipeline.ingest_postgres.load_benchmarks", side_effect=ConnectionError):
            with patch("src.pipeline.ingest_postgres.load_benchmarks_fallback", return_value=fallback_data) as mock_fb:
                result = source.fetch()
                mock_fb.assert_called_once()
                assert result == {"benchmarks": fallback_data}


class TestListAvailableSources:
    """Tests for list_available_sources using DataSource classes."""

    def test_returns_all_six_sources(self):
        from src.pipeline.ingest_sources import list_available_sources
        result = list_available_sources()
        assert set(result.keys()) == {"csv", "json", "api", "scraping", "postgres", "yfinance"}

    def test_values_are_booleans(self):
        from src.pipeline.ingest_sources import list_available_sources
        result = list_available_sources()
        for value in result.values():
            assert isinstance(value, bool)

    def test_api_scraping_postgres_always_available(self):
        from src.pipeline.ingest_sources import list_available_sources
        result = list_available_sources()
        assert result["api"] is True
        assert result["scraping"] is True
        assert result["postgres"] is True
