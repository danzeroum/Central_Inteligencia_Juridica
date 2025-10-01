<<<<<<< HEAD
"""Continuous evaluation helpers for agent quality monitoring."""
from __future__ import annotations

from dataclasses import dataclass, field
=======
"""Continuous evaluation utilities for training flows."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
from typing import Any, Dict, List


@dataclass
<<<<<<< HEAD
class ContinuousEvaluator:
    """Collect rolling metrics for agent executions."""

    metrics: Dict[str, List[float]] = field(
        default_factory=lambda: {
            "task_success_rate": [],
            "average_confidence": [],
            "user_satisfaction": [],
            "error_rate": [],
            "response_time_p95": [],
        }
    )

    async def evaluate_agent_performance(self, agent_name: str, task_result: Dict[str, Any]) -> Dict[str, Any]:
        technical = self.evaluate_technical_quality(task_result)
        business = self.evaluate_business_value(task_result)
        improvement = self.compare_with_baseline(agent_name, task_result)
        summary = {
            "agent": agent_name,
            "technical_score": technical,
            "business_score": business,
            "improvement": improvement,
        }
        self._record("task_success_rate", float(task_result.get("success", 0)))
        self._record("average_confidence", float(task_result.get("confidence", 0)))
        return summary

    def evaluate_technical_quality(self, result: Dict[str, Any]) -> float:
        return float(result.get("technical_score", 0.8))

    def evaluate_business_value(self, result: Dict[str, Any]) -> float:
        return float(result.get("business_score", 0.7))

    def compare_with_baseline(self, agent_name: str, result: Dict[str, Any]) -> float:
        return float(result.get("improvement", 0.0))

    def _record(self, metric: str, value: float) -> None:
        if metric in self.metrics:
            self.metrics[metric].append(value)
=======
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
>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
