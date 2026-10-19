"""Thread-safe In-Memory TTL Cache for Fast Platform API Responses."""

import time
import functools
import logging
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("cache")

class MemoryTTLCache:
    """Simple, high-performance in-memory cache with Time-To-Live (TTL)."""
    def __init__(self):
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            expires_at, value = self._store[key]
            if time.time() < expires_at:
                return value
            else:
                del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl_seconds: int = 45) -> None:
        self._store[key] = (time.time() + ttl_seconds, value)

    def invalidate(self, prefix: Optional[str] = None) -> None:
        if prefix is None:
            self._store.clear()
        else:
            keys_to_del = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_del:
                del self._store[k]

cache = MemoryTTLCache()


def cached_endpoint(ttl_seconds: int = 45, key_prefix: str = ""):
    """Decorator for caching service method returns based on arguments."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Exclude self/cls from cache key
            call_args = args[1:] if args else ()
            cache_key = f"{key_prefix or func.__name__}:{str(call_args)}:{str(sorted(kwargs.items()))}"
            hit = cache.get(cache_key)
            if hit is not None:
                return hit
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds)
            return result
        return wrapper
    return decorator
