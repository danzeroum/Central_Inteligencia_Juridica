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
        score = manager.agent_trust_scores.get("TestAgent", manager.default_trust_score)
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
        result = manager._requires_human_review("TestAgent", {"critical": False}, 0.3)
        assert result is True

    def test_update_trust_score_clamps_upper_bound(self) -> None:
        """Incrementos não podem ultrapassar 1.0."""
        manager = ProgressiveAutonomyManager()
        manager.update_trust_score("TestAgent", 0.4)  # 0.5 -> 0.9
        assert manager.update_trust_score("TestAgent", 0.5) == 1.0  # clamp


class TestRequiresHumanReview:
    """Cobre as três regras de '_requires_human_review' (tabela DMN)."""

    def test_critical_action_always_reviews_even_with_full_consensus(self) -> None:
        """Regra #1: ação crítica força revisão mesmo com consenso 1.0."""
        manager = ProgressiveAutonomyManager()
        manager.update_trust_score("AgenteConfiavel", 0.45)  # vira "full" (0.95)
        assert (
            manager._requires_human_review("AgenteConfiavel", {"critical": True}, 1.0)
            is True
        )

    @pytest.mark.parametrize(
        "consensus, expected",
        [
            (0.59, True),  # abaixo do limiar 0.60 -> revisa
            (0.60, False),  # no limiar (>=) com agente supervisionado -> autônomo
            (0.95, False),
        ],
    )
    def test_consensus_threshold_boundary(self, consensus, expected) -> None:
        manager = ProgressiveAutonomyManager()
        manager.update_trust_score("AgenteSup", 0.15)  # 0.5 -> 0.65 = "supervised"
        assert (
            manager._requires_human_review("AgenteSup", {"critical": False}, consensus)
            is expected
        )

    def test_restricted_agent_reviews_despite_high_consensus(self) -> None:
        """Regra #3: agente restrito (trust baixo) sempre revisa."""
        manager = ProgressiveAutonomyManager()
        manager.update_trust_score("AgenteRestrito", -0.2)  # 0.5 -> 0.3 = "restricted"
        assert (
            manager._requires_human_review("AgenteRestrito", {"critical": False}, 1.0)
            is True
        )


class TestAutonomyLevelTransitions:
    """get_autonomy_level deve mudar conforme o trust cruza os limiares."""

    @pytest.mark.parametrize(
        "trust, level",
        [
            (0.95, "full"),
            (0.80, "full"),
            (0.79, "supervised"),
            (0.60, "supervised"),
            (0.59, "restricted"),
            (0.0, "restricted"),
        ],
    )
    def test_levels(self, trust, level) -> None:
        manager = ProgressiveAutonomyManager()
        manager.agent_trust_scores["A"] = trust
        assert manager.get_autonomy_level("A") == level


class TestConfigValidation:
    """get_config/update_config — limiares editáveis com validação."""

    def test_update_config_roundtrip(self) -> None:
        manager = ProgressiveAutonomyManager()
        cfg = manager.update_config(consensus_threshold=0.7)
        assert cfg["consensus_threshold"] == 0.7
        assert manager.get_config()["consensus_threshold"] == 0.7

    @pytest.mark.parametrize("value", [-0.1, 1.5])
    def test_update_config_rejects_out_of_range(self, value) -> None:
        manager = ProgressiveAutonomyManager()
        with pytest.raises(ValueError):
            manager.update_config(consensus_threshold=value)

    def test_update_config_rejects_inverted_trust_bands(self) -> None:
        manager = ProgressiveAutonomyManager()
        with pytest.raises(ValueError):
            manager.update_config(
                trust_supervised_threshold=0.9, trust_full_threshold=0.5
            )
