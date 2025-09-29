"""Testes emergentes que validam aprendizado contínuo via memória vetorial."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.agents.supervisor_agent import SupervisorAgent


def _wait_for_indexing(seconds: float = 2.5) -> None:
    """Helper to wait for ChromaDB background persistence."""

    time.sleep(seconds)


@pytest.fixture(scope="module")
def supervisor_with_memory() -> SupervisorAgent:
    """Cria supervisor preparado para testes com memória persistente."""

    import os

    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set. Memory learning suite skipped.")

    import httpx

    try:
        response = httpx.get("http://localhost:8000/api/v1/heartbeat", timeout=5)
        response.raise_for_status()
    except Exception:
        pytest.skip("ChromaDB heartbeat not available at http://localhost:8000.")

    supervisor = SupervisorAgent()

    if not supervisor.memory.is_available():
        pytest.skip("VectorMemory unavailable for SupervisorAgent.")

    # Limpar coleção base de testes para cenários determinísticos
    try:
        supervisor.memory.client.delete_collection("tribunal_interactions")
        supervisor.memory._initialize_connection()
    except Exception:
        pass

    return supervisor


@pytest.mark.emergent
@pytest.mark.asyncio
async def test_learning_effect_latency_reduction(supervisor_with_memory: SupervisorAgent) -> None:
    """Segunda consulta similar deve ser mais rápida e usar cache de memória."""

    start_first = time.perf_counter()
    first = await supervisor_with_memory.process_task("Qual o status do sistema do TJSP?")
    latency_first = time.perf_counter() - start_first

    assert first["status"] == "success"
    assert first["memory"]["recalled_count"] == 0
    assert first["memory"]["cache_hit"] is False

    _wait_for_indexing()

    start_second = time.perf_counter()
    second = await supervisor_with_memory.process_task("Como está o sistema de São Paulo?")
    latency_second = time.perf_counter() - start_second

    assert second["status"] == "success"
    assert second["memory"]["recalled_count"] >= 1
    assert second["memory"]["cache_hit"] is True
    assert latency_second < latency_first
    assert second["execution_time"] < first["execution_time"]


@pytest.mark.emergent
@pytest.mark.asyncio
async def test_learning_effect_context_enrichment(supervisor_with_memory: SupervisorAgent) -> None:
    """Memória deve enriquecer consultas vagas reutilizando resultado relevante."""

    first = await supervisor_with_memory.process_task("Status detalhado do TJMG")
    assert first["status"] == "success"
    assert first["tribunals_used"] == ["TJMG"]
    assert first["memory"]["cache_hit"] is False

    _wait_for_indexing()

    second = await supervisor_with_memory.process_task("Como está o sistema agora?")

    assert second["status"] == "success"
    assert second["memory"]["recalled_count"] >= 1
    assert second["memory"]["cache_hit"] is True
    assert second["tribunals_used"] == ["TJMG"]


@pytest.mark.emergent
@pytest.mark.asyncio
async def test_memory_accumulation_over_sessions(supervisor_with_memory: SupervisorAgent) -> None:
    """Recall médio deve crescer conforme mais consultas são registradas."""

    queries = [
        "Status do TJSP",
        "Status do TJMG",
        "Status do TJRS",
        "Processo TJSP 123",
        "Processo TJMG 456",
    ]

    recall_counts: List[int] = []

    for query in queries:
        response = await supervisor_with_memory.process_task(query)
        recall_counts.append(response["memory"]["recalled_count"])
        _wait_for_indexing(1.5)

    avg_early = sum(recall_counts[:2]) / 2
    avg_late = sum(recall_counts[-2:]) / 2

    assert avg_late >= avg_early


@pytest.mark.emergent
@pytest.mark.asyncio
async def test_memory_prevents_redundant_processing(supervisor_with_memory: SupervisorAgent) -> None:
    """Consultas idênticas devem virar cache hit, reduzindo execução incrementalmente."""

    query = "Status do tribunal TJSP em São Paulo"
    latencies: List[float] = []
    cache_flags: List[bool] = []

    for _ in range(3):
        start = time.perf_counter()
        result = await supervisor_with_memory.process_task(query)
        latencies.append(time.perf_counter() - start)
        cache_flags.append(result["memory"]["cache_hit"])
        _wait_for_indexing(1.5)

    assert cache_flags[0] is False
    assert cache_flags[1] is True
    assert cache_flags[2] is True
    assert latencies[2] <= latencies[0]


@pytest.mark.emergent
@pytest.mark.asyncio
async def test_recall_precision(supervisor_with_memory: SupervisorAgent) -> None:
    """Memórias recuperadas devem ser relevantes ao contexto da consulta atual."""

    await supervisor_with_memory.process_task("Status completo do TJSP")
    _wait_for_indexing(1.5)
    await supervisor_with_memory.process_task("Status completo do TJMG")
    _wait_for_indexing(1.5)
    await supervisor_with_memory.process_task("Processo TJSP 123456")
    _wait_for_indexing(1.5)

    recalled = supervisor_with_memory.memory.recall_similar("Informações sobre São Paulo", k=3)

    assert recalled
    relevant = [m for m in recalled if "TJSP" in m.get("tribunals", [])]
    precision = len(relevant) / len(recalled)

    assert precision >= 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
