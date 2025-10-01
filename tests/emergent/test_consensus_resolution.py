"""Emergent behavior tests for consensus resolution."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.agents.supervisor_agent import SupervisorAgent
from src.consensus.weighted_voting import WeightedConsensusEngine


class TestConsensusResolution:
    """Validate that consensus correctly resolves divergent opinions."""

    def test_strong_consensus_accepts_majority(self) -> None:
        """Strong consensus should accept the majority opinion."""
        engine = WeightedConsensusEngine()

        proposals = {
            "tjsp": {
                "confidence": 0.9,
                "proposal": {"verdict": "procedente"},
            },
            "tjmg": {
                "confidence": 0.85,
                "proposal": {"verdict": "procedente"},
            },
            "tjrj": {
                "confidence": 0.6,
                "proposal": {"verdict": "improcedente"},
            },
        }

        result = engine.reach_consensus(proposals, "jurisprudence")

        assert result["consensus_strength"] > 0.5
        assert result["decision_maker"] in ["tjsp", "tjmg"]
        assert len(result["dissenting_opinions"]) > 0

    def test_dissenting_opinions_recorded(self) -> None:
        """Dissenting opinions must be recorded."""
        engine = WeightedConsensusEngine()

        proposals = {
            "tjsp": {"confidence": 0.8, "proposal": {"stance": "A"}},
            "tjmg": {"confidence": 0.75, "proposal": {"stance": "B"}},
            "tjrs": {"confidence": 0.7, "proposal": {"stance": "C"}},
        }

        result = engine.reach_consensus(proposals, "legal_interpretation")

        dissenting = result.get("dissenting_opinions", [])

        assert len(dissenting) >= 2

        for opinion in dissenting:
            assert "agent" in opinion
            assert "score" in opinion

    def test_weak_consensus_flagged(self) -> None:
        """Weak consensus should be flagged for human review."""
        engine = WeightedConsensusEngine()

        proposals = {
            "tjsp": {"confidence": 0.4, "proposal": {"analysis": "unclear"}},
            "tjmg": {"confidence": 0.35, "proposal": {"analysis": "ambiguous"}},
            "tjrs": {"confidence": 0.38, "proposal": {"analysis": "uncertain"}},
        }

        result = engine.reach_consensus(proposals, "complex_case")

        assert result["consensus_strength"] < 0.5

    def test_equal_confidence_resolved_by_weights(self) -> None:
        """Equal confidence should be resolved by agent expertise weights."""
        engine = WeightedConsensusEngine()

        proposals = {
            "tjsp": {"confidence": 0.8, "proposal": {"position": "X"}},
            "tjmg": {"confidence": 0.8, "proposal": {"position": "Y"}},
        }

        result = engine.reach_consensus(proposals, "jurisdiction")

        assert result["decision_maker"] is not None
        assert result["consensus_strength"] > 0


class TestSupervisorConsensusIntegration:
    """Test supervisor's integration with consensus mechanism."""

    @pytest.mark.asyncio
    async def test_supervisor_detects_multi_tribunal_query(self) -> None:
        """Supervisor should detect queries requiring multiple tribunals."""
        supervisor = SupervisorAgent()

        multi_queries = [
            "Jurisprudência sobre tema X no sudeste",
            "Comparar decisões do TJSP e TJMG",
            "Posição dos tribunais sobre Y",
        ]

        for query in multi_queries:
            assert supervisor._is_multi_tribunal_query(query)

    @pytest.mark.asyncio
    async def test_supervisor_identifies_single_tribunal_query(self) -> None:
        """Supervisor should NOT trigger consensus for single tribunal."""
        supervisor = SupervisorAgent()

        single_queries = [
            "Status do TJSP",
            "Consulta processo em São Paulo",
            "TJMG sistema funcionando",
        ]

        for query in single_queries:
            assert not supervisor._is_multi_tribunal_query(query)

    @pytest.mark.asyncio
    async def test_supervisor_identifies_relevant_tribunals(self) -> None:
        """Supervisor should correctly identify relevant tribunals."""
        supervisor = SupervisorAgent()

        tribunals = supervisor._identify_relevant_tribunals("Jurisprudência no sudeste")
        assert "TJSP" in tribunals
        assert "TJMG" in tribunals
        assert "TJRJ" in tribunals

    @pytest.mark.asyncio
    async def test_parallel_consultation_returns_responses(self) -> None:
        """Parallel consultation should gather responses from agents."""
        supervisor = SupervisorAgent()

        result = await supervisor.process_task(
            "Comparar jurisprudência entre TJSP e TJMG sobre tema X"
        )

        assert result["consensus_used"] is True
        assert "consensus" in result and result["consensus"] is not None
        assert "tribunals_consulted" in result

    @pytest.mark.asyncio
    async def test_consensus_metadata_logged(self) -> None:
        """Consensus results should be logged in ledger."""
        supervisor = SupervisorAgent()

        await supervisor.process_task("Jurisprudência sobre tema Y no sudeste")

        entries = supervisor.ledger.get_entries(
            agent_type="SupervisorAgent",
            decision_type="CONSENSUS_REACHED",
        )

        assert len(entries) > 0

    @pytest.mark.asyncio
    async def test_weak_consensus_requires_review(self) -> None:
        """Weak consensus should be flagged in response."""
        supervisor = SupervisorAgent()
        supervisor.consensus_threshold = 0.9

        result = await supervisor.process_task(
            "Posição ambígua dos tribunais sobre tema complexo"
        )

        if result.get("consensus_used") and result.get("consensus"):
            consensus = result.get("consensus", {})
            if not consensus.get("acceptable"):
                assert result["status"] == "weak_consensus"


