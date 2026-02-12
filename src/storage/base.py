"""
Abstract storage interface for the portfolio optimization project.

This module defines the Storage abstract base class that all storage
implementations must inherit from. It provides a pluggable abstraction
layer allowing easy switching between storage backends (Parquet, DuckDB,
PostgreSQL, etc.).

The interface supports:
- Raw data storage (OHLCV klines from Binance)
- Processed data storage (returns, volatility, correlation matrices)
- Output data storage (optimization results, portfolio weights)

Example usage:
    >>> from src.storage import get_storage
    >>> storage = get_storage("parquet")  # Get Parquet implementation
    >>> storage.save_raw(data)
    >>> loaded = storage.load_raw()
"""

from abc import ABC, abstractmethod
from typing import Any


class StorageError(Exception):
    """Custom exception for storage operations."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


class Storage(ABC):
    """
    Abstract storage interface.

    All storage implementations must inherit from this class and implement
    the abstract methods for saving and loading raw/processed data.

    This abstraction allows the pipeline to work with different storage
    backends without code changes - just swap the implementation.

    Implementations:
    - ParquetStorage: File-based storage using Apache Parquet format
    - (Future) DuckDBStorage: SQL on files using DuckDB
    - (Future) PostgresStorage: Full RDBMS for production
    """

    @abstractmethod
    def save_raw(
        self, data: dict[str, list[dict[str, Any]]], metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Save raw ingested data (OHLCV klines).

        Args:
            data: Dictionary mapping symbol to list of OHLCV records.
                  Format: {"BTCUSDT": [{"timestamp": "2024-01-01", "open": ..., ...}, ...]}
            metadata: Optional metadata to store with the data (e.g., ingestion timestamp).

        Returns:
            Path or identifier of the saved data.

        Raises:
            StorageError: If save operation fails.
        """
        pass

    @abstractmethod
    def load_raw(
        self, symbols: list[str] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Load raw data, optionally filtered by symbols.

        Args:
            symbols: List of symbols to load. If None, loads all available symbols.

        Returns:
            Dictionary mapping symbol to list of OHLCV records.

        Raises:
            StorageError: If load operation fails or data not found.
        """
        pass

    @abstractmethod
    def save_processed(self, data: dict[str, Any], name: str) -> str:
        """
        Save processed data (metrics, correlation matrices, etc.).

        Args:
            data: Dictionary containing processed data to save.
                  Structure depends on the type of processed data.
            name: Identifier for the processed data (e.g., "returns", "correlation").

        Returns:
            Path or identifier of the saved data.

        Raises:
            StorageError: If save operation fails.
        """
        pass

    @abstractmethod
    def load_processed(self, name: str) -> dict[str, Any]:
        """
        Load processed data by name.

        Args:
            name: Identifier of the processed data to load.

        Returns:
            Dictionary containing the processed data.

        Raises:
            StorageError: If load operation fails or data not found.
        """
        pass

    @abstractmethod
    def save_output(self, data: dict[str, Any], name: str) -> str:
        """
        Save output/results data (portfolio weights, optimization results).

        Args:
            data: Dictionary containing output data to save.
            name: Identifier for the output (e.g., "weights", "optimal_portfolio").

        Returns:
            Path or identifier of the saved data.

        Raises:
            StorageError: If save operation fails.
        """
        pass

    @abstractmethod
    def load_output(self, name: str) -> dict[str, Any]:
        """
        Load output data by name.

        Args:
            name: Identifier of the output data to load.

        Returns:
            Dictionary containing the output data.

        Raises:
            StorageError: If load operation fails or data not found.
        """
        pass

    @abstractmethod
    def list_raw_symbols(self) -> list[str]:
        """
        List all available symbols in raw data storage.

        Returns:
            List of symbol names that have stored raw data.
        """
        pass

    @abstractmethod
    def list_processed(self) -> list[str]:
        """
        List all available processed data names.

        Returns:
            List of processed data identifiers.
        """
        pass

    @abstractmethod
    def list_outputs(self) -> list[str]:
        """
        List all available output data names.

        Returns:
            List of output data identifiers.
        """
        pass
