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
