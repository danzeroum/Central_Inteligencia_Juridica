"""Métricas Prometheus para a camada de integrações jurídicas."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, REGISTRY


def _get_or_create(metric_cls, name, *args, **kwargs):
    """Return existing metric if already registered, otherwise create new one."""
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return metric_cls(name, *args, **kwargs)


integrations_queries_total = _get_or_create(
    Counter,
    "integrations_queries_total",
    "Total de consultas por fonte de integração",
    ["source", "status", "data_mode"],
)

integrations_latency_seconds = _get_or_create(
    Histogram,
    "integrations_latency_seconds",
    "Latência das consultas de integração em segundos",
    ["source"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

integrations_cache_hits_total = _get_or_create(
    Counter,
    "integrations_cache_hits_total",
    "Total de cache hits nas integrações",
    ["source"],
)

circuit_breaker_state = _get_or_create(
    Gauge,
    "circuit_breaker_state",
    "Estado do circuit breaker (0=closed, 1=open, 2=half_open)",
    ["name"],
)

integrations_risk_score = _get_or_create(
    Histogram,
    "integrations_risk_score",
    "Distribuição dos risk scores calculados",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
)

integrations_hitl_triggered_total = _get_or_create(
    Counter,
    "integrations_hitl_triggered_total",
    "Total de relatórios retidos pelo gate HITL",
)


def record_query(source: str, status: str, data_mode: str, latency_s: float) -> None:
    integrations_queries_total.labels(
        source=source, status=status, data_mode=data_mode
    ).inc()
    integrations_latency_seconds.labels(source=source).observe(latency_s)


def record_cache_hit(source: str) -> None:
    integrations_cache_hits_total.labels(source=source).inc()


def record_circuit_state(name: str, state: str) -> None:
    state_map = {"closed": 0, "open": 1, "half_open": 2}
    circuit_breaker_state.labels(name=name).set(state_map.get(state, 0))


__all__ = [
    "integrations_queries_total",
    "integrations_latency_seconds",
    "integrations_cache_hits_total",
    "circuit_breaker_state",
    "integrations_risk_score",
    "integrations_hitl_triggered_total",
    "record_query",
    "record_cache_hit",
    "record_circuit_state",
]
