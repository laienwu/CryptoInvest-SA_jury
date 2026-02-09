"""
Source package for portfolio optimization project.

This package contains modules for data ingestion, storage, transformation, and optimization.

Subpackages:
- pipeline: Data operations (ingest, transform, optimize)
- storage: Pluggable storage abstraction (parquet, duckdb, postgres)
"""

from .storage import Storage, StorageError, get_storage

__all__ = ["get_storage", "Storage", "StorageError"]
