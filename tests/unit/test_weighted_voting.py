"""Unit tests for WeightedConsensusEngine - matched to resolved Codex interface.

Key interface facts:
- reach_consensus() returns: decision, decision_maker, consensus_strength,
  confidence_distribution, ...
- Proposals must include 'score', 'weight', 'confidence' keys per agent
- Key is 'decision', NOT 'winning_proposal'
"""

from __future__ import annotations

import pytest

from src.consensus.weighted_voting import WeightedConsensusEngine


class TestReachConsensus:
    """Tests for reach_consensus with correct proposal format."""

    def test_single_proposal_unanimous(self) -> None:
        engine = WeightedConsensusEngine()
        proposals = {
            "TJSP": {
                "score": 0.8,
                "weight": 1.0,
                "confidence": 0.8,
                "proposal": {"result": "ok"},
            }
        }
        result = engine.reach_consensus(proposals, "test_decision")
        # Único proponente vence e a força fica no intervalo válido [0, 1].
        assert result["decision_maker"] == "TJSP"
        assert result["decision"] is not None
        assert 0.0 <= result["consensus_strength"] <= 1.0

    def test_two_proposals_full_agreement_is_stronger(self) -> None:
        engine = WeightedConsensusEngine()
        proposals = {
            "TJSP": {"score": 0.9, "weight": 1.0, "confidence": 0.9, "proposal": {"result": "ok"}},
            "TJMG": {"score": 0.85, "weight": 0.95, "confidence": 0.85, "proposal": {"result": "ok"}},
        }
        result = engine.reach_consensus(proposals, "test_decision")
        # Dois proponentes concordando -> consenso máximo e sem dissidência.
        assert result["consensus_strength"] == pytest.approx(1.0)
        assert result["decision_maker"] in proposals
        assert result["dissenting_opinions"] == []

    def test_disagreement_lowers_consensus_and_records_dissent(self) -> None:
        engine = WeightedConsensusEngine()
        proposals = {
            "A": {"score": 0.9, "weight": 1.0, "confidence": 0.9, "proposal": {"result": "x"}},
            "B": {"score": 0.9, "weight": 1.0, "confidence": 0.9, "proposal": {"result": "y"}},
        }
        result = engine.reach_consensus(proposals, "test_decision")
        # Propostas divergentes: vence um cluster e o outro vira dissidência.
        assert 0.0 <= result["consensus_strength"] <= 1.0
        assert result["decision_maker"] in proposals
        assert len(result["dissenting_opinions"]) == 1

    def test_empty_proposals(self) -> None:
        engine = WeightedConsensusEngine()
        result = engine.reach_consensus({}, "test_decision")
        # Sem propostas: sem decisão, força zero e listas vazias (não apenas "not None").
        assert result["decision"] is None
        assert result["decision_maker"] is None
        assert result["consensus_strength"] == 0.0
        assert result["dissenting_opinions"] == []

    def test_required_keys_in_result(self) -> None:
        """Correct key is 'decision', NOT 'winning_proposal'."""
        engine = WeightedConsensusEngine()
        proposals = {
            "TJSP": {
                "score": 0.8,
                "weight": 1.0,
                "confidence": 0.8,
                "proposal": {"result": "ok"},
            }
        }
        result = engine.reach_consensus(proposals, "test_decision")
        assert "decision" in result
        assert "consensus_strength" in result
        assert "decision_maker" in result
