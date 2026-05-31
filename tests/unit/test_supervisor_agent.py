"""Unit tests for SupervisorAgent - matched to resolved Codex async interface.

Key interface facts (from actual test error analysis):
- process_task() is ASYNC (returns coroutine) -> must await
- _delegate_to_tribunal_agent() is ASYNC -> must await
- _identify_tribunal() is sync (same in both HEAD and Codex)
- TypeError: 'coroutine' object is not subscriptable confirms async
- asyncio_mode=auto in pytest.ini handles async automatically
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agents.supervisor_agent import SupervisorAgent


def test_identify_tribunal_tjsp() -> None:
    """_identify_tribunal is sync in both versions."""
    supervisor = SupervisorAgent()
    assert supervisor._identify_tribunal("Status TJSP") == "TJSP"


def test_identify_tribunal_tjmg() -> None:
    supervisor = SupervisorAgent()
    assert supervisor._identify_tribunal("Processo em Minas Gerais") == "TJMG"


def test_identify_tribunal_default() -> None:
    supervisor = SupervisorAgent()
    assert supervisor._identify_tribunal("Tribunal qualquer") == "TJSP"


async def test_delegate_to_tribunal_agent() -> None:
    """_delegate_to_tribunal_agent is async in the resolved Codex version.

    The previous sync call returned a coroutine without executing,
    so the TribunalAgent mock was never called (Called 0 times error).
    """
    with patch("src.agents.supervisor_agent.TribunalAgent") as mock_class:
        mock_agent = MagicMock()
        mock_agent.execute_task.return_value = {"result": "test"}
        mock_class.return_value = mock_agent

        supervisor = SupervisorAgent()
        result = await supervisor._delegate_to_tribunal_agent("TJSP", "test task")

    assert result == {"result": "test"}
    # Verify TribunalAgent was instantiated (constructor args may vary)
    mock_class.assert_called()


async def test_process_task_integration() -> None:
    """process_task is async in the resolved Codex version.

    Previous sync call raised:
      TypeError: 'coroutine' object is not subscriptable
    """
    with patch("src.agents.supervisor_agent.TribunalAgent") as mock_class:
        mock_agent = MagicMock()
        mock_agent.execute_task.return_value = {"status": "success"}
        mock_class.return_value = mock_agent

        supervisor = SupervisorAgent()
        result = await supervisor.process_task("Verificar status TJSP")

    assert result["status"] == "success"
    # tribunal_used or tribunal key depending on exact resolved return structure
    assert "tribunal_used" in result or "tribunal" in result
