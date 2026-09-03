"""In-memory response cache with TTL for frequently accessed endpoints.

Reduces database load and improves response times for read-heavy endpoints
like dashboard KPIs, analytics, and risk trends.

Configurable via environment:
- CACHE_ENABLED: enable/disable (default true)
- CACHE_DEFAULT_TTL: default TTL in seconds (default 30)
- CACHE_MAX_ENTRIES: max cached responses (default 500)

Usage:
    from app.core.response_cache import cache_response, invalidate_cache

    @router.get("/dashboard")
    @cache_response(ttl=15)
    async def get_dashboard():
        ...

    # After write operations:
    invalidate_cache("/api/dashboard")
"""

import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from functools import wraps
from typing import Callable, Optional

logger = logging.getLogger(__name__)

CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "30"))
CACHE_MAX_ENTRIES = int(os.getenv("CACHE_MAX_ENTRIES", "500"))


class ResponseCache:
    """LRU cache with TTL support for API responses."""

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES):
        self.max_entries = max_entries
        self._cache: OrderedDict[str, tuple[float, float, any]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _make_key(self, method: str, path: str, params: dict = None, user_id: int = None) -> str:
        """Generate cache key from request details."""
        key_parts = [method, path]
        if params:
            key_parts.append(json.dumps(params, sort_keys=True))
        if user_id:
            key_parts.append(str(user_id))
        raw = ":".join(key_parts)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[tuple]:
        """Get cached response if valid (not expired)."""
        if not CACHE_ENABLED:
            return None

        if key in self._cache:
            timestamp, ttl, response = self._cache[key]
            if time.time() - timestamp < ttl:
                self._hits += 1
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                return response
            else:
                # Expired
                del self._cache[key]

        self._misses += 1
        return None

    def set(self, key: str, response, ttl: int = CACHE_DEFAULT_TTL) -> None:
        """Cache a response with TTL."""
        if not CACHE_ENABLED:
            return

        # Evict oldest if at capacity
        while len(self._cache) >= self.max_entries:
            self._cache.popitem(last=False)

        self._cache[key] = (time.time(), ttl, response)

    def invalidate(self, pattern: str = None) -> int:
        """Invalidate cache entries matching a pattern."""
        if pattern is None:
            count = len(self._cache)
            self._cache.clear()
            return count

        keys_to_remove = [k for k in self._cache if pattern in k]
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        return {
            "enabled": CACHE_ENABLED,
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(
                (self._hits / total_requests * 100) if total_requests > 0 else 0, 1
            ),
        }


# Singleton instance
response_cache = ResponseCache()


def cache_response(ttl: int = CACHE_DEFAULT_TTL, key_prefix: str = ""):
    """Decorator to cache endpoint responses.

    Usage:
        @router.get("/dashboard")
        @cache_response(ttl=15)
        async def get_dashboard():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key from function name and kwargs
            cache_key = response_cache._make_key(
                method="GET",
                path=f"{key_prefix}:{func.__name__}",
                params={k: v for k, v in kwargs.items() if v is not None and not hasattr(v, '__dict__') and not callable(getattr(v, '__call__', None))},
            )

            # Check cache
            cached = response_cache.get(cache_key)
            if cached is not None:
                return cached

            # Call original function
            result = await func(*args, **kwargs)

            # Cache the result
            response_cache.set(cache_key, result, ttl=ttl)
            return result

        return wrapper
    return decorator


def invalidate_cache(pattern: str = None) -> int:
    """Invalidate cached responses matching a pattern."""
    return response_cache.invalidate(pattern)
