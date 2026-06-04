"""Testes do MetricsCollector, incluindo o snapshot agregado (Frente C).

O ``snapshot()`` foi adicionado ao corrigir um bug latente: ``/health?verbose=true``
chamava ``MetricsCollector.snapshot()``, que não existia (AttributeError → 500).
"""

from __future__ import annotations

from src.utils.metrics_collector import MetricsCollector


def test_snapshot_has_expected_keys():
    snap = MetricsCollector.snapshot()
    assert set(snap) == {
        "tasks_total",
        "cache_hits_total",
        "api_errors_total",
        "active_agents",
    }
    assert all(isinstance(v, (int, float)) for v in snap.values())


def test_snapshot_reflects_recorded_metrics():
    before = MetricsCollector.snapshot()["cache_hits_total"]
    MetricsCollector.record_cache_hit("TJSP", "consulta")
    after = MetricsCollector.snapshot()["cache_hits_total"]
    assert after == before + 1


def test_snapshot_reflects_active_agents():
    MetricsCollector.set_agent_active("TJTEST", True)
    assert MetricsCollector.snapshot()["active_agents"] >= 1
