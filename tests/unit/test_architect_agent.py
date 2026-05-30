"""Unit tests for ArchitectAgent."""

from __future__ import annotations

import pytest

from src.agents.architect_agent import ArchitectAgent


@pytest.fixture
def architect() -> ArchitectAgent:
    return ArchitectAgent()


class TestReasonWithCoT:
    def test_identifies_tjsp(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Consultar jurisprudencia do TJSP")
        assert "TJSP" in result.get("identified_tribunals", [])
        assert result["confidence"] > 0

    def test_identifies_multiple_tribunals(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Comparar TJSP e TJMG")
        tribunals = result.get("identified_tribunals", [])
        assert "TJSP" in tribunals
        assert "TJMG" in tribunals
        assert result["confidence"] > 0.6

    def test_fallback_to_tjsp(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Processo qualquer")
        tribunals = result.get("identified_tribunals", [])
        assert "TJSP" in tribunals

    def test_empty_task(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("")
        assert result["confidence"] < 0.3
        assert "TJSP" in result.get("identified_tribunals", [])

    def test_stf_federal(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Consulta sobre o Supremo Tribunal Federal")
        tribunals = result.get("identified_tribunals", [])
        assert "STF" in tribunals

    def test_returns_required_fields(self, architect: ArchitectAgent) -> None:
        result = architect.reason_with_cot("Tarefa teste")
        assert "problem_analysis" in result
        assert "recommendation" in result
        assert "confidence" in result
        assert "identified_tribunals" in result
        assert "chain_of_thought" in result


class TestCreatePlan:
    def test_creates_plan(self, architect: ArchitectAgent) -> None:
        reasoning = architect.reason_with_cot("Tarefa com cache")
        plan = architect.create_plan({"description": "test"}, reasoning)
        assert "goal" in plan
        assert "architecture" in plan
        assert "components" in plan

    def test_includes_cache_component(self, architect: ArchitectAgent) -> None:
        reasoning = {"recommendation": "Sistema com cache distribuido"}
        plan = architect.create_plan({"description": "test"}, reasoning)
        assert "Caching Layer" in plan["components"]
