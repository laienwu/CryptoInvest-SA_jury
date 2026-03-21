"""
Storage package for the portfolio optimization project.

This package provides a pluggable storage abstraction layer that allows
switching between different storage backends without changing pipeline code.

Usage:
    >>> from src.storage import get_storage
    >>> storage = get_storage("parquet")  # Default
    >>> storage.save_raw(data)
    >>> loaded = storage.load_raw()

Available backends:
- parquet: File-based storage using Apache Parquet (default)
- duckdb: SQL on files using DuckDB (star schema warehouse)
- minio: S3-compatible object storage via MinIO

Factory function:
    get_storage(name) -> Returns the appropriate Storage implementation

Example workflow:
    >>> from src.storage import get_storage
    >>> from src.pipeline.ingest import ingest_data
    >>>
    >>> # Ingest data from Binance
    >>> data = ingest_data()
    >>>
    >>> # Save to storage
    >>> storage = get_storage()  # Uses default "parquet"
    >>> storage.save_raw(data)
    >>>
    >>> # Load back later
    >>> loaded = storage.load_raw(["BTCUSDT", "ETHUSDT"])
"""

from types import MappingProxyType
from typing import Any

from .base import Storage, StorageError
from .duckdb import DuckDBStorage
from .parquet import ParquetStorage

# MinIO is an optional dependency — only register if installed
try:
    from .minio import MinIOStorage

    _has_minio = True
except ImportError:
    _has_minio = False

# Type alias for storage names
StorageName = str

# Registry of available storage implementations.
# _mutable_registry is the private, writable store; _STORAGE_REGISTRY is the
# read-only proxy exposed to the rest of the codebase.  Mutations go through
# register_storage() only.
_mutable_registry: dict[str, type[Storage]] = {
    "parquet": ParquetStorage,
    "duckdb": DuckDBStorage,
}
if _has_minio:
    _mutable_registry["minio"] = MinIOStorage
_STORAGE_REGISTRY: MappingProxyType[str, type[Storage]] = MappingProxyType(_mutable_registry)

# Default storage backend
DEFAULT_STORAGE = "parquet"


def get_storage(name: str | None = None, **kwargs: Any) -> Storage:
    """
    Factory function to get a storage implementation.

    This is the primary entry point for obtaining a storage instance.
    It implements the pluggable abstraction pattern, allowing different
    storage backends to be used interchangeably.

    Args:
        name: Name of the storage backend to use. Options:
              - "parquet" (default): File-based Parquet storage
              - "duckdb": SQL on files (star schema warehouse)
              - "minio": S3-compatible object storage
        **kwargs: Additional arguments passed to the storage constructor.
                  For ParquetStorage: data_dir (str | Path) - custom data directory

    Returns:
        A Storage implementation instance.

    Raises:
        ValueError: If the requested storage backend is not available.

    Examples:
        >>> # Get default storage
        >>> storage = get_storage()

        >>> # Explicitly request Parquet
        >>> storage = get_storage("parquet")

        >>> # Custom data directory
        >>> storage = get_storage("parquet", data_dir="/path/to/data")
    """
    storage_name = name or DEFAULT_STORAGE

    if storage_name not in _STORAGE_REGISTRY:
        available = ", ".join(_STORAGE_REGISTRY.keys())
        raise ValueError(
            f"Unknown storage backend: '{storage_name}'. "
            f"Available backends: {available}"
        )

    storage_class = _STORAGE_REGISTRY[storage_name]
    return storage_class(**kwargs)


def register_storage(name: str, storage_class: type[Storage]) -> None:
    """
    Register a new storage backend.

    This allows extending the storage system with custom implementations
    without modifying the core package.

    Args:
        name: Name to register the storage under.
        storage_class: Storage implementation class (must inherit from Storage).

    Raises:
        TypeError: If storage_class doesn't inherit from Storage.

    Example:
        >>> from src.storage import register_storage, Storage
        >>> class MyStorage(Storage):
        ...     # implementation
        >>> register_storage("my_backend", MyStorage)
        >>> storage = get_storage("my_backend")
    """
    global _STORAGE_REGISTRY
    if not issubclass(storage_class, Storage):
        raise TypeError(
            f"{storage_class.__name__} must inherit from Storage"
        )
    _mutable_registry[name] = storage_class
    _STORAGE_REGISTRY = MappingProxyType(_mutable_registry)


def list_available_backends() -> list[str]:
    """
    List all available storage backends.

    Returns:
        List of storage backend names that can be passed to get_storage().
    """
    return list(_STORAGE_REGISTRY.keys())


# Exports
__all__ = [
    # Factory function
    "get_storage",
    # Base classes
    "Storage",
    "StorageError",
    # Implementations
    "ParquetStorage",
    "DuckDBStorage",
    # Utilities
    "register_storage",
    "list_available_backends",
]
if _has_minio:
    __all__.append("MinIOStorage")
