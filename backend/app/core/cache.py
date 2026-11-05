"""Thread-safe In-Memory TTL Cache for Fast Platform API Responses."""

import time
import functools
import logging
import threading
from collections import OrderedDict
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger("cache")


class MemoryTTLCache:
    """Thread-safe, bounded in-memory cache with Time-To-Live (TTL) and LRU eviction."""

    def __init__(self, maxsize: int = 1000):
        self._store: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._store:
                expires_at, value = self._store[key]
                if time.time() < expires_at:
                    self._store.move_to_end(key)
                    return value
                else:
                    del self._store[key]
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 45) -> None:
        now = time.time()
        with self._lock:
            if key in self._store:
                del self._store[key]
            elif len(self._store) >= self._maxsize:
                # Evict expired entries first
                expired_keys = [k for k, (exp, _) in self._store.items() if now >= exp]
                for k in expired_keys:
                    del self._store[k]
                # If still at capacity, evict oldest (LRU) entry
                while len(self._store) >= self._maxsize:
                    self._store.popitem(last=False)

            self._store[key] = (now + ttl_seconds, value)

    def invalidate(self, prefix: Optional[str] = None) -> None:
        with self._lock:
            if prefix is None:
                self._store.clear()
            else:
                keys_to_del = [k for k in self._store if k.startswith(prefix)]
                for k in keys_to_del:
                    del self._store[k]

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


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
