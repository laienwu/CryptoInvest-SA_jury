"""
Redis cache layer for the Portfolio Optimization API.

Provides optional caching with graceful fallback: when Redis is unavailable,
the API continues to work normally without caching. Cache is controlled by
the REDIS_URL environment variable.
"""

import json
import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300  # 5 minutes


class RedisCache:
    """Thin wrapper around a Redis client for JSON response caching."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, key: str) -> dict[str, Any] | None:
        """Return cached JSON for *key*, or None on miss / error."""
        try:
            raw: bytes | None = self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)  # type: ignore[no-any-return]
        except Exception:
            logger.warning("Redis GET failed for key=%s", key, exc_info=True)
            return None

    def set(self, key: str, data: dict[str, Any], ttl: int = _CACHE_TTL_SECONDS) -> None:
        """Store *data* as JSON under *key* with a TTL (seconds)."""
        try:
            self._client.set(key, json.dumps(data), ex=ttl)
        except Exception:
            logger.warning("Redis SET failed for key=%s", key, exc_info=True)

    def invalidate(self, pattern: str) -> None:
        """Delete all keys matching *pattern* (glob-style)."""
        try:
            keys: list[bytes] = self._client.keys(pattern)
            if keys:
                self._client.delete(*keys)
        except Exception:
            logger.warning("Redis INVALIDATE failed for pattern=%s", pattern, exc_info=True)


def get_cache() -> RedisCache | None:
    """FastAPI dependency: return a RedisCache if REDIS_URL is set, else None."""
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None
    try:
        import redis

        client = redis.from_url(redis_url, decode_responses=False)
        client.ping()
        return RedisCache(client)
    except Exception:
        logger.warning("Redis unavailable at %s — caching disabled", redis_url, exc_info=True)
        return None


def cached_response(
    cache: RedisCache | None,
    key: str,
    ttl: int,
    fetch_fn: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Return cached data for *key*, or call *fetch_fn* and cache the result.

    If *cache* is None (Redis not configured), *fetch_fn* is called directly.
    """
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            return hit

    data = fetch_fn()

    if cache is not None:
        cache.set(key, data, ttl=ttl)

    return data
