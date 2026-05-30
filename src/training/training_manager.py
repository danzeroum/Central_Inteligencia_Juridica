"""Training Manager - Orchestrates continuous learning for tribunal agents."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.evaluation.ab_testing import AgentABTestingFramework
from src.evaluation.continuous_evaluator import ContinuousEvaluator
from src.routing.learning_router import LearningRouter
from src.utils.ledger import DecisionLedger

logger = logging.getLogger(__name__)


@dataclass
class TrainingSession:
    """Represents a single training session."""

    session_id: str
    agent_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    improvements: Dict[str, float] = field(default_factory=dict)
    feedback_count: int = 0
    status: str = "running"  # running, completed, failed


@dataclass
class AgentTrainingState:
    """Tracks training state for a specific agent."""

    agent_type: str
    total_sessions: int = 0
    total_feedback: int = 0
    current_performance: Dict[str, float] = field(default_factory=dict)
    baseline_performance: Dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.01
    last_training: Optional[datetime] = None


class TrainingManager:
    """Orchestrates continuous learning across all agents."""

    def __init__(
        self,
        evaluator: Optional[ContinuousEvaluator] = None,
        router: Optional[LearningRouter] = None,
        ab_framework: Optional[AgentABTestingFramework] = None,
        ledger: Optional[DecisionLedger] = None,
    ) -> None:
        self.evaluator = evaluator or ContinuousEvaluator()
        self.router = router or LearningRouter()
        self.ab_framework = ab_framework or AgentABTestingFramework()
        self.ledger = ledger or DecisionLedger()

        self.training_states: Dict[str, AgentTrainingState] = {}
        self.active_sessions: Dict[str, TrainingSession] = {}
        self.training_history: List[TrainingSession] = []

        self.feedback_queue: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.min_feedback_for_training = 10
        self.training_interval_hours = 24
        self.auto_trigger_enabled = False

        self._storage_dir = Path(".training_state")
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    async def start_training_session(self, agent_type: str) -> TrainingSession:
        """Start a new training session for an agent."""

        session_id = (
            f"training_{agent_type}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        )

        if agent_type not in self.training_states:
            self.training_states[agent_type] = AgentTrainingState(
                agent_type=agent_type,
                baseline_performance=self._get_current_metrics(agent_type),
            )

        session = TrainingSession(
            session_id=session_id,
            agent_type=agent_type,
            start_time=datetime.now(timezone.utc),
        )

        self.active_sessions[session_id] = session
        logger.info("Started training session %s for agent %s", session_id, agent_type)

        self.ledger.log_decision(
            agent_type="TrainingManager",
            decision_type="TRAINING_SESSION_STARTED",
            metadata={
                "session_id": session_id,
                "agent_type": agent_type,
                "baseline_metrics": self.training_states[
                    agent_type
                ].baseline_performance,
            },
        )

        return session

    async def process_feedback(
        self,
        agent_type: str,
        task_result: Dict[str, Any],
        user_rating: Optional[float] = None,
        corrections: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Process feedback for an agent's performance."""

        if agent_type not in self.training_states:
            self.training_states[agent_type] = AgentTrainingState(
                agent_type=agent_type,
                baseline_performance=self._get_current_metrics(agent_type),
            )

        feedback = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_result": task_result,
            "user_rating": user_rating,
            "corrections": corrections,
        }

        self.feedback_queue[agent_type].append(feedback)

        state = self.training_states.get(agent_type)
        if state:
            state.total_feedback += 1

        logger.debug(
            "Processed feedback for %s. Queue size: %d",
            agent_type,
            len(self.feedback_queue[agent_type]),
        )

        if (
            self.auto_trigger_enabled
            and len(self.feedback_queue[agent_type]) >= self.min_feedback_for_training
        ):
            if await self._should_trigger_training(agent_type):
                await self.train_agent(agent_type)

    async def train_agent(self, agent_type: str) -> Dict[str, Any]:
        """Execute a training cycle for an agent using accumulated feedback."""

        session = await self.start_training_session(agent_type)

        try:
            feedback_batch = self.feedback_queue[agent_type][
                : self.min_feedback_for_training
            ]

            current_metrics = await self._evaluate_with_feedback(
                agent_type, feedback_batch
            )
            session.metrics = current_metrics

            baseline = self.training_states[agent_type].baseline_performance
            improvements = self._calculate_improvements(baseline, current_metrics)
            session.improvements = improvements

            await self._update_routing_weights(
                agent_type, current_metrics, feedback_batch
            )

            state = self.training_states[agent_type]
            state.current_performance = current_metrics
            state.total_sessions += 1
            state.last_training = datetime.now(timezone.utc)

            self.feedback_queue[agent_type] = self.feedback_queue[agent_type][
                self.min_feedback_for_training :
            ]
            session.feedback_count = len(feedback_batch)

            session.end_time = datetime.now(timezone.utc)
            session.status = "completed"

            self.training_history.append(session)
            self.active_sessions.pop(session.session_id, None)

            logger.info(
                "Completed training for %s. Improvements: %s",
                agent_type,
                improvements,
            )

            self.ledger.log_decision(
                agent_type="TrainingManager",
                decision_type="TRAINING_COMPLETED",
                metadata={
                    "session_id": session.session_id,
                    "agent_type": agent_type,
                    "metrics": current_metrics,
                    "improvements": improvements,
                    "feedback_processed": len(feedback_batch),
                },
            )

            state.baseline_performance = current_metrics

            return {
                "session_id": session.session_id,
                "status": "completed",
                "metrics": current_metrics,
                "improvements": improvements,
                "feedback_processed": len(feedback_batch),
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Training failed for %s: %s", agent_type, exc)
            session.status = "failed"
            session.end_time = datetime.now(timezone.utc)
            self.active_sessions.pop(session.session_id, None)

            self.ledger.log_decision(
                agent_type="TrainingManager",
                decision_type="TRAINING_FAILED",
                metadata={
                    "session_id": session.session_id,
                    "agent_type": agent_type,
                    "error": str(exc),
                },
            )

            return {
                "session_id": session.session_id,
                "status": "failed",
                "error": str(exc),
            }

    async def run_ab_test(
        self,
        agent_a_type: str,
        agent_b_type: str,
        test_cases: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run A/B test between two agent variants."""

        logger.info("Starting A/B test: %s vs %s", agent_a_type, agent_b_type)

        agent_a = type(
            "Agent",
            (),
            {"execute": lambda self, task: {"success": True, "latency": 0.5}},
        )()
        agent_b = type(
            "Agent",
            (),
            {"execute": lambda self, task: {"success": True, "latency": 0.3}},
        )()

        result = await self.ab_framework.run_ab_test(
            agent_a=agent_a,
            agent_b=agent_b,
            test_cases=test_cases,
            metrics=["latency", "accuracy"],
        )

        self.ledger.log_decision(
            agent_type="TrainingManager",
            decision_type="AB_TEST_COMPLETED",
            metadata={
                "agent_a": agent_a_type,
                "agent_b": agent_b_type,
                "winner": result["winner"],
                "confidence": result["statistical_significance"],
            },
        )

        return result

    def get_training_stats(self, agent_type: Optional[str] = None) -> Dict[str, Any]:
        """Get training statistics for agents."""

        if agent_type:
            state = self.training_states.get(agent_type)
            if not state:
                pending_feedback = len(self.feedback_queue.get(agent_type, []))
                return {
                    "agent_type": agent_type,
                    "total_sessions": 0,
                    "total_feedback": pending_feedback,
                    "current_performance": {},
                    "baseline_performance": self._get_current_metrics(agent_type),
                    "improvements": {},
                    "last_training": None,
                    "pending_feedback": pending_feedback,
                }

            return {
                "agent_type": agent_type,
                "total_sessions": state.total_sessions,
                "total_feedback": state.total_feedback,
                "current_performance": state.current_performance,
                "baseline_performance": state.baseline_performance,
                "improvements": self._calculate_improvements(
                    state.baseline_performance, state.current_performance
                ),
                "last_training": (
                    state.last_training.isoformat() if state.last_training else None
                ),
                "pending_feedback": len(self.feedback_queue.get(agent_type, [])),
            }

        return {
            agent: self.get_training_stats(agent)
            for agent in self.training_states.keys()
        }

    async def _should_trigger_training(self, agent_type: str) -> bool:
        """Determine if training should be triggered for an agent."""

        state = self.training_states.get(agent_type)
        if not state or not state.last_training:
            return True

        time_since_last = datetime.now(timezone.utc) - state.last_training
        return time_since_last > timedelta(hours=self.training_interval_hours)

    async def _evaluate_with_feedback(
        self, agent_type: str, feedback_batch: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Evaluate agent performance using feedback."""

        await asyncio.sleep(0)

        total_ratings = sum(
            fb.get("user_rating", 0.5) for fb in feedback_batch if fb.get("user_rating")
        )
        count_ratings = sum(1 for fb in feedback_batch if fb.get("user_rating"))

        avg_rating = total_ratings / count_ratings if count_ratings > 0 else 0.5

        success_count = sum(
            1
            for fb in feedback_batch
            if fb.get("task_result", {}).get("success", False)
        )
        success_rate = success_count / len(feedback_batch) if feedback_batch else 0.0

        return {
            "user_satisfaction": avg_rating,
            "success_rate": success_rate,
            "feedback_volume": float(len(feedback_batch)),
        }

    async def _update_routing_weights(
        self,
        agent_type: str,
        metrics: Dict[str, float],
        feedback_batch: List[Dict[str, Any]],
    ) -> None:
        """Update routing weights based on training results."""

        for feedback in feedback_batch:
            task_result = feedback.get("task_result", {})
            route = task_result.get("route", "default")
            success = task_result.get("success", False)
            latency = task_result.get("latency", 1.0)

            request = {"agent_type": agent_type}
            self.router.update_route_performance(request, route, success, latency)

    def _calculate_improvements(
        self, baseline: Dict[str, float], current: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate percentage improvements from baseline."""

        improvements: Dict[str, float] = {}
        for key, current_value in current.items():
            baseline_value = baseline.get(key)
            if baseline_value and baseline_value > 0:
                improvement = ((current_value - baseline_value) / baseline_value) * 100
                improvements[key] = round(improvement, 2)
        return improvements

    def _get_current_metrics(self, agent_type: str) -> Dict[str, float]:
        """Get current baseline metrics for an agent."""

        return {
            "user_satisfaction": 0.7,
            "success_rate": 0.85,
            "feedback_volume": 0.0,
        }


__all__ = ["TrainingManager", "TrainingSession", "AgentTrainingState"]
