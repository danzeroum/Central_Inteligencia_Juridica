"""Unit tests for CacheManager."""

from __future__ import annotations

import time

import pytest

from src.utils.cache_manager import CacheManager, CacheManagerConfig


@pytest.fixture
def cache() -> CacheManager:
    config = CacheManagerConfig(namespace="test")
    return CacheManager(config=config)


class TestSetGetCached:
    def test_set_and_get(self, cache: CacheManager) -> None:
        cache.set_cached("key1", "value1")
        result = cache.get_cached("key1")
        assert result == "value1"

    def test_get_missing_key_returns_none(self, cache: CacheManager) -> None:
        result = cache.get_cached("nonexistent")
        assert result is None

    def test_overwrite_key(self, cache: CacheManager) -> None:
        cache.set_cached("key1", "value1")
        cache.set_cached("key1", "value2")
        result = cache.get_cached("key1")
        assert result == "value2"


class TestDeleteCached:
    def test_delete_existing_key(self, cache: CacheManager) -> None:
        cache.set_cached("key1", "value1")
        cache.delete_cached("key1")
        assert cache.get_cached("key1") is None

    def test_delete_nonexistent_key_no_error(self, cache: CacheManager) -> None:
        cache.delete_cached("nonexistent")  # Should not raise


class TestHealth:
    def test_health_returns_dict(self, cache: CacheManager) -> None:
        result = cache.health()
        assert isinstance(result, dict)
        assert "status" in result
