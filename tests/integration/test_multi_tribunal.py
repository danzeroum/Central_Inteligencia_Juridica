"""Integration tests for multi-tribunal routing in SupervisorAgent."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.agents.supervisor_agent import SupervisorAgent
from src.agents.tribunal_agent import TribunalAgent


@pytest.fixture
def supervisor_with_stubbed_delegates(monkeypatch: pytest.MonkeyPatch) -> SupervisorAgent:
    """Return a SupervisorAgent with deterministic tribunal delegates."""

    supervisor = SupervisorAgent()

    counter = {"value": 0}

    def _fake_execute(self: TribunalAgent, task: str) -> Dict[str, str]:
        counter["value"] += 1
        timestamp = (datetime(2025, 9, 30) + timedelta(seconds=counter["value"])).isoformat()
        return {
            "tribunal": self.tribunal_code,
            "operation": "status",
            "status": "success",
            "timestamp": timestamp,
            "payload": {
                "task": task,
                "delegated_to": self.tribunal_code,
            },
        }

    monkeypatch.setattr(TribunalAgent, "execute_task", _fake_execute)
    return supervisor


class TestTribunalIdentification:
    """Unit level tests for tribunal identification helpers."""

    def setup_method(self) -> None:
        self.supervisor = SupervisorAgent()

    def test_identify_single_tribunal(self) -> None:
        tribunals = self.supervisor._identify_all_tribunals("Status do TJSP")
        assert tribunals == ["TJSP"]

    def test_identify_multiple_tribunals_ordered(self) -> None:
        tribunals = self.supervisor._identify_all_tribunals(
            "Status TJRS e consulta processo STF"
        )
        assert tribunals == ["TJRS", "STF"]

    def test_identify_multiple_tribunals_varied(self) -> None:
        tribunals = self.supervisor._identify_all_tribunals(
            "Verificar TJSP, TJMG e TJRJ sobre o mesmo caso"
        )
        assert tribunals == ["TJSP", "TJMG", "TJRJ"]

    def test_identify_duplicate_tribunal_only_once(self) -> None:
        tribunals = self.supervisor._identify_all_tribunals(
            "Status do TJSP e também consulta no TJSP"
        )
        assert tribunals == ["TJSP"]

    def test_identify_tribunal_legacy_method(self) -> None:
        assert self.supervisor._identify_tribunal("Status do TJSP") == "TJSP"
        assert self.supervisor._identify_tribunal("Status TJRS e STF") in {"TJRS", "STF"}
        assert self.supervisor._identify_tribunal("Status geral") == "TJSP"


@pytest.mark.asyncio
class TestMultiTribunalRouting:
    """Integration style tests for the multi-tribunal execution flow."""

    async def test_process_single_tribunal_task_backward_compatibility(
        self, supervisor_with_stubbed_delegates: SupervisorAgent
    ) -> None:
        result = await supervisor_with_stubbed_delegates.process_task("Verificar status TJSP")

        assert result["status"] == "success"
        assert result["tribunals_used"] == ["TJSP"]
        assert result.get("multi_tribunal") is None
        assert result["tribunal_used"] == "TJSP"
        assert result["supervisor_result"]["tribunal"] == "TJSP"

    async def test_process_multi_tribunal_task_success(
        self, supervisor_with_stubbed_delegates: SupervisorAgent
    ) -> None:
        result = await supervisor_with_stubbed_delegates.process_task(
            "Status do tribunal TJRS e consulta no STF"
        )

        assert result["status"] == "success"
        assert result["multi_tribunal"] is True
        assert result["tribunals_consulted"] == ["TJRS", "STF"]

        supervisor_result = result["supervisor_result"]
        assert supervisor_result["status"] == "multiple_results"
        assert set(supervisor_result["tribunals"].keys()) == {"TJRS", "STF"}

        for tribunal_code, payload in supervisor_result["tribunals"].items():
            assert payload["tribunal"] == tribunal_code
            assert payload["operation"] == "status"
            assert payload["status"] == "success"
            assert "timestamp" in payload

    async def test_process_multi_tribunal_with_three_tribunals(
        self, supervisor_with_stubbed_delegates: SupervisorAgent
    ) -> None:
        result = await supervisor_with_stubbed_delegates.process_task(
            "Consultar TJSP, TJMG e TJRJ"
        )

        assert result["multi_tribunal"] is True
        assert result["tribunals_consulted"] == ["TJSP", "TJMG", "TJRJ"]
        assert len(result["supervisor_result"]["tribunals"]) == 3

    async def test_multi_tribunal_task_logs_decision(
        self, supervisor_with_stubbed_delegates: SupervisorAgent
    ) -> None:
        await supervisor_with_stubbed_delegates.process_task("Status TJSP e TJMG")

        decomposition_entries = supervisor_with_stubbed_delegates.ledger.get_entries(
            decision_type="MULTI_TRIBUNAL_DECOMPOSITION"
        )
        assert decomposition_entries
        assert decomposition_entries[-1]["metadata"]["tribunals"] == ["TJSP", "TJMG"]

    async def test_multi_tribunal_statistics_tracking(
        self, supervisor_with_stubbed_delegates: SupervisorAgent
    ) -> None:
        await supervisor_with_stubbed_delegates.process_task("Status TJSP")
        await supervisor_with_stubbed_delegates.process_task("Status TJRS e STF")
        await supervisor_with_stubbed_delegates.process_task("Status TJMG")
        await supervisor_with_stubbed_delegates.process_task("TJSP e TJRJ")

        stats = supervisor_with_stubbed_delegates.get_agent_stats()
        assert stats["total_tasks_processed"] == 4
        assert stats["multi_tribunal_tasks"] == 2

    async def test_multi_tribunal_task_preserves_individual_timestamps(
        self, supervisor_with_stubbed_delegates: SupervisorAgent
    ) -> None:
        result = await supervisor_with_stubbed_delegates.process_task("Status TJSP e TJMG")

        timestamps = [
            payload["timestamp"]
            for payload in result["supervisor_result"]["tribunals"].values()
        ]
        assert len(timestamps) == 2
        assert all("T" in ts for ts in timestamps)
        assert len({ts for ts in timestamps}) == len(timestamps)
