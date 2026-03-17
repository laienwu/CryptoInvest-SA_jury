"""
Tests for the Redis cache layer (src/api/cache.py).

All tests use mocks — no real Redis instance required.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.api.cache import RedisCache, _CACHE_TTL_SECONDS, cached_response, get_cache


# ---------------------------------------------------------------------------
# RedisCache unit tests
# ---------------------------------------------------------------------------


class TestRedisCacheGet:
    """Tests for RedisCache.get()."""

    def test_cache_hit(self):
        """get() returns deserialized data when key exists."""
        client = MagicMock()
        payload = {"weights": {"BTCUSDT": 0.6}}
        client.get.return_value = json.dumps(payload).encode()

        cache = RedisCache(client)
        result = cache.get("portfolio:weights")

        assert result == payload
        client.get.assert_called_once_with("portfolio:weights")

    def test_cache_miss(self):
        """get() returns None when key does not exist."""
        client = MagicMock()
        client.get.return_value = None

        cache = RedisCache(client)
        assert cache.get("portfolio:missing") is None

    def test_cache_get_error(self):
        """get() returns None and logs warning on Redis error."""
        client = MagicMock()
        client.get.side_effect = ConnectionError("Redis down")

        cache = RedisCache(client)
        assert cache.get("portfolio:weights") is None


class TestRedisCacheSet:
    """Tests for RedisCache.set()."""

    def test_set_stores_json(self):
        """set() serializes data and stores with TTL."""
        client = MagicMock()
        cache = RedisCache(client)
        data = {"name": "returns", "data": [0.01, 0.02]}

        cache.set("portfolio:metrics:returns", data, ttl=60)

        client.set.assert_called_once_with(
            "portfolio:metrics:returns",
            json.dumps(data),
            ex=60,
        )

    def test_set_default_ttl(self):
        """set() uses default TTL when not specified."""
        client = MagicMock()
        cache = RedisCache(client)

        cache.set("k", {"a": 1})

        _, kwargs = client.set.call_args
        assert kwargs["ex"] == _CACHE_TTL_SECONDS

    def test_set_error_does_not_raise(self):
        """set() swallows Redis errors (logs warning, does not crash)."""
        client = MagicMock()
        client.set.side_effect = ConnectionError("Redis down")

        cache = RedisCache(client)
        # Should not raise
        cache.set("k", {"a": 1})


class TestRedisCacheInvalidate:
    """Tests for RedisCache.invalidate()."""

    def test_invalidate_deletes_matching_keys(self):
        """invalidate() deletes all keys matching the glob pattern."""
        client = MagicMock()
        client.keys.return_value = [b"portfolio:weights", b"portfolio:frontier"]

        cache = RedisCache(client)
        cache.invalidate("portfolio:*")

        client.keys.assert_called_once_with("portfolio:*")
        client.delete.assert_called_once_with(b"portfolio:weights", b"portfolio:frontier")

    def test_invalidate_no_matching_keys(self):
        """invalidate() does nothing when no keys match."""
        client = MagicMock()
        client.keys.return_value = []

        cache = RedisCache(client)
        cache.invalidate("portfolio:*")

        client.delete.assert_not_called()

    def test_invalidate_error_does_not_raise(self):
        """invalidate() swallows Redis errors."""
        client = MagicMock()
        client.keys.side_effect = ConnectionError("Redis down")

        cache = RedisCache(client)
        cache.invalidate("portfolio:*")


# ---------------------------------------------------------------------------
# cached_response helper tests
# ---------------------------------------------------------------------------


class TestCachedResponse:
    """Tests for the cached_response() helper."""

    def test_cache_hit_skips_fetch(self):
        """When cache has data, fetch_fn is never called."""
        client = MagicMock()
        cached_data = {"weights": {"BTCUSDT": 0.6}}
        client.get.return_value = json.dumps(cached_data).encode()
        cache = RedisCache(client)

        fetch_fn = MagicMock()
        result = cached_response(cache, "portfolio:weights", 300, fetch_fn)

        assert result == cached_data
        fetch_fn.assert_not_called()

    def test_cache_miss_calls_fetch_and_stores(self):
        """When cache misses, fetch_fn is called and result is cached."""
        client = MagicMock()
        client.get.return_value = None
        cache = RedisCache(client)

        fresh_data = {"name": "returns", "data": [0.01]}
        fetch_fn = MagicMock(return_value=fresh_data)

        result = cached_response(cache, "portfolio:metrics:returns", 300, fetch_fn)

        assert result == fresh_data
        fetch_fn.assert_called_once()
        client.set.assert_called_once_with(
            "portfolio:metrics:returns",
            json.dumps(fresh_data),
            ex=300,
        )

    def test_no_cache_calls_fetch_directly(self):
        """When cache is None, fetch_fn is called without caching."""
        fresh_data = {"weights": {"BTCUSDT": 0.6}}
        fetch_fn = MagicMock(return_value=fresh_data)

        result = cached_response(None, "portfolio:weights", 300, fetch_fn)

        assert result == fresh_data
        fetch_fn.assert_called_once()

    def test_fetch_fn_exception_propagates(self):
        """Exceptions from fetch_fn are not swallowed."""
        client = MagicMock()
        client.get.return_value = None
        cache = RedisCache(client)

        fetch_fn = MagicMock(side_effect=FileNotFoundError("not found"))

        with pytest.raises(FileNotFoundError):
            cached_response(cache, "k", 300, fetch_fn)


# ---------------------------------------------------------------------------
# get_cache() dependency tests
# ---------------------------------------------------------------------------


class TestGetCache:
    """Tests for the get_cache() FastAPI dependency."""

    def test_returns_none_when_no_redis_url(self):
        """get_cache() returns None when REDIS_URL is not set."""
        with patch.dict("os.environ", {}, clear=True):
            assert get_cache() is None

    def test_returns_none_when_redis_url_empty(self):
        """get_cache() returns None when REDIS_URL is empty string."""
        with patch.dict("os.environ", {"REDIS_URL": ""}):
            assert get_cache() is None

    def test_returns_cache_when_redis_available(self):
        """get_cache() returns RedisCache when Redis is reachable."""
        mock_client = MagicMock()
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url.return_value = mock_client

        with (
            patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}),
            patch.dict("sys.modules", {"redis": mock_redis_mod}),
        ):
            result = get_cache()

        assert isinstance(result, RedisCache)
        mock_client.ping.assert_called_once()

    def test_returns_none_when_redis_unreachable(self):
        """get_cache() returns None when Redis ping fails."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = ConnectionError("refused")
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url.return_value = mock_client

        with (
            patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}),
            patch.dict("sys.modules", {"redis": mock_redis_mod}),
        ):
            result = get_cache()

        assert result is None
