"""Cache manager backed by Redis with graceful degradation to memory."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

try:  # pragma: no cover - optional dependency path
    import redis
except Exception:  # pragma: no cover - fallback when redis lib missing
    redis = None  # type: ignore

logger = logging.getLogger(__name__)


class CacheManager:
    """Simple cache abstraction with Redis backend and in-memory fallback."""

    def __init__(self, redis_url: str = "redis://localhost:6379", default_ttl: int = 3600) -> None:
        self.default_ttl = default_ttl
        self._redis_url = redis_url
        self._redis_client = self._initialize_redis(redis_url)
        self._memory_cache: Dict[str, Tuple[float, Any]] = {}
        self._memory_lock = threading.Lock()

    def _initialize_redis(self, redis_url: str):  # type: ignore[no-untyped-def]
        if not redis:
            logger.warning("Redis library not available. Falling back to in-memory cache.")
            return None

        try:
            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            logger.info("Connected to Redis cache at %s", redis_url)
            return client
        except Exception as exc:  # pragma: no cover - external service
            logger.warning("Could not connect to Redis at %s: %s", redis_url, exc)
            return None

    def _generate_key(self, tribunal: str, operation: str, params: Dict[str, Any]) -> str:
        content = f"{tribunal}:{operation}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get_cached(self, tribunal: str, operation: str, params: Dict[str, Any]) -> Optional[Any]:
        key = self._generate_key(tribunal, operation, params)

        if self._redis_client:
            cached = self._redis_client.get(key)
            if cached is not None:
                return json.loads(cached)
            return None

        with self._memory_lock:
            item = self._memory_cache.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < time.time():
                del self._memory_cache[key]
                return None
            return value

    def set_cache(
        self,
        tribunal: str,
        operation: str,
        params: Dict[str, Any],
        result: Any,
        ttl: Optional[int] = None,
    ) -> None:
        key = self._generate_key(tribunal, operation, params)
        payload = json.dumps(result)
        ttl_value = ttl or self.default_ttl

        if self._redis_client:
            self._redis_client.setex(key, ttl_value, payload)
            return

        with self._memory_lock:
            self._memory_cache[key] = (time.time() + ttl_value, result)

    def health(self) -> Dict[str, Any]:
        """Return cache backend health metadata."""

        if self._redis_client:
            try:
                self._redis_client.ping()
                backend = "redis"
                status = "healthy"
            except Exception as exc:  # pragma: no cover - external service
                backend = "redis"
                status = "degraded"
                return {
                    "backend": backend,
                    "status": status,
                    "detail": str(exc),
                }
            return {"backend": backend, "status": status}

        with self._memory_lock:
            size = len(self._memory_cache)
        return {"backend": "memory", "status": "healthy", "entries": size}


_global_cache: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheManager()
    return _global_cache


__all__ = ["CacheManager", "get_cache_manager"]
