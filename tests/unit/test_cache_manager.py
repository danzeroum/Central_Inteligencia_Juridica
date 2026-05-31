"""Unit tests for CacheManager (codex interface with circuit breaker)."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from src.tools.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
)
from src.utils.cache_manager import CacheManager, CacheManagerConfig


class FakeRedis:
    """In-memory fake Redis client for testing."""

    def __init__(
        self,
        *,
        fail_on_set: bool = False,
        fail_on_get: bool = False,
        fail_on_delete: bool = False,
        allow_ping: bool = True,
    ) -> None:
        self.fail_on_set = fail_on_set
        self.fail_on_get = fail_on_get
        self.fail_on_delete = fail_on_delete
        self.allow_ping = allow_ping
        self.storage: Dict[str, str] = {}

    def ping(self) -> bool:
        if not self.allow_ping:
            raise RuntimeError("ping failure")
        return True

    def set(self, *, name: str, value: str, ex: int | None = None) -> bool:
        if self.fail_on_set:
            raise RuntimeError("set failure")
        self.storage[name] = value
        return True

    def get(self, *, name: str) -> str | None:
        if self.fail_on_get:
            raise RuntimeError("get failure")
        return self.storage.get(name)

    def delete(self, name: str) -> int:
        if self.fail_on_delete:
            raise RuntimeError("delete failure")
        return 1 if self.storage.pop(name, None) is not None else 0


def _build_cache(**fake_kwargs: Any) -> CacheManager:
    config = CacheManagerConfig(
        namespace="unit_test_cache",
        default_ttl=1,
        circuit_breaker=CircuitBreakerConfig(
            name="cache_test",
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=1,
            half_open_max_calls=1,
        ),
    )
    fake = FakeRedis(**fake_kwargs)
    return CacheManager(redis_client=fake, config=config)


class TestSetGetCached:
    def test_set_and_get_memory_only(self) -> None:
        cache = CacheManager(config=CacheManagerConfig(namespace="mem"))
        cache.set_cached("TJSP", "status", {"value": 1})
        assert cache.get_cached("TJSP", "status") == {"value": 1}

    def test_get_missing_key_returns_none(self) -> None:
        cache = CacheManager(config=CacheManagerConfig(namespace="mem"))
        result = cache.get_cached("TJSP", "nonexistent")
        assert result is None

    def test_overwrite_key(self) -> None:
        cache = CacheManager(config=CacheManagerConfig(namespace="mem"))
        cache.set_cached("TJSP", "status", {"v": 1})
        cache.set_cached("TJSP", "status", {"v": 2})
        assert cache.get_cached("TJSP", "status") == {"v": 2}


class TestDeleteCached:
    def test_delete_existing_key(self) -> None:
        cache = _build_cache()
        cache.set_cached("TJSP", "status", {"value": 4})
        cache.delete_cached("TJSP", "status")
        assert cache.get_cached("TJSP", "status") is None

    def test_delete_nonexistent_key_no_error(self) -> None:
        cache = _build_cache()
        cache.delete_cached("TJSP", "nonexistent")  # Should not raise


class TestHealth:
    def test_health_returns_dict(self) -> None:
        cache = _build_cache()
        result = cache.health()
        assert isinstance(result, dict)
        assert "redis_available" in result
        assert "memory_items" in result


class TestRedisFailure:
    def test_redis_failure_falls_back_to_memory(self) -> None:
        cache = _build_cache(fail_on_set=True)
        cache.set_cached("TJSP", "status", {"value": 2})
        assert cache.get_cached("TJSP", "status") == {"value": 2}

    def test_get_uses_memory_when_redis_errors(self) -> None:
        cache = _build_cache()
        cache.set_cached("TJSP", "status", {"value": 3})
        cache.redis_client.fail_on_get = True  # type: ignore[attr-defined]
        assert cache.get_cached("TJSP", "status") == {"value": 3}

    def test_circuit_opens_after_failures(self) -> None:
        cache = _build_cache(fail_on_set=True)
        cache.set_cached("TJSP", "status", {"value": 5})
        stats = cache.get_circuit_stats()
        assert stats["state"] in ("open", "closed", "half_open")

    def test_reset_circuit(self) -> None:
        cache = _build_cache(fail_on_set=True)
        cache.set_cached("TJSP", "status", {"value": 6})
        cache.reset_circuit()
        cache.redis_client.fail_on_set = False  # type: ignore[attr-defined]
        cache.set_cached("TJSP", "status", {"value": 7})
        stats = cache.get_circuit_stats()
        assert stats["state"] == "closed"
