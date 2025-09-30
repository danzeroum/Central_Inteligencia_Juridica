"""Integration tests for the training system."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.training.learning_metrics import LearningMetricsCollector
from src.training.training_manager import TrainingManager


@pytest.mark.asyncio
async def test_training_manager_initialization() -> None:
    """Test that TrainingManager initializes correctly."""

    manager = TrainingManager()

    assert manager.evaluator is not None
    assert manager.router is not None
    assert manager.ab_framework is not None
    assert manager.ledger is not None
    assert len(manager.training_states) == 0
    assert len(manager.active_sessions) == 0


@pytest.mark.asyncio
async def test_feedback_submission() -> None:
    """Test submitting feedback for an agent."""

    manager = TrainingManager()

    await manager.process_feedback(
        agent_type="TJSP",
        task_result={"success": True, "latency": 0.5},
        user_rating=0.9,
        corrections=None,
    )

    assert "TJSP" in manager.feedback_queue
    assert len(manager.feedback_queue["TJSP"]) == 1
    assert manager.feedback_queue["TJSP"][0]["user_rating"] == 0.9


@pytest.mark.asyncio
async def test_training_session_lifecycle() -> None:
    """Test complete training session lifecycle."""

    manager = TrainingManager()

    for index in range(manager.min_feedback_for_training):
        await manager.process_feedback(
            agent_type="TJMG",
            task_result={"success": True, "latency": 0.3 + index * 0.1},
            user_rating=0.8 + index * 0.01,
        )

    result = await manager.train_agent("TJMG")

    assert result["status"] == "completed"
    assert "metrics" in result
    assert "improvements" in result
    assert result["feedback_processed"] == manager.min_feedback_for_training

    assert "TJMG" in manager.training_states
    state = manager.training_states["TJMG"]
    assert state.total_sessions == 1
    assert state.last_training is not None


@pytest.mark.asyncio
async def test_insufficient_feedback_handling() -> None:
    """Test that training requires minimum feedback."""

    manager = TrainingManager()

    await manager.process_feedback(
        agent_type="TJRS",
        task_result={"success": True},
        user_rating=0.7,
    )

    assert len(manager.active_sessions) == 0


@pytest.mark.asyncio
async def test_training_stats_retrieval() -> None:
    """Test retrieving training statistics."""

    manager = TrainingManager()

    await manager.process_feedback(
        agent_type="STF",
        task_result={"success": True},
        user_rating=0.95,
    )

    stats = manager.get_training_stats("STF")

    assert "agent_type" in stats
    assert stats["agent_type"] == "STF"
    assert "pending_feedback" in stats
    assert stats["pending_feedback"] == 1


@pytest.mark.asyncio
async def test_ab_testing() -> None:
    """Test A/B testing between agent variants."""

    manager = TrainingManager()

    test_cases = [
        {"task": "status check"},
        {"task": "process query"},
    ]

    result = await manager.run_ab_test(
        agent_a_type="TJSP_v1",
        agent_b_type="TJSP_v2",
        test_cases=test_cases,
    )

    assert "winner" in result
    assert "scores" in result
    assert result["winner"] in ["A", "B"]


def test_metrics_collector_initialization() -> None:
    """Test that metrics collector initializes properly."""

    collector = LearningMetricsCollector(window_size=50)

    assert collector.window_size == 50
    assert len(collector.metrics) == 0


def test_metrics_recording() -> None:
    """Test recording metrics."""

    collector = LearningMetricsCollector()

    collector.record("TJSP", "accuracy", 0.85)
    collector.record("TJSP", "accuracy", 0.87)
    collector.record("TJSP", "accuracy", 0.90)

    summary = collector.get_metric_summary("TJSP", "accuracy")

    assert summary["available"] is True
    assert summary["data_points"] == 3
    assert summary["statistics"]["mean"] > 0.85


def test_metrics_trend_detection() -> None:
    """Test trend detection in metrics."""

    collector = LearningMetricsCollector()

    for index in range(20):
        collector.record("TJMG", "success_rate", 0.7 + index * 0.01)

    summary = collector.get_metric_summary("TJMG", "success_rate")

    assert summary["trend"] == "improving"


def test_metrics_anomaly_detection() -> None:
    """Test anomaly detection."""

    collector = LearningMetricsCollector()

    for index in range(50):
        collector.record("TJRS", "latency", 0.5 + (index % 10) * 0.01)

    collector.record("TJRS", "latency", 5.0)

    anomalies = collector.detect_anomalies("TJRS", "latency", threshold_std=2.0)

    assert len(anomalies) > 0
    assert any(anomaly["value"] == 5.0 for anomaly in anomalies)


def test_metrics_comparison() -> None:
    """Test comparing metrics between agents."""

    collector = LearningMetricsCollector()

    for _ in range(10):
        collector.record("AgentA", "accuracy", 0.85)

    for _ in range(10):
        collector.record("AgentB", "accuracy", 0.90)

    comparison = collector.compare_agents("AgentA", "AgentB", "accuracy")

    assert comparison["comparison"]["better_performer"] == "AgentB"
    assert comparison["comparison"]["percent_difference"] > 0


def test_learning_rate_calculation() -> None:
    """Test learning rate calculation."""

    collector = LearningMetricsCollector()

    for index in range(5):
        collector.record("TJRJ", "accuracy", 0.7 + index * 0.05)
        time.sleep(0.05)

    learning_rate = collector.calculate_learning_rate("TJRJ", "accuracy", time_window_hours=1)

    assert learning_rate is not None
    assert learning_rate > 0


def test_metrics_export() -> None:
    """Test exporting metrics."""

    collector = LearningMetricsCollector()

    collector.record("TJSP", "accuracy", 0.85)
    collector.record("TJSP", "latency", 0.45)

    export = collector.export_metrics("TJSP")

    assert export["agent"] == "TJSP"
    assert "metrics" in export
    assert "accuracy" in export["metrics"]
    assert "latency" in export["metrics"]
    assert "raw_data" in export["metrics"]["accuracy"]


@pytest.mark.asyncio
async def test_training_with_multiple_agents() -> None:
    """Test training multiple agents simultaneously."""

    manager = TrainingManager()

    agents = ["TJSP", "TJMG", "TJRS"]

    for agent in agents:
        for _ in range(manager.min_feedback_for_training):
            await manager.process_feedback(
                agent_type=agent,
                task_result={"success": True, "latency": 0.5},
                user_rating=0.8,
            )

    results = []
    for agent in agents:
        results.append(await manager.train_agent(agent))

    assert all(result["status"] == "completed" for result in results)
    assert len(manager.training_states) == len(agents)


@pytest.mark.asyncio
async def test_training_history_tracking() -> None:
    """Test that training history is properly tracked."""

    manager = TrainingManager()

    for _ in range(manager.min_feedback_for_training):
        await manager.process_feedback(
            agent_type="STF",
            task_result={"success": True},
            user_rating=0.9,
        )

    await manager.train_agent("STF")

    assert len(manager.training_history) == 1
    session = manager.training_history[0]
    assert session.agent_type == "STF"
    assert session.status == "completed"
    assert session.end_time is not None


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    pytest.main([__file__, "-v"])