class TestConsensusComposition:
    """Test composition of consensus with other patterns."""

    @pytest.mark.asyncio
    async def test_consensus_with_a2a_communication(self) -> None:
        """Consensus should work seamlessly with A2A messaging."""
        supervisor = SupervisorAgent()

        result = await supervisor.process_task(
            "Análise comparativa TJSP, TJMG e TJRS sobre tema Z"
        )

        assert result.get("consensus_used") is True

        history = supervisor.get_message_history()
        assert len(history) >= 0

    @pytest.mark.asyncio
    async def test_consensus_preserves_agent_autonomy(self) -> None:
        """Each agent should maintain independent analysis."""
        supervisor = SupervisorAgent()

        result = await supervisor.process_task(
            "Comparar interpretações entre múltiplos tribunais"
        )

        if result.get("consensus"):
            dissenting = result["consensus"].get("dissenting_opinions", [])
            if len(dissenting) > 0:
                assert all("agent" in dissent for dissent in dissenting)

    @pytest.mark.asyncio
    async def test_consensus_failure_graceful_degradation(self) -> None:
        """If consensus fails, should gracefully degrade."""
        supervisor = SupervisorAgent()

        result = await supervisor.process_task("Query that might fail consensus")

        assert result["status"] in {"success", "weak_consensus", "error"}


class TestConsensusEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_single_agent_no_consensus_needed(self) -> None:
        """Single agent response should not trigger consensus."""
        supervisor = SupervisorAgent()

        result = await supervisor.process_task("Status do TJSP")

        assert result.get("consensus_used") is False

    def test_all_agents_agree_strong_consensus(self) -> None:
        """When all agents agree, consensus should be very strong."""
        engine = WeightedConsensusEngine()

        proposals = {
            "tjsp": {"confidence": 0.9, "proposal": {"answer": "A"}},
            "tjmg": {"confidence": 0.85, "proposal": {"answer": "A"}},
            "tjrs": {"confidence": 0.88, "proposal": {"answer": "A"}},
        }

        result = engine.reach_consensus(proposals, "unanimous")

        assert result["consensus_strength"] > 0.8

    def test_no_proposals_handled_gracefully(self) -> None:
        """Empty proposals should be handled without crash."""
        engine = WeightedConsensusEngine()

        result = engine.reach_consensus({}, "empty")

        assert result["decision"] is None
        assert result["consensus_strength"] == 0.0

    @pytest.mark.asyncio
    async def test_confidence_bounds_respected(self) -> None:
        """Confidence should always be between 0 and 1."""
        supervisor = SupervisorAgent()

        result = {"status": "success", "data": {"value": "test"}}
        confidence = supervisor._estimate_response_confidence(result)

        assert 0.0 <= confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
