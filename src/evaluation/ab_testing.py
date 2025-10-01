<<<<<<< HEAD
"""Lightweight agent A/B testing utilities."""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass
class AgentABTestingFramework:
    """Execute simple A/B comparisons between agent implementations."""

    ledger_path: Path = Path(".buildtoflip/ledger/ab_tests.jsonl")

    async def run_ab_test(
        self,
        agent_a: Any,
        agent_b: Any,
        test_cases: Iterable[Dict[str, Any]],
        metrics: List[str],
    ) -> Dict[str, Any]:
        results = {"A": [], "B": []}
        for case in test_cases:
            order = ["A", "B"]
            random.shuffle(order)
            outputs = {}
            for variant in order:
                agent = agent_a if variant == "A" else agent_b
                if hasattr(agent, "execute"):
                    outputs[variant] = await agent.execute(case)
                else:
                    outputs[variant] = {"success": True}
            for variant, output in outputs.items():
                results[variant].append(self._score_output(output, metrics))
        summary = self._summarise_results(results)
        self._log_experiment(summary)
        return summary

    def _score_output(self, output: Dict[str, Any], metrics: List[str]) -> float:
        score_components = []
        for metric in metrics:
            score_components.append(float(output.get(metric, 1.0)))
        return sum(score_components) / max(len(score_components), 1)

    def _summarise_results(self, results: Dict[str, List[float]]) -> Dict[str, Any]:
        avg_a = statistics.fmean(results["A"]) if results["A"] else 0.0
        avg_b = statistics.fmean(results["B"]) if results["B"] else 0.0
        winner = "A" if avg_a >= avg_b else "B"
        diff = abs(avg_a - avg_b)
        significance = min(1.0, diff)
        return {"winner": winner, "scores": {"A": avg_a, "B": avg_b}, "statistical_significance": significance}

    def _log_experiment(self, summary: Dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **summary}
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{payload}\n")
=======
"""Simple A/B testing utilities for training workflows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Protocol


class ExecutableAgent(Protocol):
    """Protocol representing the minimal agent interface for testing."""

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task synchronously and return a result payload."""


@dataclass
class ABTestResult:
    """Stores the aggregated result of an A/B experiment."""

    winner: str
    scores: Dict[str, float]
    statistical_significance: float
    samples: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "winner": self.winner,
            "scores": self.scores,
            "statistical_significance": self.statistical_significance,
            "samples": self.samples,
        }


class AgentABTestingFramework:
    """Lightweight framework used to compare two agent variants."""

    def __init__(self) -> None:
        self._history: List[ABTestResult] = []

    async def run_ab_test(
        self,
        *,
        agent_a: ExecutableAgent,
        agent_b: ExecutableAgent,
        test_cases: Iterable[Dict[str, Any]],
        metrics: List[str],
    ) -> Dict[str, Any]:
        """Run a deterministic A/B test between two agents."""

        cases = list(test_cases)
        if not cases:
            raise ValueError("test_cases must contain at least one case")

        await asyncio.sleep(0)

        scores = {"A": [], "B": []}

        for case in cases:
            result_a = agent_a.execute(case)
            result_b = agent_b.execute(case)

            scores["A"].append(self._score_result(result_a, metrics))
            scores["B"].append(self._score_result(result_b, metrics))

        aggregates = {
            "A": mean(scores["A"]),
            "B": mean(scores["B"]),
        }

        winner = "A" if aggregates["A"] >= aggregates["B"] else "B"

        significance = self._calculate_significance(aggregates["A"], aggregates["B"], len(cases))

        result = ABTestResult(
            winner=winner,
            scores=aggregates,
            statistical_significance=significance,
            samples=len(cases),
        )
        self._history.append(result)
        return result.to_dict()

    @staticmethod
    def _score_result(result: Dict[str, Any], metrics: List[str]) -> float:
        success_weight = 1.0 if result.get("success", False) else 0.0
        latency = result.get("latency", 1.0)
        latency_bonus = 1.0 / (latency + 1e-6)

        score = success_weight + latency_bonus

        if "accuracy" in metrics and "accuracy" in result:
            score += result["accuracy"]
        if "quality" in metrics and "quality" in result:
            score += result["quality"]

        return score

    @staticmethod
    def _calculate_significance(score_a: float, score_b: float, samples: int) -> float:
        diff = abs(score_a - score_b)
        base = min(0.99, 0.5 + diff)
        adjustment = min(0.49, diff * (samples / 10))
        return round(min(0.99, base + adjustment), 4)

    def history(self) -> List[Dict[str, Any]]:
        """Return historical A/B experiment results."""

        return [result.to_dict() for result in self._history]


__all__ = ["AgentABTestingFramework", "ABTestResult"]
>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
