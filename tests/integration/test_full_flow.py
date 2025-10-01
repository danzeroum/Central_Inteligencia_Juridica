<<<<<<< HEAD
"""Integration tests covering supervisor and tribunal agents working together."""

from __future__ import annotations

from src.agents.supervisor_agent import SupervisorAgent
from src.agents.tribunal_agent import TribunalAgent


def test_complete_happy_path_flow() -> None:
    supervisor = SupervisorAgent()
    result = supervisor.process_task("Status do tribunal TJSP")

    assert result["status"] == "success"
    assert result["tribunal_used"] == "TJSP"
    assert "supervisor_result" in result
    assert result["supervisor_result"]["tribunal"] == "TJSP"
    assert result["supervisor_result"]["operation"] == "status_check"


def test_error_handling_flow() -> None:
    supervisor = SupervisorAgent()
    result = supervisor.process_task("Status <script>alert('xss')</script> TJSP")

    assert result["status"] == "success"
    sanitized_task = result["supervisor_result"]["tribunal"]
    assert "<script>" not in sanitized_task


def test_tribunal_agent_initialization() -> None:
    tribunal_agent = TribunalAgent("TJMG")
    result = tribunal_agent.execute_task("Consultar processo")

    assert result["tribunal"] == "TJMG"
    assert "operation" in result
    assert "timestamp" in result


def test_supervisor_tribunal_communication() -> None:
    supervisor = SupervisorAgent()
    tribunal_agent = TribunalAgent("TJRS")

    delegated_result = tribunal_agent.execute_task("Status geral")
    supervisor_result = supervisor.process_task("Status geral TJRS")

    assert supervisor_result["supervisor_result"]["tribunal"] == "TJRS"
    assert delegated_result["tribunal"] == "TJRS"

=======
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pytest

from src.agents.supervisor_agent import SupervisorAgent


@pytest.mark.asyncio
async def test_full_flow_single_tribunal():
    supervisor = SupervisorAgent()

    result = await supervisor.process_task("Status TJSP")

    assert result["status"] == "success"
    assert result["tribunals_used"] == ["TJSP"]
    assert result["parallel"] is False
    assert result["supervisor_result"]["tribunal"] == "TJSP"


@pytest.mark.asyncio
async def test_full_flow_multiple_tribunals_parallel():
    supervisor = SupervisorAgent()

    result = await supervisor.process_task("Status TJSP e TJMG")

    assert result["status"] == "success"
    assert result["parallel"] is True
    assert set(result["tribunals_used"]) == {"TJSP", "TJMG"}

    supervisor_result = result["supervisor_result"]
    assert supervisor_result["status"] == "multiple_results"
    assert supervisor_result["count"] == 2
    assert set(supervisor_result["tribunals"].keys()) == {"TJSP", "TJMG"}
>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
