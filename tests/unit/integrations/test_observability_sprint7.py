"""Testes de observabilidade (Sprint 7)."""

from __future__ import annotations

import pytest


class TestSpanRecordContextManager:
    """SpanRecord deve funcionar como context manager (Sprint 7)."""

    def test_span_as_context_manager(self):
        from src.utils.observability import SpanRecord

        span = SpanRecord(operation="test_op", metadata={})
        assert span.end_time is None

        with span as s:
            assert s is span  # __enter__ retorna self

        assert span.end_time is not None  # close() foi chamado

    def test_span_close_on_exit(self):
        from src.utils.observability import SpanRecord

        span = SpanRecord(operation="test_op", metadata={})
        with span:
            pass
        assert span.end_time is not None

    def test_span_exception_does_not_suppress(self):
        from src.utils.observability import SpanRecord

        span = SpanRecord(operation="test_op", metadata={})
        with pytest.raises(ValueError):
            with span:
                raise ValueError("test error")
        # end_time ainda foi setado mesmo com exceção
        assert span.end_time is not None


class TestAgentObserverWithContextManager:
    """AgentOrchestrator usa AgentObserver (não NullObserver)."""

    def test_orchestrator_uses_agent_observer(self):
        from src.utils.observability import AgentObserver

        # Verifica que src/orchestrator.py usa AgentObserver
        import inspect
        import src.orchestrator as orch_mod

        source = inspect.getsource(orch_mod)
        assert "AgentObserver" in source
        # Verifica que NullObserver não é usado como observer ativo (pode existir em comentários)
        assert "self.observer = NullObserver()" not in source

    def test_agent_observer_exports_trajectory(self):
        from src.utils.observability import AgentObserver

        observer = AgentObserver()
        span = observer.start_span("operation_x", {"key": "value"})
        span.log_reasoning("reasoning step 1")
        span.close()

        trajectory = observer.export_trajectory()
        assert trajectory["trace_id"] is not None
        assert len(trajectory["spans"]) == 1
        assert trajectory["spans"][0]["operation"] == "operation_x"
        assert "reasoning step 1" in trajectory["spans"][0]["reasoning_log"]


class TestMetricsExist:
    def test_metrics_importable(self):
        from src.integrations.metrics import (
            integrations_queries_total,
            integrations_latency_seconds,
            integrations_cache_hits_total,
            circuit_breaker_state,
            integrations_risk_score,
            integrations_hitl_triggered_total,
        )

        # Verifica que são objetos Prometheus válidos
        assert integrations_queries_total is not None
        assert integrations_latency_seconds is not None

    def test_record_query_metric(self):
        from src.integrations.metrics import record_query

        # Deve executar sem erros
        record_query("test_source", "success", "mock", 0.1)

    def test_record_cache_hit(self):
        from src.integrations.metrics import record_cache_hit

        record_cache_hit("test_source")

    def test_record_circuit_state(self):
        from src.integrations.metrics import record_circuit_state

        record_circuit_state("integration_test", "open")
        record_circuit_state("integration_test", "closed")


class TestDashboardFile:
    def test_dashboard_json_exists_and_valid(self):
        import json
        from pathlib import Path

        dashboard_file = (
            Path(__file__).resolve().parents[3]
            / "monitoring"
            / "grafana"
            / "provisioning"
            / "dashboards"
            / "json"
            / "integrations-intelligence.json"
        )
        assert dashboard_file.exists(), f"Dashboard não encontrado: {dashboard_file}"
        data = json.loads(dashboard_file.read_text())
        assert "title" in data
        assert "panels" in data
        assert len(data["panels"]) > 0

    def test_alert_rules_have_integrations_group(self):
        import yaml
        from pathlib import Path

        alert_file = (
            Path(__file__).resolve().parents[3] / "monitoring" / "alert_rules.yml"
        )
        data = yaml.safe_load(alert_file.read_text())
        groups = {g["name"]: g for g in data.get("groups", [])}
        assert "cij-integrations" in groups
        rules = groups["cij-integrations"]["rules"]
        rule_names = {r["alert"] for r in rules}
        assert "IntegrationSourceDown" in rule_names
        assert "IntegrationHighFailureRate" in rule_names
        assert "IntegrationHighLatency" in rule_names
