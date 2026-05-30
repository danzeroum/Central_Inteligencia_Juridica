"""Progressive autonomy manager integrating HITL queue."""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, Optional

from src.hitl.hitl_queue import get_hitl_queue


class ProgressiveAutonomyManager:
    """Coordinates agent autonomy with human-in-the-loop oversight."""

    def __init__(
        self,
        *,
        consensus_threshold: float = 0.6,
        default_trust_score: float = 0.5,
        history_size: int = 100,
    ) -> None:
        if not 0 <= consensus_threshold <= 1:
            raise ValueError("consensus_threshold must be between 0 and 1")
        if not 0 <= default_trust_score <= 1:
            raise ValueError("default_trust_score must be between 0 and 1")

        self.consensus_threshold = consensus_threshold
        self.default_trust_score = default_trust_score
        self.history_size = history_size
        # Faixas de trust que definem o nível de autonomia (DMN — subdecisão).
        self.trust_full_threshold = 0.8
        self.trust_supervised_threshold = 0.6
        self.agent_trust_scores: Dict[str, float] = {}
        self.action_history: Deque[Dict[str, Any]] = deque(maxlen=history_size)

    async def execute_with_autonomy(
        self, agent: str, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an action considering trust, consensus, and HITL requirements."""

        consensus = float(action.get("consensus", 1.0))
        requires_hitl = self._requires_human_review(agent, action, consensus)
        decision: Dict[str, Any] = {
            "approved": True,
            "modifications": None,
            "feedback": None,
        }

        if requires_hitl:
            decision = await self._request_human_approval(agent, action)

        approved = bool(decision.get("approved"))
        final_action = action.copy()
        modifications = decision.get("modifications") if decision else None
        if approved and isinstance(modifications, dict):
            final_action.update(modifications)

        self._record_action(
            agent,
            action,
            approved=approved,
            requires_hitl=requires_hitl,
            decision=decision,
        )

        return {
            "agent": agent,
            "action": final_action,
            "executed": approved,
            "decision": decision,
            "requires_hitl": requires_hitl,
        }

    def _requires_human_review(
        self, agent: str, action: Dict[str, Any], consensus: float
    ) -> bool:
        """Determine if human review is necessary for the given action."""

        if action.get("critical"):
            return True

        if consensus < self.consensus_threshold:
            return True

        autonomy_level = self._get_autonomy_level(agent)
        return autonomy_level == "restricted"

    def _get_autonomy_level(self, agent: str) -> str:
        """Return autonomy level string based on agent trust score."""

        trust = self.agent_trust_scores.get(agent, self.default_trust_score)
        if trust >= self.trust_full_threshold:
            return "full"
        if trust >= self.trust_supervised_threshold:
            return "supervised"
        return "restricted"

    def get_autonomy_level(self, agent: str) -> str:
        """Versão pública de :meth:`_get_autonomy_level`."""

        return self._get_autonomy_level(agent)

    def get_config(self) -> Dict[str, Any]:
        """Exporta os limiares da regra de autonomia (tabela DMN)."""

        return {
            "consensus_threshold": self.consensus_threshold,
            "trust_full_threshold": self.trust_full_threshold,
            "trust_supervised_threshold": self.trust_supervised_threshold,
            "default_trust_score": self.default_trust_score,
        }

    def update_config(
        self,
        *,
        consensus_threshold: Optional[float] = None,
        trust_full_threshold: Optional[float] = None,
        trust_supervised_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Atualiza os limiares da regra de autonomia, validando intervalos."""

        def _validate(name: str, value: float) -> float:
            if not 0 <= value <= 1:
                raise ValueError(f"{name} deve estar entre 0 e 1")
            return float(value)

        if consensus_threshold is not None:
            self.consensus_threshold = _validate(
                "consensus_threshold", consensus_threshold
            )
        if trust_full_threshold is not None:
            self.trust_full_threshold = _validate(
                "trust_full_threshold", trust_full_threshold
            )
        if trust_supervised_threshold is not None:
            self.trust_supervised_threshold = _validate(
                "trust_supervised_threshold", trust_supervised_threshold
            )
        if self.trust_supervised_threshold > self.trust_full_threshold:
            raise ValueError(
                "trust_supervised_threshold não pode exceder trust_full_threshold"
            )
        return self.get_config()

    def update_trust_score(self, agent: str, delta: float) -> float:
        """Update trust score incrementally and return the new value."""

        current = self.agent_trust_scores.get(agent, self.default_trust_score)
        new_score = min(max(current + delta, 0.0), 1.0)
        self.agent_trust_scores[agent] = new_score
        return new_score

    def _record_action(
        self,
        agent: str,
        action: Dict[str, Any],
        *,
        approved: bool,
        requires_hitl: bool,
        decision: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist action history for future trust calculations."""

        self.action_history.append(
            {
                "agent": agent,
                "action": action,
                "approved": approved,
                "requires_hitl": requires_hitl,
                "decision": decision,
            }
        )

    async def _request_human_approval(
        self, agent: str, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request human approval for the action through the HITL queue."""

        queue = get_hitl_queue()

        context = {
            "agent_name": agent,
            "autonomy_level": self._get_autonomy_level(agent),
            "trust_score": self.agent_trust_scores.get(agent, self.default_trust_score),
            "recent_actions": [
                entry
                for entry in list(self.action_history)[-5:]
                if entry["agent"] == agent
            ],
        }

        request = queue.add_request(agent=agent, action=action, context=context)
        decision = await queue.wait_for_decision(request.request_id)
        return decision


# Instância global compartilhada (mesmo padrão de get_hitl_queue).
_autonomy_manager: Optional["ProgressiveAutonomyManager"] = None


def get_autonomy_manager() -> "ProgressiveAutonomyManager":
    """Retorna a instância global do gestor de autonomia progressiva."""

    global _autonomy_manager
    if _autonomy_manager is None:
        _autonomy_manager = ProgressiveAutonomyManager()
    return _autonomy_manager


__all__ = ["ProgressiveAutonomyManager", "get_autonomy_manager"]
