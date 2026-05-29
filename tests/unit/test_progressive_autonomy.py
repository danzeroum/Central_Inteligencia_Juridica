"""Unit tests for ProgressiveAutonomyManager."""

from __future__ import annotations

import pytest

from src.hitl.progressive_autonomy import ProgressiveAutonomyManager


@pytest.fixture
def manager() -> ProgressiveAutonomyManager:
    return ProgressiveAutonomyManager()


class TestAutonomyLevels:
    def test_initial_trust_score(self, manager: ProgressiveAutonomyManager) -> None:
        score = manager.get_trust_score("TestAgent")
        assert score is not None

    def test_update_trust_score(self, manager: ProgressiveAutonomyManager) -> None:
        manager.update_trust_score("TestAgent", delta=0.1)
        score = manager.get_trust_score("TestAgent")
        assert score > 0.5

    def test_negative_delta(self, manager: ProgressiveAutonomyManager) -> None:
        initial = manager.get_trust_score("TestAgent")
        manager.update_trust_score("TestAgent", delta=-0.05)
        after = manager.get_trust_score("TestAgent")
        assert after < initial

    def test_requires_human_review_with_low_consensus(self, manager: ProgressiveAutonomyManager) -> None:
        result = manager._requires_human_review(
            consensus_strength=0.3,
            action="critical_legal_decision",
        )
        assert result is True
