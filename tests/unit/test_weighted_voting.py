"""Unit tests for WeightedConsensusEngine - matched to resolved Codex interface.

Key interface fact (from actual test error analysis):
- reach_consensus() returns dict with key "decision" (NOT "winning_proposal")
- Also returns: consensus_strength, decision_maker, confidence_distribution, ...
"""

from __future__ import annotations

import pytest

from src.consensus.weighted_voting import WeightedConsensusEngine


class TestReachConsensus:
    """Tests for reach_consensus with correct result key names."""

    def test_single_proposal_unanimous(self) -> None:
        engine = WeightedConsensusEngine()
        proposals = {"TJSP": {"proposal": {"result": "ok"}, "score": 0.8}}
        result = engine.reach_consensus(proposals, "test_decision")
        assert result["consensus_strength"] >= 0.7

    def test_two_proposals_high_agreement(self) -> None:
        engine = WeightedConsensusEngine()
        proposals = {
            "TJSP": {"proposal": {"result": "ok"}, "score": 0.9},
            "TJMG": {"proposal": {"result": "ok"}, "score": 0.85},
        }
        result = engine.reach_consensus(proposals, "test_decision")
        assert result["consensus_strength"] >= 0.5

    def test_empty_proposals(self) -> None:
        engine = WeightedConsensusEngine()
        proposals: dict = {}
        result = engine.reach_consensus(proposals, "test_decision")
        assert result is not None

    def test_required_keys_in_result(self) -> None:
        """Correct key is decision, NOT winning_proposal."""
        engine = WeightedConsensusEngine()
        proposals = {"TJSP": {"proposal": {"result": "ok"}, "score": 0.8}}
        result = engine.reach_consensus(proposals, "test_decision")
        assert "decision" in result
        assert "consensus_strength" in result
        assert "decision_maker" in result

