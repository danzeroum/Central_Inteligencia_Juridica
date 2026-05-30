"""Unit tests for WeightedConsensusEngine."""

from __future__ import annotations

import pytest

from src.consensus.weighted_voting import WeightedConsensusEngine


@pytest.fixture
def engine() -> WeightedConsensusEngine:
    return WeightedConsensusEngine()


class TestReachConsensus:
    def test_single_proposal_unanimous(self, engine: WeightedConsensusEngine) -> None:
        proposals = {
            "TJSP": {"confidence": 0.9, "proposal": {"result": "ok"}},
        }
        result = engine.reach_consensus(proposals, "legal_analysis")
        assert result["consensus_strength"] >= 0.8
        assert result["decision_maker"] == "TJSP"

    def test_two_proposals_high_agreement(
        self, engine: WeightedConsensusEngine
    ) -> None:
        proposals = {
            "TJSP": {"confidence": 0.85, "proposal": {"result": "similar"}},
            "TJMG": {"confidence": 0.83, "proposal": {"result": "similar"}},
        }
        result = engine.reach_consensus(proposals, "legal_analysis")
        assert result["consensus_strength"] > 0.5

    def test_empty_proposals(self, engine: WeightedConsensusEngine) -> None:
        proposals: dict = {}
        result = engine.reach_consensus(proposals, "legal_analysis")
        assert result["consensus_strength"] == 0.0

    def test_required_keys_in_result(self, engine: WeightedConsensusEngine) -> None:
        proposals = {
            "TJSP": {"confidence": 0.8, "proposal": {"result": "ok"}},
        }
        result = engine.reach_consensus(proposals, "test")
        assert "consensus_strength" in result
        assert "decision_maker" in result
        assert "winning_proposal" in result
