"""Unit tests for ProgressiveAutonomyManager - matched to resolved Codex interface.

Key interface facts (from actual test error analysis):
- No get_trust_score() method exists; access agent_trust_scores dict directly
- update_trust_score(agent, delta) -> float (returns new score, clamped 0-1)
- _requires_human_review(agent, action, consensus) uses positional "consensus"
  NOT keyword "consensus_strength"
- default_trust_score attribute holds the default (0.5)
- agent_trust_scores dict holds per-agent scores
"""

from __future__ import annotations

import pytest

from src.hitl.progressive_autonomy import ProgressiveAutonomyManager


class TestAutonomyLevels:
    """Tests for trust score management and human review determination."""

    def test_initial_trust_score(self) -> None:
        """No explicit getter; check dict directly with default fallback."""
        manager = ProgressiveAutonomyManager()
        score = manager.agent_trust_scores.get(
            "TestAgent", manager.default_trust_score
        )
        assert score == 0.5

    def test_update_trust_score(self) -> None:
        """update_trust_score(agent, delta) returns new clamped score."""
        manager = ProgressiveAutonomyManager()
        new_score = manager.update_trust_score("TestAgent", 0.1)
        assert new_score == 0.6
        assert manager.agent_trust_scores["TestAgent"] == 0.6

    def test_negative_delta(self) -> None:
        """Negative delta decreases trust, clamped to 0.0."""
        manager = ProgressiveAutonomyManager()
        initial = manager.agent_trust_scores.get(
            "TestAgent", manager.default_trust_score
        )
        assert initial == 0.5
        new_score = manager.update_trust_score("TestAgent", -0.3)
        assert new_score == 0.2

    def test_requires_human_review_with_low_consensus(self) -> None:
        """Low consensus (0.3) < threshold (0.6) triggers human review.

        Signature: _requires_human_review(agent, action, consensus) - positional args.
        """
        manager = ProgressiveAutonomyManager()
        # consensus is POSITIONAL (3rd arg), not keyword "consensus_strength"
        result = manager._requires_human_review(
            "TestAgent", {"critical": False}, 0.3
        )
        assert result is True

