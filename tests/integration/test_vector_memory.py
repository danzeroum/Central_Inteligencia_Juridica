"""Integration tests for VectorMemory system."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pytest

from src.memory.vector_memory import VectorMemory


@pytest.fixture(scope="module", autouse=True)
def check_prerequisites():
    """Verifica pré-requisitos antes de rodar testes."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set. Cannot test embeddings.")

    import httpx

    try:
        response = httpx.get("http://localhost:8000/api/v1/heartbeat", timeout=5)
        response.raise_for_status()
    except Exception:
        pytest.skip(
            "ChromaDB not running. Start with: docker-compose up -d chromadb"
        )


@pytest.fixture
def memory_system():
    """Fornece instância do VectorMemory para testes."""
    memory = VectorMemory(collection_name="test_interactions")

    if not memory.is_available():
        pytest.skip("VectorMemory unavailable. Check chromadb installation or service.")

    if memory.is_available():
        try:
            memory.client.delete_collection("test_interactions")
        except Exception:
            pass
        memory._initialize_connection()

    yield memory


@pytest.mark.integration
def test_memory_connection(memory_system: VectorMemory):
    """Valida conexão com ChromaDB."""

    assert memory_system.is_available()
    assert memory_system.client is not None
    assert memory_system.collection is not None


@pytest.mark.integration
def test_remember_and_recall_cycle(memory_system: VectorMemory):
    """Teste completo: armazenar e recuperar memória."""

    task = "Qual o status do sistema do TJSP?"
    result = {"tribunal": "TJSP", "status": "operacional"}
    metadata = {
        "tribunals": ["TJSP"],
        "intent_operacao": "status_check",
        "confidence": 0.95,
    }

    success = memory_system.remember(task, result, metadata)
    assert success is True

    time.sleep(3)

    recalled = memory_system.recall_similar(
        "Como está funcionando São Paulo?",
        k=1,
    )

    assert len(recalled) >= 1
    assert recalled[0]["tribunals"] == ["TJSP"]
    assert recalled[0]["intent_operacao"] == "status_check"
    assert "similarity_score" in recalled[0]
    assert recalled[0]["similarity_score"] > 0.7
    assert "result_snapshot" in recalled[0]

    snapshot = recalled[0]["result_snapshot"]
    restored = json.loads(snapshot)
    assert restored["tribunal"] == "TJSP"


@pytest.mark.integration
def test_recall_multiple_memories(memory_system: VectorMemory):
    """Valida recall de múltiplas memórias ordenadas por similaridade."""

    memories = [
        ("Status do TJSP", {"status": "ok"}, {"tribunals": ["TJSP"]}),
        ("Status do TJMG", {"status": "ok"}, {"tribunals": ["TJMG"]}),
        ("Processo no TJSP", {"processo": "123"}, {"tribunals": ["TJSP"]}),
    ]

    for task, result, metadata in memories:
        memory_system.remember(task, result, metadata)

    time.sleep(3)

    recalled = memory_system.recall_similar("Status TJSP", k=3)

    assert len(recalled) >= 2
    assert recalled[0]["similarity_score"] >= recalled[1]["similarity_score"]


@pytest.mark.integration
def test_recall_empty_on_no_match(memory_system: VectorMemory):
    """Valida que queries muito diferentes não retornam resultados."""

    memory_system.remember(
        "Status do TJSP",
        {"status": "ok"},
        {"tribunals": ["TJSP"]},
    )

    time.sleep(3)

    recalled = memory_system.recall_similar(
        "Qual a previsão do tempo para amanhã?",
        k=1,
        min_similarity=0.7,
    )

    assert len(recalled) == 0


@pytest.mark.integration
def test_recall_performance(memory_system: VectorMemory):
    """Valida latência do recall."""

    for i in range(5):
        memory_system.remember(
            f"Status do tribunal {i}",
            {"status": "ok"},
            {"tribunals": [f"TJ{i}"]},
        )

    time.sleep(3)

    start = time.perf_counter()
    recalled = memory_system.recall_similar("Status tribunal", k=3)
    elapsed = time.perf_counter() - start

    assert recalled
    assert elapsed < 0.3, f"Recall too slow: {elapsed:.3f}s"


@pytest.mark.integration
def test_memory_persistence(memory_system: VectorMemory):
    """Valida que memórias persistem (volume Docker)."""

    task_id = f"test_persistence_{time.time()}"
    memory_system.remember(
        task_id,
        {"test": True},
        {"test_id": task_id},
    )

    time.sleep(3)

    new_memory = VectorMemory(collection_name="test_interactions")

    recalled = new_memory.recall_similar(task_id, k=1)
    assert len(recalled) >= 1
    assert recalled[0].get("test_id") == task_id
    assert "result_snapshot" in recalled[0]


@pytest.mark.integration
def test_memory_stats(memory_system: VectorMemory):
    """Valida estatísticas do sistema de memória."""

    for i in range(3):
        memory_system.remember(
            f"Task {i}",
            {"idx": i},
            {"test": True},
        )

    time.sleep(3)

    stats = memory_system.get_stats()

    assert stats["status"] == "healthy"
    assert stats["total_memories"] >= 3
    assert "collection" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
