"""Continuous evaluation utilities for training flows."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class EvaluationRecord:
    """A single evaluation record."""

    agent_type: str
    metrics: Dict[str, float]
    timestamp: datetime
    context: Dict[str, Any]


class ContinuousEvaluator:
    """Collects lightweight evaluation metrics for agents."""

    def __init__(self) -> None:
        self._history: Dict[str, List[EvaluationRecord]] = defaultdict(list)

    async def evaluate(
        self, agent_type: str, metrics: Dict[str, float], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Persist evaluation metrics and return rolling aggregates."""

        await asyncio.sleep(0)

        record = EvaluationRecord(
            agent_type=agent_type,
            metrics=dict(metrics),
            timestamp=datetime.now(timezone.utc),
            context=dict(context),
        )
        self._history[agent_type].append(record)

        aggregates = self._aggregate(agent_type)
        return {
            "agent_type": agent_type,
            "timestamp": record.timestamp.isoformat(),
            "metrics": metrics,
            "aggregates": aggregates,
        }

    def _aggregate(self, agent_type: str) -> Dict[str, float]:
        history = self._history.get(agent_type, [])
        if not history:
            return {}

        totals: Dict[str, float] = defaultdict(float)
        for record in history[-50:]:
            for key, value in record.metrics.items():
                totals[key] += float(value)

        count = float(min(len(history), 50)) or 1.0
        return {key: value / count for key, value in totals.items()}

    def history(self, agent_type: str) -> List[Dict[str, Any]]:
        """Return the raw evaluation history for an agent."""

        return [
            {
                "timestamp": record.timestamp.isoformat(),
                "metrics": dict(record.metrics),
                "context": dict(record.context),
            }
            for record in self._history.get(agent_type, [])
        ]


__all__ = ["ContinuousEvaluator", "EvaluationRecord"]
