"""FastAPI endpoints for agent training management."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.training.training_manager import AgentTrainingState, TrainingManager

router = APIRouter(prefix="/api/v1/training", tags=["Training"])

_training_manager: Optional[TrainingManager] = None


def get_training_manager() -> TrainingManager:
    """Get or create the global training manager."""

    global _training_manager
    if _training_manager is None:
        _training_manager = TrainingManager()
    return _training_manager


class FeedbackRequest(BaseModel):
    """Request model for submitting agent feedback."""

    agent_type: str = Field(..., description="Type of agent (e.g., 'TJSP', 'TJMG')")
    task_result: Dict[str, Any] = Field(..., description="Result of the task execution")
    user_rating: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="User satisfaction rating (0-1)"
    )
    corrections: Optional[Dict[str, Any]] = Field(
        None, description="Corrections or improvements suggested by user"
    )


class TrainingRequest(BaseModel):
    """Request model for triggering agent training."""

    agent_type: str = Field(..., description="Type of agent to train")
    force: bool = Field(False, description="Force training even if conditions not met")


class ABTestRequest(BaseModel):
    """Request model for A/B testing."""

    agent_a_type: str = Field(..., description="First agent variant")
    agent_b_type: str = Field(..., description="Second agent variant")
    test_cases: List[Dict[str, Any]] = Field(..., description="Test cases to run")


class TrainingStatsResponse(BaseModel):
    """Response model for training statistics."""

    agent_type: Optional[str]
    stats: Dict[str, Any]


@router.post("/feedback", status_code=status.HTTP_202_ACCEPTED)
async def submit_feedback(feedback: FeedbackRequest) -> Dict[str, str]:
    """Submit feedback for an agent's performance."""

    manager = get_training_manager()

    await manager.process_feedback(
        agent_type=feedback.agent_type,
        task_result=feedback.task_result,
        user_rating=feedback.user_rating,
        corrections=feedback.corrections,
    )

    return {
        "status": "accepted",
        "message": f"Feedback for {feedback.agent_type} queued for training",
    }


@router.post("/train")
async def trigger_training(request: TrainingRequest) -> Dict[str, Any]:
    """Trigger a training cycle for a specific agent."""

    manager = get_training_manager()

    pending_feedback = len(manager.feedback_queue.get(request.agent_type, []))

    if not request.force and pending_feedback < manager.min_feedback_for_training:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Insufficient feedback for training. "
                f"Need {manager.min_feedback_for_training}, have {pending_feedback}. "
                "Use force=true to override."
            ),
        )

    result = await manager.train_agent(request.agent_type)

    if result.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Training failed: {result.get('error')}",
        )

    return result


@router.get("/stats")
async def get_training_stats(agent_type: Optional[str] = None) -> TrainingStatsResponse:
    """Get training statistics for agents."""

    manager = get_training_manager()
    stats = manager.get_training_stats(agent_type)

    return TrainingStatsResponse(agent_type=agent_type, stats=stats)


@router.get("/active-sessions")
async def get_active_sessions() -> Dict[str, Any]:
    """Get all currently active training sessions."""

    manager = get_training_manager()

    sessions = {
        session_id: {
            "agent_type": session.agent_type,
            "start_time": session.start_time.isoformat(),
            "status": session.status,
            "metrics": session.metrics,
        }
        for session_id, session in manager.active_sessions.items()
    }

    return {
        "active_count": len(sessions),
        "sessions": sessions,
    }


@router.get("/history")
async def get_training_history(agent_type: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Get training history."""

    manager = get_training_manager()

    history = manager.training_history
    if agent_type:
        history = [session for session in history if session.agent_type == agent_type]

    history = sorted(history, key=lambda session: session.start_time, reverse=True)[:limit]

    return {
        "total_sessions": len(manager.training_history),
        "filtered_count": len(history),
        "sessions": [
            {
                "session_id": session.session_id,
                "agent_type": session.agent_type,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "status": session.status,
                "metrics": session.metrics,
                "improvements": session.improvements,
                "feedback_count": session.feedback_count,
            }
            for session in history
        ],
    }


@router.post("/ab-test")
async def run_ab_test(request: ABTestRequest) -> Dict[str, Any]:
    """Run an A/B test between two agent variants."""

    manager = get_training_manager()

    if not request.test_cases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="test_cases cannot be empty",
        )

    result = await manager.run_ab_test(
        agent_a_type=request.agent_a_type,
        agent_b_type=request.agent_b_type,
        test_cases=request.test_cases,
    )

    return result


@router.post("/reset/{agent_type}")
async def reset_training_state(agent_type: str) -> Dict[str, str]:
    """Reset training state for an agent."""

    manager = get_training_manager()

    if agent_type not in manager.training_states:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No training state found for agent {agent_type}",
        )

    manager.feedback_queue[agent_type] = []
    manager.training_states[agent_type] = AgentTrainingState(
        agent_type=agent_type,
        baseline_performance=manager._get_current_metrics(agent_type),
    )

    return {
        "status": "success",
        "message": f"Training state reset for {agent_type}",
    }


__all__ = ["router", "get_training_manager"]
