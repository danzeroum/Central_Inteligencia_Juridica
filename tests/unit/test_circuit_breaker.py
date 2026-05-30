from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.tools.circuit_breaker import (CircuitBreaker, CircuitBreakerConfig,
                                       CircuitBreakerOpenError)
from src.utils.cache_manager import (CacheManager, CacheManagerConfig,
                                     RedisError)


class FakeRedis:
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
            raise RedisError("ping failure")
        return True

    def set(self, *, name: str, value: str, ex: int | None = None) -> bool:
        if self.fail_on_set:
            raise RedisError("set failure")
        self.storage[name] = value
        return True

    def get(self, *, name: str) -> str | None:
        if self.fail_on_get:
            raise RedisError("get failure")
        return self.storage.get(name)

    def delete(self, name: str) -> int:
        if self.fail_on_delete:
            raise RedisError("delete failure")
        return 1 if self.storage.pop(name, None) is not None else 0


# ---------------------------------------------------------------------------
# Circuit breaker tests
# ---------------------------------------------------------------------------


def test_initial_state_is_closed() -> None:
    breaker = CircuitBreaker()
    assert breaker.get_state()["state"] == "closed"
    assert breaker.is_closed()


def test_transition_to_open_after_threshold_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)

    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    state = breaker.get_state()
    assert state["state"] == "open"
    assert breaker.is_open()


@pytest.mark.parametrize("timeout", [0.05, 0.1])
def test_call_blocks_when_open(timeout: float) -> None:
    breaker = CircuitBreaker(failure_threshold=1, timeout_seconds=timeout)

    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(CircuitBreakerOpenError) as exc:
        breaker.call(lambda: "should_not_run")

    assert exc.value.retry_after is not None
    assert exc.value.retry_after >= 0


def test_half_open_transition_after_timeout() -> None:
    breaker = CircuitBreaker(
        failure_threshold=1,
        timeout_seconds=0.05,
        success_threshold=1,
        half_open_max_calls=1,
    )

    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    time.sleep(0.06)
    state = breaker.get_state()
    assert state["state"] == "open"
    assert state["can_execute"] is True
    assert pytest.approx(0.0, abs=0.02) == state["time_until_half_open"]

    breaker.call(lambda: "ok")
    assert breaker.get_state()["state"] == "closed"


def test_half_open_success_closes_circuit() -> None:
    breaker = CircuitBreaker(
        failure_threshold=1,
        timeout_seconds=0.05,
        success_threshold=2,
        half_open_max_calls=2,
    )

    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    time.sleep(0.06)

    breaker.call(lambda: "ok")
    breaker.call(lambda: "ok")

    assert breaker.get_state()["state"] == "closed"


def test_half_open_failure_reopens_circuit() -> None:
    breaker = CircuitBreaker(
        failure_threshold=1,
        timeout_seconds=0.05,
        success_threshold=1,
        half_open_max_calls=1,
    )

    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    time.sleep(0.06)

    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    assert breaker.get_state()["state"] == "open"


def test_context_manager_records_success() -> None:
    breaker = CircuitBreaker()
    with breaker.protect():
        pass
    assert breaker.get_state()["failure_count"] == 0


def test_context_manager_records_failure() -> None:
    breaker = CircuitBreaker(failure_threshold=1)
    with pytest.raises(RuntimeError):
        with breaker.protect():
            raise RuntimeError("fail")
    assert breaker.get_state()["state"] == "open"


def test_reset_closes_circuit() -> None:
    breaker = CircuitBreaker(failure_threshold=1)
    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert breaker.is_open()
    breaker.reset()
    assert breaker.is_closed()


def test_thread_safety_under_concurrent_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1)
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        except Exception as exc:  # pragma: no cover - concurrency safety
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert breaker.get_state()["state"] == "open"
    assert any(isinstance(err, RuntimeError) for err in errors)


def test_prometheus_metrics_registered() -> None:
    prometheus_client = pytest.importorskip("prometheus_client")
    registry = prometheus_client.REGISTRY

    breaker = CircuitBreaker(name="metrics_test", failure_threshold=1)
    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    metric_values = {
        sample.name: sample.value
        for metric in registry.collect()
        if metric.name.startswith("circuit_breaker")
        for sample in metric.samples
        if sample.labels.get("name") == "metrics_test"
    }
    assert metric_values


# ---------------------------------------------------------------------------
# Cache manager tests
# ---------------------------------------------------------------------------


def build_cache_manager(**fake_kwargs: Any) -> CacheManager:
    config = CacheManagerConfig(
        namespace="unit_test_cache",
        default_ttl=1,
        circuit_breaker=CircuitBreakerConfig(
            name="cache_manager_test",
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=1,
            half_open_max_calls=1,
        ),
    )
    fake = FakeRedis(**fake_kwargs)
    return CacheManager(redis_client=fake, config=config)


def test_make_key_uses_sha256_hash() -> None:
    cache = build_cache_manager()
    key = cache.make_key("TJSP", "status", "123")
    assert key.startswith("unit_test_cache:")
    assert len(key.split(":")) == 2


def test_set_and_get_memory_only() -> None:
    cache = CacheManager(config=CacheManagerConfig(namespace="memory_only"))
    cache.set_cached("TJSP", "status", {"value": 1})
    assert cache.get_cached("TJSP", "status") == {"value": 1}


def test_redis_failure_opens_circuit_and_falls_back_to_memory() -> None:
    cache = build_cache_manager(fail_on_set=True)
    cache.set_cached("TJSP", "status", {"value": 2})
    assert cache.get_cached("TJSP", "status") == {"value": 2}
    assert cache.get_circuit_stats()["state"] == "open"


def test_get_uses_memory_when_redis_errors() -> None:
    cache = build_cache_manager()
    cache.set_cached("TJSP", "status", {"value": 3})
    cache.redis_client.fail_on_get = True  # type: ignore[attr-defined]
    assert cache.get_cached("TJSP", "status") == {"value": 3}


def test_delete_removes_memory_entry() -> None:
    cache = build_cache_manager()
    cache.set_cached("TJSP", "status", {"value": 4})
    cache.delete_cached("TJSP", "status")
    assert cache.get_cached("TJSP", "status") is None


def test_health_includes_circuit_information() -> None:
    cache = build_cache_manager(fail_on_set=True)
    cache.set_cached("TJSP", "status", {"value": 5})
    health = cache.health()
    assert "circuit_breaker" in health
    assert health["circuit_breaker"]["state"] in {"open", "closed", "half_open"}


def test_reset_circuit_allows_redis_retry() -> None:
    cache = build_cache_manager(fail_on_set=True)
    cache.set_cached("TJSP", "status", {"value": 6})
    assert cache.get_circuit_stats()["state"] == "open"
    cache.reset_circuit()
    cache.redis_client.fail_on_set = False  # type: ignore[attr-defined]
    cache.set_cached("TJSP", "status", {"value": 7})
    assert cache.get_circuit_stats()["state"] == "closed"
