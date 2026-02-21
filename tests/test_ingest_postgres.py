"""
Tests for src/pipeline/ingest_postgres.py

Covers: DatabaseError, BenchmarkRepository (context manager, DI, test_connection,
load_benchmarks), and load_benchmarks_fallback.
All psycopg2 calls are mocked — no real database needed.
"""

from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.config import DatabaseConfig
from src.pipeline.ingest_postgres import (
    BenchmarkRepository,
    DatabaseError,
    load_benchmarks_fallback,
)


# =============================================================================
# DatabaseError
# =============================================================================


def test_database_error_message_and_query() -> None:
    err = DatabaseError("query failed", query="SELECT * FROM foo")
    assert err.message == "query failed"
    assert err.query == "SELECT * FROM foo"
    assert str(err) == "query failed"


def test_database_error_no_query() -> None:
    err = DatabaseError("connection refused")
    assert err.query is None


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_config() -> DatabaseConfig:
    return DatabaseConfig(
        host="localhost", port=5432,
        database="test_db", user="test", password="test",
    )


def _make_mock_conn() -> MagicMock:
    """Build a mock psycopg2 connection.

    load_benchmarks executes 3 queries in sequence on the same cursor.
    We set fetchall to return [] for all — empty but valid.
    """
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None

    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    return conn


# =============================================================================
# BenchmarkRepository — dependency injection
# =============================================================================


def test_repository_accepts_injected_config(test_config: DatabaseConfig) -> None:
    repo = BenchmarkRepository(test_config)
    assert repo._config == test_config


def test_repository_uses_load_db_config_when_no_config() -> None:
    with patch("src.pipeline.ingest_postgres.load_db_config") as mock_load:
        mock_load.return_value = DatabaseConfig()
        repo = BenchmarkRepository()
    mock_load.assert_called_once()
    assert repo._config is not None


# =============================================================================
# BenchmarkRepository — context manager
# =============================================================================


def test_context_manager_commits_on_success(test_config: DatabaseConfig) -> None:
    mock_conn = _make_mock_conn()

    with patch("src.pipeline.ingest_postgres.BenchmarkRepository._open_connection",
               return_value=mock_conn):
        with BenchmarkRepository(test_config):
            pass

    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()


def test_context_manager_rolls_back_on_exception(test_config: DatabaseConfig) -> None:
    mock_conn = _make_mock_conn()

    with patch("src.pipeline.ingest_postgres.BenchmarkRepository._open_connection",
               return_value=mock_conn):
        with pytest.raises(ValueError):
            with BenchmarkRepository(test_config):
                raise ValueError("deliberate")

    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()


# =============================================================================
# BenchmarkRepository — test_connection
# =============================================================================


def test_test_connection_returns_true_on_success(test_config: DatabaseConfig) -> None:
    mock_conn = _make_mock_conn()

    with patch("src.pipeline.ingest_postgres.BenchmarkRepository._open_connection",
               return_value=mock_conn):
        repo = BenchmarkRepository(test_config)
        assert repo.test_connection() is True


def test_test_connection_returns_false_on_failure(test_config: DatabaseConfig) -> None:
    with patch("src.pipeline.ingest_postgres.BenchmarkRepository._open_connection",
               side_effect=DatabaseError("refused")):
        repo = BenchmarkRepository(test_config)
        assert repo.test_connection() is False


# =============================================================================
# BenchmarkRepository — psycopg2 import error
# =============================================================================


def test_open_connection_raises_if_psycopg2_missing(test_config: DatabaseConfig) -> None:
    with patch.dict("sys.modules", {"psycopg2": None}):
        repo = BenchmarkRepository(test_config)
        with pytest.raises(DatabaseError, match="psycopg2 required"):
            repo._open_connection()


# =============================================================================
# BenchmarkRepository — load_benchmarks returns dict
# =============================================================================


def test_load_benchmarks_returns_dict(test_config: DatabaseConfig) -> None:
    """load_benchmarks returns a dict with indices, portfolio_history, comparisons."""
    mock_conn = _make_mock_conn()

    with patch("src.pipeline.ingest_postgres.BenchmarkRepository._open_connection",
               return_value=mock_conn):
        repo = BenchmarkRepository(test_config)
        result = repo.load_benchmarks()

    assert isinstance(result, dict)
    assert "indices" in result
    assert "portfolio_history" in result
    assert "comparisons" in result


def test_load_benchmarks_empty_db_returns_empty_collections(
    test_config: DatabaseConfig,
) -> None:
    mock_conn = _make_mock_conn()

    with patch("src.pipeline.ingest_postgres.BenchmarkRepository._open_connection",
               return_value=mock_conn):
        repo = BenchmarkRepository(test_config)
        result = repo.load_benchmarks()

    assert result["indices"] == {}
    assert result["portfolio_history"] == []
    assert result["comparisons"] == []


# =============================================================================
# load_benchmarks_fallback — returns dict with same structure
# =============================================================================


def test_load_benchmarks_fallback_returns_dict() -> None:
    result = load_benchmarks_fallback()
    assert isinstance(result, dict)


def test_load_benchmarks_fallback_has_required_keys() -> None:
    result = load_benchmarks_fallback()
    assert "indices" in result
    assert "source" in result


def test_load_benchmarks_fallback_no_db_needed() -> None:
    """Fallback must work with zero DB connectivity."""
    with patch("src.pipeline.ingest_postgres.BenchmarkRepository._open_connection",
               side_effect=DatabaseError("no db")):
        result = load_benchmarks_fallback()
    assert isinstance(result, dict)
    assert "source" in result
