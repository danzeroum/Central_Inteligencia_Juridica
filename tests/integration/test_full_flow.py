"""Integration tests covering supervisor and tribunal agents working together."""

from __future__ import annotations

import pytest

from src.agents.supervisor_agent import SupervisorAgent


@pytest.mark.asyncio
async def test_full_flow_single_tribunal() -> None:
    supervisor = SupervisorAgent()

    result = await supervisor.process_task("Status TJSP")

    assert result["status"] in ("success", "weak_consensus")
    assert isinstance(result.get("tribunals_used"), list)
    assert len(result.get("tribunals_used", [])) >= 1
    assert "TJSP" in result.get("tribunals_used", [])
    assert "supervisor_result" in result


@pytest.mark.asyncio
async def test_full_flow_multiple_tribunals_parallel() -> None:
    supervisor = SupervisorAgent()

    result = await supervisor.process_task("Comparar jurisprudencia TJSP e TJMG")

    assert result["status"] in (
        "success",
        "success_with_consensus",
        "weak_consensus",
        "pending_human_review",
    )
    assert isinstance(result.get("tribunals_used"), list)
    assert "supervisor_result" in result


@pytest.mark.asyncio
async def test_xss_sanitization_in_task() -> None:
    """Verify that XSS payloads are sanitized during task processing."""

    supervisor = SupervisorAgent()
    result = await supervisor.process_task("Status <script>alert('xss')</script> TJSP")

    assert result["status"] in ("success", "weak_consensus")
    # The sanitizer should strip or escape the script tag
    supervisor_result = result.get("supervisor_result", {})
    result_str = str(supervisor_result)
    assert "<script>" not in result_str
    assert (
        "alert" not in result_str
        or "alert" in result_str.lower()
        and "script" not in result_str.lower()
    )


@pytest.mark.asyncio
async def test_empty_task_handling() -> None:
    """Verify graceful handling of empty or whitespace-only tasks."""

    supervisor = SupervisorAgent()
    result = await supervisor.process_task("   ")

    assert "status" in result
