"""Testes para validar execução paralela do SupervisorAgent."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pytest

from src.agents.supervisor_agent import SupervisorAgent


@pytest.mark.asyncio
async def test_parallel_execution_multiple_tribunals():
    """Valida que múltiplos tribunais são processados em paralelo."""
    supervisor = SupervisorAgent()

    # Tarefa com 3 tribunais
    result = await supervisor.process_task(
        "Verificar status do TJSP, TJMG e TJRS"
    )

    assert result["status"] == "success"
    assert result["parallel"] is True
    assert len(result["tribunals_used"]) == 3
    assert set(result["tribunals_used"]) == {"TJSP", "TJMG", "TJRS"}

    # Verifica agregação correta
    supervisor_result = result["supervisor_result"]
    assert supervisor_result["status"] == "multiple_results"
    assert supervisor_result["count"] == 3
    assert "TJSP" in supervisor_result["tribunals"]
    assert "TJMG" in supervisor_result["tribunals"]
    assert "TJRS" in supervisor_result["tribunals"]


@pytest.mark.asyncio
async def test_parallel_faster_than_sequential():
    """Prova que execução paralela é mais rápida que sequencial."""
    supervisor = SupervisorAgent()

    # Execução paralela (3 tribunais)
    start_parallel = time.perf_counter()
    result_parallel = await supervisor.process_task(
        "Status TJSP, TJMG e TJRS"
    )
    time_parallel = time.perf_counter() - start_parallel

    # Execução sequencial simulada (3 chamadas separadas)
    start_sequential = time.perf_counter()
    await supervisor.process_task("Status TJSP")
    await supervisor.process_task("Status TJMG")
    await supervisor.process_task("Status TJRS")
    time_sequential = time.perf_counter() - start_sequential

    # Paralelo deve ser significativamente mais rápido
    speedup = time_sequential / time_parallel

    print(f"\n⚡ Speedup: {speedup:.2f}x")
    print(f"   Parallel: {time_parallel:.3f}s")
    print(f"   Sequential: {time_sequential:.3f}s")

    assert speedup > 1.5, f"Speedup de {speedup:.2f}x é insuficiente"


@pytest.mark.asyncio
async def test_backward_compatibility_single_tribunal():
    """Garante que consultas single-tribunal ainda funcionam."""
    supervisor = SupervisorAgent()

    result = await supervisor.process_task("Status do TJSP")

    assert result["status"] == "success"
    assert result["tribunals_used"] == ["TJSP"]
    assert result["parallel"] is False

    # Resultado não deve estar agregado (backward compatibility)
    supervisor_result = result["supervisor_result"]
    assert supervisor_result.get("status") != "multiple_results"
    assert supervisor_result["tribunal"] == "TJSP"


@pytest.mark.asyncio
async def test_error_handling_partial_failures():
    """Valida que falhas parciais não quebram a resposta completa."""
    supervisor = SupervisorAgent()

    # Simula erro injetando tribunal inválido
    result = await supervisor.process_task(
        "Status TJSP e TRIBUNAL_INVALIDO"
    )

    # Deve retornar sucesso com os resultados válidos
    assert result["status"] == "success"
    assert "TJSP" in result["tribunals_used"]

    # Verifica que pelo menos TJSP foi processado
    supervisor_result = result["supervisor_result"]
    if supervisor_result.get("status") == "multiple_results":
        assert "TJSP" in supervisor_result["tribunals"]


@pytest.mark.asyncio
async def test_metrics_tracking_parallel_execution():
    """Valida que métricas de paralelização são rastreadas."""
    supervisor = SupervisorAgent()

    # Executa algumas tarefas paralelas
    await supervisor.process_task("Status TJSP e TJMG")
    await supervisor.process_task("Status TJRS")

    stats = supervisor.get_agent_stats()

    assert stats["total_tasks_processed"] == 2
    assert stats["parallel_tasks_count"] == 1  # Apenas a primeira
    assert len(stats["active_tribunals"]) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
