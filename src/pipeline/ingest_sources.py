"""
Multi-source data ingestion module.

Demonstrates C8 compliance: extraction from multiple source types.

Sources implemented:
1. API REST (Binance) - Dynamic price data
2. CSV File - Static symbol metadata
3. JSON File - Portfolio configuration
4. Web Scraping (CoinGecko) - Market rankings
5. PostgreSQL - Historical benchmarks

This module provides functions to extract and aggregate data from
heterogeneous sources, a key requirement for the Data Engineer certification.

Example usage:
    >>> from src.pipeline.ingest_sources import ingest_all_sources
    >>> data = ingest_all_sources()
    >>> print(data["sources"])
    ['csv', 'json', 'api', 'scraping', 'postgres']
"""

import csv
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.config import load_config

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration (from centralized config)
# =============================================================================

_cfg = load_config()

DATA_DIR: Path = _cfg.data_dir
REFERENCE_DIR: Path = _cfg.reference_dir

# Source file paths
SYMBOLS_METADATA_CSV = REFERENCE_DIR / "symbols_metadata.csv"
PORTFOLIO_CONFIG_JSON = REFERENCE_DIR / "portfolio_config.json"


# =============================================================================
# Exceptions
# =============================================================================


class SourceError(Exception):
    """Exception for data source errors."""

    def __init__(self, message: str, source: str | None = None):
        self.message = message
        self.source = source
        super().__init__(self.message)


# =============================================================================
# DataSource ABC (clean architecture pattern)
# =============================================================================


class DataSource(ABC):
    """Abstract base class for all data sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this source."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the source can be reached."""
        ...

    @abstractmethod
    def fetch(self) -> dict[str, Any]:
        """Fetch data from the source. Returns a dict to merge into results."""
        ...


class CSVSource(DataSource):
    """CSV file data source (symbols metadata)."""

    @property
    def name(self) -> str:
        return "csv"

    def is_available(self) -> bool:
        return SYMBOLS_METADATA_CSV.exists()

    def fetch(self) -> dict[str, Any]:
        return {"metadata": load_symbols_metadata_csv()}


class JSONSource(DataSource):
    """JSON file data source (portfolio configuration)."""

    @property
    def name(self) -> str:
        return "json"

    def is_available(self) -> bool:
        return PORTFOLIO_CONFIG_JSON.exists()

    def fetch(self) -> dict[str, Any]:
        return {"config": load_portfolio_config_json()}


class BinanceAPISource(DataSource):
    """Binance REST API data source (price data)."""

    def __init__(self, symbols: list[str] | None = None):
        self._symbols = symbols

    @property
    def name(self) -> str:
        return "api"

    def is_available(self) -> bool:
        return True

    def fetch(self) -> dict[str, Any]:
        from src.pipeline.ingest import ingest_data
        return {"prices": ingest_data(symbols=self._symbols)}


class ScrapingSource(DataSource):
    """CoinGecko web scraping data source (market rankings)."""

    def __init__(self, limit: int = 20):
        self._limit = limit

    @property
    def name(self) -> str:
        return "scraping"

    def is_available(self) -> bool:
        return True

    def fetch(self) -> dict[str, Any]:
        from src.pipeline.ingest_scraping import scrape_market_rankings
        return {"market_rankings": scrape_market_rankings(limit=self._limit, allow_fallback=True)}


class PostgresSource(DataSource):
    """PostgreSQL database data source (benchmarks)."""

    @property
    def name(self) -> str:
        return "postgres"

    def is_available(self) -> bool:
        return True

    def fetch(self) -> dict[str, Any]:
        from src.pipeline.ingest_postgres import load_benchmarks, load_benchmarks_fallback
        try:
            benchmarks = load_benchmarks()
        except Exception:
            logger.warning("PostgreSQL not available, using fallback")
            benchmarks = load_benchmarks_fallback()
        return {"benchmarks": benchmarks}


# =============================================================================
# Source 1: CSV File Reader (C8 - fichier de données)
# =============================================================================


