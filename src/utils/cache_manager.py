"""Dynamic cache manager with Redis backend protected by a circuit breaker."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency guard
    import redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - redis not installed
    redis = None  # type: ignore
    RedisError = RuntimeError  # type: ignore

from src.tools.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)


@dataclass
class CacheManagerConfig:
    """Configuration holder for :class:`CacheManager`."""

    namespace: str = "ci_cache"
    default_ttl: int = 300
    circuit_breaker: CircuitBreakerConfig = field(
        default_factory=lambda: CircuitBreakerConfig(
            name="cache_manager_redis",
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=3,
            half_open_max_calls=3,
        )
    )


class CacheManager:
    """Centralised cache manager with Redis + in-memory fallback."""

    def __init__(
        self,
        *,
        redis_client: Optional["redis.Redis"] = None,
        config: Optional[CacheManagerConfig] = None,
    ) -> None:
        self.config = config or CacheManagerConfig()
        self._lock = RLock()
        self._memory_store: Dict[str, tuple[Any, float | None]] = {}

        self.redis_client = redis_client or self._create_redis_client()
        self.circuit_breaker = CircuitBreaker(config=self.config.circuit_breaker)
        self._redis_available = self._test_redis_connection()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def make_key(
        self,
        tribunal: str,
        category: str,
        identifier: str | None = None,
    ) -> str:
        """Return a deterministic cache key hashed with SHA-256."""

        parts = [self.config.namespace, tribunal, category]
        if identifier:
            parts.append(identifier)
        raw_key = ":".join(parts)
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"{self.config.namespace}:{digest}"

    def set_cached(
        self,
        tribunal: str,
        category: str,
        value: Any,
        *,
        identifier: str | None = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Store a value using double-write (Redis + memory)."""

        key = self.make_key(tribunal, category, identifier)
        ttl = ttl if ttl is not None else self.config.default_ttl
        self._write_memory(key, value, ttl)

        if not self._should_use_redis():
            return

        payload = self._serialize(value)
        try:
            self.circuit_breaker.call(self._redis_set, key, payload, ttl)
        except CircuitBreakerOpenError as exc:
            logger.warning(
                "Circuit breaker OPEN for cache manager (%s). Using memory fallback.",
                exc.name or self.config.circuit_breaker.name,
            )
        except RedisError as exc:
            logger.error("Redis set failed: %s", exc)
            self._redis_available = False
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error writing to Redis: %s", exc)

    def get_cached(
        self,
        tribunal: str,
        category: str,
        *,
        identifier: str | None = None,
    ) -> Any | None:
        """Retrieve value with automatic Redis → memory fallback."""

        key = self.make_key(tribunal, category, identifier)

        if self._should_use_redis():
            try:
                result = self.circuit_breaker.call(self._redis_get, key)
            except CircuitBreakerOpenError:
                result = None
            except RedisError as exc:
                logger.error("Redis get failed: %s", exc)
                self._redis_available = False
                result = None
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Unexpected error reading from Redis: %s", exc)
                result = None

            if result is not None:
                value = self._deserialize(result)
                self._write_memory(key, value, self.config.default_ttl)
                return value

        return self._read_memory(key)

    def delete_cached(
        self,
        tribunal: str,
        category: str,
        *,
        identifier: str | None = None,
    ) -> None:
        """Delete cached value from both Redis and memory."""

        key = self.make_key(tribunal, category, identifier)
        with self._lock:
            self._memory_store.pop(key, None)

        if not self._should_use_redis():
            return

        try:
            self.circuit_breaker.call(self._redis_delete, key)
        except CircuitBreakerOpenError:
            logger.info("Circuit open during delete; memory entry already removed")
        except RedisError as exc:
            logger.error("Redis delete failed: %s", exc)
            self._redis_available = False
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error deleting from Redis: %s", exc)

    def health(self) -> Dict[str, Any]:
        """Return diagnostic information about cache backends."""

        with self._lock:
            memory_items = len(self._memory_store)
        state = self.get_circuit_stats()
        return {
            "redis_available": self._redis_available,
            "redis_enabled": self.redis_client is not None,
            "memory_items": memory_items,
            "circuit_breaker": state,
        }

    def get_circuit_stats(self) -> Dict[str, Any]:
        return self.circuit_breaker.get_state()

    def reset_circuit(self) -> None:
        self.circuit_breaker.reset()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _create_redis_client(self) -> Optional["redis.Redis"]:
        if redis is None:
            return None

        url = os.getenv("REDIS_URL")
        if url:
            try:
                return redis.from_url(url)
            except RedisError as exc:  # pragma: no cover - connection error path
                logger.error("Failed to connect to Redis via URL: %s", exc)
                return None

        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        password = os.getenv("REDIS_PASSWORD")

        try:
            return redis.Redis(host=host, port=port, db=db, password=password)
        except RedisError as exc:  # pragma: no cover - connection error path
            logger.error("Failed to initialise Redis client: %s", exc)
            return None

    def _test_redis_connection(self) -> bool:
        if self.redis_client is None:
            return False
        try:
            self.redis_client.ping()
            return True
        except RedisError as exc:
            logger.warning("Redis ping failed: %s. Falling back to memory.", exc)
            return False

    def _should_use_redis(self) -> bool:
        if self.redis_client is None:
            return False

        if not self._redis_available and self.circuit_breaker.is_closed():
            self._redis_available = self._test_redis_connection()

        if self.circuit_breaker.is_open():
            return False

        return self._redis_available

    def _write_memory(self, key: str, value: Any, ttl: Optional[int]) -> None:
        expires_at: float | None
        if ttl is None or ttl <= 0:
            expires_at = None
        else:
            expires_at = time.monotonic() + ttl
        with self._lock:
            self._memory_store[key] = (value, expires_at)

    def _read_memory(self, key: str) -> Any | None:
        with self._lock:
            entry = self._memory_store.get(key)
            if not entry:
                return None
            value, expires_at = entry
            if expires_at is not None and time.monotonic() >= expires_at:
                self._memory_store.pop(key, None)
                return None
            return value

    def _redis_set(self, key: str, value: str, ttl: Optional[int]) -> bool:
        if self.redis_client is None:
            raise RuntimeError("Redis client not configured")
        if ttl is None or ttl <= 0:
            return bool(self.redis_client.set(name=key, value=value))
        return bool(self.redis_client.set(name=key, value=value, ex=ttl))

    def _redis_get(self, key: str) -> Optional[str]:
        if self.redis_client is None:
            raise RuntimeError("Redis client not configured")
        data = self.redis_client.get(name=key)
        if data is None:
            return None
        if isinstance(data, bytes):
            return data.decode("utf-8")
        return str(data)

    def _redis_delete(self, key: str) -> int:
        if self.redis_client is None:
            raise RuntimeError("Redis client not configured")
        return int(self.redis_client.delete(key))

    @staticmethod
    def _serialize(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _deserialize(value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
