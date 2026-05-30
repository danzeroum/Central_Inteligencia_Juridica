"""Pytest-based unit tests for SupervisorAgent internals."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agents.supervisor_agent import SupervisorAgent


def test_identify_tribunal_tjsp() -> None:
    supervisor = SupervisorAgent()
    assert supervisor._identify_tribunal("Status TJSP") == "TJSP"


def test_identify_tribunal_tjmg() -> None:
    supervisor = SupervisorAgent()
    assert supervisor._identify_tribunal("Processo em Minas Gerais") == "TJMG"


def test_identify_tribunal_default() -> None:
    supervisor = SupervisorAgent()
    assert supervisor._identify_tribunal("Tribunal qualquer") == "TJSP"


@patch("src.agents.supervisor_agent.TribunalAgent")
def test_delegate_to_tribunal_agent(mock_agent_class: MagicMock) -> None:
    supervisor = SupervisorAgent()
    mock_agent = MagicMock()
    mock_agent.execute_task.return_value = {"result": "test"}
    mock_agent_class.return_value = mock_agent

    result = supervisor._delegate_to_tribunal_agent("TJSP", "test task")

    mock_agent_class.assert_called_once_with(
        tribunal_code="TJSP", ledger=supervisor.ledger
    )
    mock_agent.execute_task.assert_called_once_with("test task")
    assert result == {"result": "test"}


@patch("src.agents.supervisor_agent.TribunalAgent")
def test_process_task_integration(mock_agent_class: MagicMock) -> None:
    supervisor = SupervisorAgent()
    mock_agent = MagicMock()
    mock_agent.execute_task.return_value = {"status": "success"}
    mock_agent_class.return_value = mock_agent

    result = supervisor.process_task("Verificar status TJSP")

    assert result["status"] == "success"
    assert result["tribunal_used"] == "TJSP"
    mock_agent.execute_task.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
