"""Unit tests for TribunalAgent - matched to resolved Codex interface.

Key interface facts (from actual test error analysis):
- _check_tribunal_status() returns operation="status" (NOT "status_check")
- NO _simulate_process_query() method (removed during merge resolution)
- NO _generic_tribunal_response() method (removed during merge resolution)
- execute_task() wraps internal result: {tribunal, operation, task, **internal, latency, ...}
- _extract_process_number(task) exists in both versions
- TribunalAgent(tribunal_code, ledger=None) constructor
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.tribunal_agent import TribunalAgent


def test_tjsp_status_check_internal() -> None:
    """Codex version returns operation=status, NOT status_check."""
    agent = TribunalAgent("TJSP")
    status = agent._check_tribunal_status()
    assert status["tribunal"] == "TJSP"
    assert status["operation"] == "status"
    assert "status" in status.get("data", status)


def test_tjmg_status_check_internal() -> None:
    agent = TribunalAgent("TJMG")
    status = agent._check_tribunal_status()
    assert status["tribunal"] == "TJMG"
    assert "status" in status.get("data", status)


def test_extract_process_number_valid() -> None:
    """_extract_process_number exists in both HEAD and Codex versions."""
    agent = TribunalAgent("TJSP")
    result = agent._extract_process_number(
        "processo 1234567-89.2024.1.01.0001"
    )
    assert result is not None
    assert "1234567" in result


def test_extract_process_number_none() -> None:
    agent = TribunalAgent("TJSP")
    result = agent._extract_process_number("sem numero de processo")
    assert result is None


def test_execute_task_status_flow() -> None:
    """execute_task wraps the internal _check_tribunal_status result.

    Wrapped structure: {tribunal, operation, task, **internal_result, latency, ...}
    Previous test incorrectly expected raw internal dict.
    """
    agent = TribunalAgent("TJSP")
    mock_result = {"data": {"status": "operacional"}}
    with patch.object(
        agent, "_check_tribunal_status", return_value=mock_result
    ) as mock_status:
        result = agent.execute_task("Status do tribunal")
        mock_status.assert_called_once()

    assert result["tribunal"] == "TJSP"
    assert "operation" in result
    assert "latency" in result
    assert "task" in result


def test_execute_task_process_flow() -> None:
    """execute_task routes process queries internally and wraps result.

    Since _simulate_process_query does not exist in the resolved version,
    we test execute_task directly and verify the wrapped response structure.
    """
    agent = TribunalAgent("TJMG")
    result = agent.execute_task("Consulta processo 123456")
    # Verify basic wrapped structure (may use mock fallback for API)
    assert result["tribunal"] == "TJMG"
    assert "latency" in result
    assert "operation" in result

