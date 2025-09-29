"""Emergent behavior tests for learning via vector memory."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.agents.supervisor_agent import SupervisorAgent


@pytest.fixture(scope="module")
def supervisor() -> SupervisorAgent:
    """Provides supervisor agent with memory prerequisites validated."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not configured for memory learning test.")

    import httpx

    try:
        response = httpx.get("http://localhost:8000/api/v1/heartbeat", timeout=5)
        response.raise_for_status()
    except Exception:
        pytest.skip("ChromaDB not available for memory learning test.")

    agent = SupervisorAgent()

    if not agent.memory.is_available():
        pytest.skip("VectorMemory unavailable for SupervisorAgent.")

    return agent


@pytest.mark.emergent
@pytest.mark.asyncio
async def test_supervisor_recalls_previous_tasks(supervisor: SupervisorAgent):
    """Supervisor should recall similar tasks after first execution."""

    first_response = await supervisor.process_task("Status do TJSP")
    assert first_response["status"] == "success"
    assert first_response["memory"]["recalled_count"] == 0

    await asyncio.sleep(3)

    second_response = await supervisor.process_task("Como está o sistema de São Paulo?")
    assert second_response["status"] == "success"
    assert second_response["memory"]["recalled_count"] >= 1
    assert second_response["memory"]["recall_time"] >= 0.0

    # Validate task history records memory usage growth
    assert supervisor.task_history[-1]["recalled_memories"] >= 1
    assert supervisor.task_history[-1]["recall_time"] == second_response["memory"]["recall_time"]
