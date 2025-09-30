"""Adaptive routing helper informed by training feedback."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass
class RouteStats:
    """Lightweight structure describing route performance."""

    success: int = 0
    failure: int = 0
    total_latency: float = 0.0

    def record(self, success: bool, latency: float) -> None:
        if success:
            self.success += 1
        else:
            self.failure += 1
        self.total_latency += float(latency)

    @property
    def calls(self) -> int:
        return self.success + self.failure

    @property
    def success_rate(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.success / self.calls

    @property
    def average_latency(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.total_latency / self.calls


class LearningRouter:
    """Minimal learning-aware router used in tests and demos."""

    def __init__(self) -> None:
        self._routes: Dict[Tuple[str, str], RouteStats] = defaultdict(RouteStats)

    def update_route_performance(
        self,
        request: Dict[str, Any],
        route: str,
        success: bool,
        latency: float,
    ) -> None:
        """Record execution data for a given agent/route combination."""

        agent_type = request.get("agent_type", "unknown")
        key = (agent_type, route)
        self._routes[key].record(success, latency)

    def get_route_snapshot(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Return a nested dictionary with aggregated metrics."""

        snapshot: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(dict)
        for (agent, route), stats in self._routes.items():
            snapshot[agent][route] = {
                "success_rate": stats.success_rate,
                "average_latency": stats.average_latency,
                "calls": float(stats.calls),
            }
        return snapshot


__all__ = ["LearningRouter", "RouteStats"]
