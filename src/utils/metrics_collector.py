"""Prometheus metrics collector helpers for tribunal operations."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import Counter, Gauge, Histogram

# Prometheus metrics definitions
_task_counter = Counter(
    "tribunal_tasks_total",
    "Total tasks processed",
    labelnames=("tribunal", "operation"),
)
_task_duration = Histogram(
    "tribunal_task_duration_seconds",
    "Task duration in seconds",
    labelnames=("tribunal", "operation"),
)
_active_agents = Gauge(
    "active_tribunal_agents",
    "Number of active tribunal agents",
    labelnames=("tribunal",),
)
_cache_hits = Counter(
    "cache_hits_total",
    "Number of cache hits",
    labelnames=("tribunal", "operation"),
)
_api_errors = Counter(
    "api_errors_total",
    "Total API errors",
    labelnames=("tribunal", "error_type"),
)


class MetricsCollector:
    """Utility wrapper over Prometheus metrics with safe defaults."""

    @staticmethod
    def record_task(tribunal: str, operation: str, duration: float, success: bool) -> None:
        _task_counter.labels(tribunal=tribunal, operation=operation).inc()
        _task_duration.labels(tribunal=tribunal, operation=operation).observe(duration)
        if not success:
            _api_errors.labels(tribunal=tribunal, error_type="task_failure").inc()

    @staticmethod
    def record_cache_hit(tribunal: str, operation: str) -> None:
        _cache_hits.labels(tribunal=tribunal, operation=operation).inc()

    @staticmethod
    def record_api_error(tribunal: str, error_type: str) -> None:
        _api_errors.labels(tribunal=tribunal, error_type=error_type).inc()

    @staticmethod
    def set_agent_active(tribunal: str, active: bool) -> None:
        _active_agents.labels(tribunal=tribunal).set(1 if active else 0)

    @staticmethod
    def set_total_agents(counts: dict[str, int]) -> None:
        for tribunal, count in counts.items():
            _active_agents.labels(tribunal=tribunal).set(count)

    @staticmethod
    @contextmanager
    def track_task(tribunal: str, operation: str) -> Iterator[None]:
        start = time.perf_counter()
        success = True
        try:
            yield
        except Exception:  # pragma: no cover - delegated to caller
            success = False
            MetricsCollector.record_api_error(tribunal, "exception")
            raise
        finally:
            duration = time.perf_counter() - start
            MetricsCollector.record_task(tribunal, operation, duration, success)


__all__ = ["MetricsCollector"]
