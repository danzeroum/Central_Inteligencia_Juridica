from __future__ import annotations

from typing import Dict


class MetricsCollector:
    """Lightweight metrics helper with in-memory state for tests."""

    _active_agents: Dict[str, bool] = {}
    _total_agents: Dict[str, int] = {}

    @classmethod
    def set_agent_active(cls, agent: str, active: bool) -> None:
        cls._active_agents[agent] = active

    @classmethod
    def set_total_agents(cls, counts: Dict[str, int]) -> None:
        cls._total_agents.update(counts)

    @classmethod
    def snapshot(cls) -> Dict[str, Dict[str, int | bool]]:
        return {
            "active_agents": dict(cls._active_agents),
            "total_agents": dict(cls._total_agents),
        }
