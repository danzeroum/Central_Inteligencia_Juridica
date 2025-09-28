"""Pytest-based unit tests for TribunalAgent internals."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.tribunal_agent import TribunalAgent


def test_tjsp_status_check_internal() -> None:
    agent = TribunalAgent("TJSP")
    status = agent._check_tribunal_status()
    assert status["tribunal"] == "TJSP"
    assert status["operation"] == "status_check"
    assert status["data"]["status"] == "operacional"


def test_tjmg_status_check_internal() -> None:
    agent = TribunalAgent("TJMG")
    status = agent._check_tribunal_status()
    assert status["tribunal"] == "TJMG"
    assert status["data"]["status"] == "instabilidade"


def test_process_query_simulation_internal() -> None:
    agent = TribunalAgent("TJSP")
    result = agent._simulate_process_query()
    assert result["operation"] == "process_query"
    assert "numero_processo" in result["data"]
    assert "TJSP" in result["data"]["numero_processo"]


def test_generic_response_internal() -> None:
    agent = TribunalAgent("TJRS")
    response = agent._generic_tribunal_response()
    assert "capacidades" in response["data"]
    assert "status_check" in response["data"]["capacidades"]


def test_execute_task_status_flow() -> None:
    agent = TribunalAgent("TJSP")
    with patch.object(agent, "_check_tribunal_status", return_value={"test": "data"}) as mock_status:
        result = agent.execute_task("Status do tribunal")
        mock_status.assert_called_once()
        assert result == {"test": "data"}


def test_execute_task_process_flow() -> None:
    agent = TribunalAgent("TJMG")
    with patch.object(agent, "_simulate_process_query", return_value={"process": "data"}) as mock_process:
        result = agent.execute_task("Consulta processo 123")
        mock_process.assert_called_once()
        assert result == {"process": "data"}


if __name__ == "__main__":
    pytest.main([__file__])
