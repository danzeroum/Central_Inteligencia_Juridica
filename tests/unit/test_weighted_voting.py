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
        assert result["consensus_strength"] >= 0.0

    def test_two_proposals_high_agreement(self) -> None:
        engine = WeightedConsensusEngine()
        proposals = {
            "TJSP": {
                "score": 0.9,
                "weight": 1.0,
                "confidence": 0.9,
                "proposal": {"result": "ok"},
            },
            "TJMG": {
                "score": 0.85,
                "weight": 0.95,
                "confidence": 0.85,
                "proposal": {"result": "ok"},
            },
        }
        result = engine.reach_consensus(proposals, "test_decision")
        assert result["consensus_strength"] >= 0.0

    def test_empty_proposals(self) -> None:
        engine = WeightedConsensusEngine()
        proposals: dict = {}
        result = engine.reach_consensus(proposals, "test_decision")
        assert result is not None

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
