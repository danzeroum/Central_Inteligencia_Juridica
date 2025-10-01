"""Test observability metrics collection."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from prometheus_client import REGISTRY
from src.utils.decision_metrics import DecisionMetricsCollector


def test_decision_metrics_collected():
    """Verifica que métricas de decisão são coletadas."""

    # Registrar decisão
    DecisionMetricsCollector.record_decision(
        agent="test_agent",
        decision_type="test_decision",
        outcome="success",
        confidence=0.85,
        duration_seconds=1.5,
    )

    assert (
        REGISTRY.get_sample_value(
            "agent_decisions_total",
            labels={
                "agent": "test_agent",
                "decision_type": "test_decision",
                "outcome": "success",
            },
        )
        is not None
    )
    assert (
        REGISTRY.get_sample_value(
            "agent_decision_confidence_count",
            labels={
                "agent": "test_agent",
                "decision_type": "test_decision",
            },
        )
        is not None
    )
    assert (
        REGISTRY.get_sample_value(
            "agent_decision_duration_seconds_count",
            labels={
                "agent": "test_agent",
                "decision_type": "test_decision",
            },
        )
        is not None
    )

    print("✅ Decision metrics collected successfully")


def test_consensus_metrics_collected():
    """Verifica que métricas de consenso são coletadas."""

    DecisionMetricsCollector.record_consensus(
        decision_type="test_consensus",
        strength=0.75,
        participants=3,
        winning_agent="agent_a",
        outcome="strong",
    )

    assert (
        REGISTRY.get_sample_value(
            "consensus_strength_count",
            labels={"decision_type": "test_consensus"},
        )
        is not None
    )
    assert (
        REGISTRY.get_sample_value(
            "consensus_participants",
            labels={"decision_type": "test_consensus"},
        )
        is not None
    )

    print("✅ Consensus metrics collected successfully")


def test_hitl_metrics_collected():
    """Verifica que métricas HITL são coletadas."""

    DecisionMetricsCollector.record_hitl_request(
        agent="test_agent",
        status="approved",
        response_time_seconds=45.0,
    )

    DecisionMetricsCollector.update_hitl_queue_depth(5)

    assert (
        REGISTRY.get_sample_value(
            "hitl_requests_total",
            labels={"agent": "test_agent", "status": "approved"},
        )
        is not None
    )
    assert (
        REGISTRY.get_sample_value(
            "hitl_response_time_seconds_count",
            labels={"agent": "test_agent", "outcome": "approved"},
        )
        is not None
    )
    assert REGISTRY.get_sample_value("hitl_queue_depth") is not None

    print("✅ HITL metrics collected successfully")


if __name__ == "__main__":
    test_decision_metrics_collected()
    test_consensus_metrics_collected()
    test_hitl_metrics_collected()
    print("\n✅ Todos os testes de observabilidade passaram!")