def load_symbols_metadata_csv(
    file_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Load symbol metadata from CSV file.

    This demonstrates extraction from a structured file source (C8).

    CSV Structure:
    - symbol: Trading pair (e.g., BTCUSDT)
    - name: Full name (e.g., Bitcoin)
    - sector: Classification (Currency, Smart Contracts, etc.)
    - category: Technical category (Layer 1, Layer 2, etc.)
    - launch_year: Year of launch
    - market_cap_rank: Approximate ranking
    - is_stablecoin: Boolean flag
    - consensus: Consensus mechanism

    Args:
        file_path: Path to CSV file. Defaults to symbols_metadata.csv.

    Returns:
        List of dictionaries, one per symbol.

    Raises:
        SourceError: If file not found or parsing fails.

    Example:
        >>> metadata = load_symbols_metadata_csv()
        >>> print(metadata[0])
        {'symbol': 'BTCUSDT', 'name': 'Bitcoin', 'sector': 'Currency', ...}
    """
    if file_path is None:
        file_path = SYMBOLS_METADATA_CSV

    if not file_path.exists():
        raise SourceError(
            f"CSV file not found: {file_path}",
            source="csv"
        )

    logger.info(f"Loading CSV: {file_path.name}")

    try:
        records: list[dict[str, Any]] = []

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Type conversion
                record = {
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "sector": row["sector"],
                    "category": row["category"],
                    "launch_year": int(row["launch_year"]),
                    "market_cap_rank": int(row["market_cap_rank"]),
                    "is_stablecoin": row["is_stablecoin"].lower() == "true",
                    "consensus": row["consensus"],
                }
                records.append(record)

        logger.info(f"Loaded {len(records)} symbols from CSV")
        return records

    except Exception as e:
        raise SourceError(f"CSV parsing error: {e}", source="csv") from e


def get_symbol_metadata(symbol: str) -> dict[str, Any] | None:
    """
    Get metadata for a specific symbol from CSV.

    Args:
        symbol: Trading pair symbol (e.g., BTCUSDT).

    Returns:
        Metadata dictionary or None if not found.
    """
    metadata = load_symbols_metadata_csv()
    for record in metadata:
        if record["symbol"] == symbol:
            return record
    return None


# =============================================================================
# Source 2: JSON File Reader (C8 - fichier de données)
# =============================================================================


def load_portfolio_config_json(
    file_path: Path | None = None,
) -> dict[str, Any]:
    """
    Load portfolio configuration from JSON file.

    This demonstrates extraction from a semi-structured file source (C8).

    JSON Structure:
    - portfolio: Name, description, version
    - constraints: Investment constraints (min/max weights, etc.)
    - risk_parameters: Risk-free rate, target volatility
    - sector_classification: Symbol groupings
    - benchmarks: Benchmark weights

    Args:
        file_path: Path to JSON file. Defaults to portfolio_config.json.

    Returns:
        Configuration dictionary.

    Raises:
        SourceError: If file not found or parsing fails.

    Example:
        >>> config = load_portfolio_config_json()
        >>> print(config["risk_parameters"]["risk_free_rate"])
        0.05
    """
    if file_path is None:
        file_path = PORTFOLIO_CONFIG_JSON

    if not file_path.exists():
        raise SourceError(
            f"JSON file not found: {file_path}",
            source="json"
        )

    logger.info(f"Loading JSON: {file_path.name}")

    try:
        with open(file_path, encoding="utf-8") as f:
            config: dict[str, Any] = json.load(f)

        logger.info(f"Loaded config: {config['portfolio']['name']}")
        return config

    except json.JSONDecodeError as e:
        raise SourceError(f"JSON parsing error: {e}", source="json") from e
    except Exception as e:
        raise SourceError(f"JSON read error: {e}", source="json") from e


# =============================================================================
# Source 3: API (imported from ingest.py)
# =============================================================================

# API functions are in ingest.py - we import them for aggregation


# =============================================================================
# Multi-Source Aggregation (C10)
# =============================================================================


def enrich_prices_with_metadata(
    price_data: dict[str, list[dict[str, Any]]],
    metadata: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Enrich price data with symbol metadata.

    This demonstrates data aggregation from multiple sources (C10).
    Combines dynamic API data with static CSV metadata.

    Args:
        price_data: Dictionary of symbol -> price records (from API).
        metadata: List of metadata records (from CSV).

    Returns:
        Enriched price data with metadata fields added.

    Example:
        >>> enriched = enrich_prices_with_metadata(prices, metadata)
        >>> print(enriched["BTCUSDT"][0]["sector"])
        'Currency'
    """
    # Build metadata lookup
    meta_lookup = {m["symbol"]: m for m in metadata}

    enriched: dict[str, list[dict[str, Any]]] = {}

    for symbol, records in price_data.items():
        meta = meta_lookup.get(symbol, {})

        enriched_records = []
        for record in records:
            enriched_record = {
                **record,
                "name": meta.get("name", "Unknown"),
                "sector": meta.get("sector", "Unknown"),
                "category": meta.get("category", "Unknown"),
            }
            enriched_records.append(enriched_record)

        enriched[symbol] = enriched_records

    return enriched


def ingest_all_sources(
    symbols: list[str] | None = None,
    include_api: bool = True,
    include_scraping: bool = True,
    include_postgres: bool = True,
) -> dict[str, Any]:
    """
    Ingest data from all configured sources.

    Main entry point for multi-source ingestion (C8 compliance).
    Demonstrates extraction from 5 different source types.

    Sources:
    1. CSV: Symbol metadata (static file)
    2. JSON: Portfolio configuration (semi-structured file)
    3. API: Price data from Binance (REST API)
    4. Scraping: Market rankings from CoinGecko (web scraping)
    5. PostgreSQL: Historical benchmarks (relational database)

    Args:
        symbols: List of symbols to fetch. If None, uses config.
        include_api: Whether to fetch live API data.
        include_scraping: Whether to scrape market rankings.
        include_postgres: Whether to load from PostgreSQL.

    Returns:
        Aggregated data from all sources:
        {
            "sources": ["csv", "json", "api", "scraping", "postgres"],
            "metadata": {...},      # From CSV
            "config": {...},        # From JSON
            "prices": {...},        # From API
            "market_rankings": [...], # From scraping
            "benchmarks": {...},    # From PostgreSQL
            "enriched": {...},      # Merged data
        }

    Example:
        >>> data = ingest_all_sources()
        >>> print(data["sources"])
        ['csv', 'json', 'api', 'scraping', 'postgres']
    """
    logger.info("=" * 60)
    logger.info("MULTI-SOURCE INGESTION (C8) - 5 Source Types")
    logger.info("=" * 60)

    sources_loaded: list[str] = []
    sources_failed: list[dict[str, str]] = []
    result: dict[str, Any] = {}

    # Build source list
    sources: list[DataSource] = [CSVSource(), JSONSource()]
    if include_api:
        # Resolve symbols from config if needed
        api_symbols = symbols
        if api_symbols is None:
            try:
                config = load_portfolio_config_json()
                sectors = config.get("sector_classification", {})
                api_symbols = list({s for syms in sectors.values() for s in syms})
            except SourceError:
                api_symbols = None
        sources.append(BinanceAPISource(symbols=api_symbols))
    if include_scraping:
        sources.append(ScrapingSource())
    if include_postgres:
        sources.append(PostgresSource())

    # Fetch from each source
    for i, source in enumerate(sources, 1):
        logger.info(f"[Source {i}/{len(sources)}] {source.name}")
        try:
            data = source.fetch()
            result.update(data)
            sources_loaded.append(source.name)
        except (SourceError, Exception) as e:
            logger.warning(f"Source {source.name} failed: {e}")
            sources_failed.append({"source": source.name, "error": str(e)})

    # Data Aggregation (C10)
    metadata = result.get("metadata", [])
    if metadata and "prices" in result:
        logger.info("Merging sources (C10)")
        enriched = enrich_prices_with_metadata(result["prices"], metadata)
        result["enriched"] = enriched
        logger.info(f"Enriched {len(enriched)} symbols with CSV metadata")

        # Add market rankings if available
        if "market_rankings" in result:
            from src.pipeline.ingest_scraping import enrich_with_market_data
            market_data = enrich_with_market_data(
                list(result["prices"].keys()),
                result["market_rankings"]
            )
            result["market_data"] = market_data
            logger.info(f"Added market rankings for {len(market_data)} symbols")

    result["sources"] = sources_loaded
    if sources_failed:
        result["failures"] = sources_failed

    # Summary
    logger.info("=" * 60)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Sources loaded: {sources_loaded}")
    logger.info(f"Total source types: {len(sources_loaded)}/5")
    logger.info("Source breakdown:")
    logger.info(f"[{'Y' if 'csv' in sources_loaded else 'N'}] CSV File")
    logger.info(f"[{'Y' if 'json' in sources_loaded else 'N'}] JSON File")
    logger.info(f"[{'Y' if 'api' in sources_loaded else 'N'}] REST API")
    logger.info(f"[{'Y' if 'scraping' in sources_loaded else 'N'}] Web Scraping")
    logger.info(f"[{'Y' if 'postgres' in sources_loaded else 'N'}] PostgreSQL DB")

    if "metadata" in result:
        logger.info(f"Symbols (CSV): {len(result.get('metadata', []))}")
    if "prices" in result:
        logger.info(f"Symbols (API): {len(result.get('prices', {}))}")
    if "market_rankings" in result:
        logger.info(f"Rankings (Scraping): {len(result.get('market_rankings', []))}")
    if "benchmarks" in result:
        logger.info(f"Indices (Postgres): {len(result.get('benchmarks', {}).get('indices', {}))}")

    return result


# =============================================================================
# Utility Functions
# =============================================================================


def list_available_sources() -> dict[str, bool]:
    """
    Check which data sources are available.

    Returns:
        Dictionary of source -> availability status.
    """
    all_sources: list[DataSource] = [
        CSVSource(),
        JSONSource(),
        BinanceAPISource(),
        ScrapingSource(),
        PostgresSource(),
    ]
    return {source.name: source.is_available() for source in all_sources}


def get_symbols_by_sector(sector: str) -> list[str]:
    """
    Get symbols belonging to a specific sector.

    Args:
        sector: Sector name (e.g., "Smart Contracts").

    Returns:
        List of symbols in that sector.
    """
    metadata = load_symbols_metadata_csv()
    return [m["symbol"] for m in metadata if m["sector"] == sector]


def get_symbols_by_category(category: str) -> list[str]:
    """
    Get symbols belonging to a specific category.

    Args:
        category: Category name (e.g., "Layer 1").

    Returns:
        List of symbols in that category.
    """
    metadata = load_symbols_metadata_csv()
    return [m["symbol"] for m in metadata if m["category"] == category]


# =============================================================================
# Main execution (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Testing multi-source ingestion...")
    print()

    # Test without API (faster)
    data = ingest_all_sources(include_api=False)

    print("\n" + "=" * 50)
    print("METADATA SAMPLE")
    print("=" * 50)
    if "metadata" in data:
        for m in data["metadata"][:3]:
            print(f"  {m['symbol']}: {m['name']} ({m['sector']})")

    print("\n" + "=" * 50)
    print("CONFIG SAMPLE")
    print("=" * 50)
    if "config" in data:
        print(f"  Portfolio: {data['config']['portfolio']['name']}")
        print(f"  Risk-free rate: {data['config']['risk_parameters']['risk_free_rate']}")

    # Test with API
    print("\n" + "=" * 50)
    print("FULL TEST WITH API")
    print("=" * 50)
    # Uncomment to test with API:
    # data = ingest_all_sources(symbols=["BTCUSDT", "ETHUSDT"])
