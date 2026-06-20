"""Testes unitários do TrainingManager — C3 (lacuna apontada na auditoria).

Cobre:
- ``_get_current_metrics`` deriva de dados reais (sem constantes fabricadas);
- ``run_ab_test`` sinaliza ``simulated`` corretamente (com/sem agent_factory).
"""

from __future__ import annotations

import asyncio

from src.training.training_manager import TrainingManager


def _agent_with_latency(latency: float):
    return type(
        "A", (), {"execute": lambda self, task: {"success": True, "latency": latency}}
    )()


def test_get_current_metrics_no_data_is_zeros() -> None:
    manager = TrainingManager()
    metrics = manager._get_current_metrics("TJSP")
    assert metrics == {
        "user_satisfaction": 0.0,
        "success_rate": 0.0,
        "feedback_volume": 0.0,
    }


def test_get_current_metrics_derived_from_feedback() -> None:
    manager = TrainingManager()
    asyncio.run(manager.process_feedback("TJSP", {"success": True}, user_rating=0.8))
    asyncio.run(manager.process_feedback("TJSP", {"success": False}, user_rating=0.4))

    metrics = manager._get_current_metrics("TJSP")
    assert metrics["feedback_volume"] == 2.0
    assert metrics["user_satisfaction"] == 0.6  # (0.8 + 0.4) / 2
    assert metrics["success_rate"] == 0.5  # 1 de 2 com sucesso


def test_run_ab_test_simulated_without_factory() -> None:
    manager = TrainingManager()
    result = asyncio.run(
        manager.run_ab_test("v1", "v2", [{"task": "t1"}, {"task": "t2"}])
    )
    assert result["simulated"] is True
    assert "winner" in result and result["winner"] in ("A", "B")


def test_run_ab_test_with_factory_not_simulated() -> None:
    manager = TrainingManager(
        agent_factory=lambda name: _agent_with_latency(0.4 if name == "v1" else 0.2)
    )
    result = asyncio.run(
        manager.run_ab_test("v1", "v2", [{"task": "t1"}, {"task": "t2"}])
    )
    assert result["simulated"] is False
    assert "winner" in result
