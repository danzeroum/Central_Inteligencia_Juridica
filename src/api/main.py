from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from src.agents.supervisor_agent import SupervisorAgent

logger = logging.getLogger(__name__)

app = FastAPI(title="Central Inteligência Jurídica")

AUTH_REQUIRED = False


class TaskRequest(BaseModel):
    task_description: str = Field(..., description="Descrição da tarefa jurídica")


class SuccessfulTaskResponse(BaseModel):
    status: str
    supervisor_result: Dict[str, Any]
    tribunals_used: list[str]
    task_id: str
    execution_time: float
    parallel: bool
    timestamp: str


class AuthManager:
    @staticmethod
    async def verify_token() -> str:
        return "anonymous"


async def enforce_rate_limit() -> None:  # pragma: no cover - placeholder
    return None


supervisor_agent = SupervisorAgent()


@app.post("/tasks", response_model=SuccessfulTaskResponse)
async def process_task(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> SuccessfulTaskResponse:
    """Processa uma tarefa jurídica utilizando o SupervisorAgent."""

    logger.info(
        "Recebida tarefa para processamento%s: %s",
        f" do usuário {user_id}" if AUTH_REQUIRED else "",
        task_request.task_description,
    )

    result = await supervisor_agent.process_task(task_request.task_description)

    response = SuccessfulTaskResponse.model_validate(result)
    return response
