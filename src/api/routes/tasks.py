"""Rotas de processamento de tarefas jurídicas (simples, avançado e comparação)."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.auth import AuthManager
from src.api.rate_limit import enforce_rate_limit
from src.api.rbac import Principal, require_permissions
from src.api.schemas.requests import ProblemDetail, SuccessfulTaskResponse, TaskRequest
from src.api.state import supervisor_agent, unified_orchestrator
from src.api.config import AUTH_REQUIRED

logger = logging.getLogger(__name__)

router = APIRouter()


async def _process_task_internal(
    task_request: TaskRequest,
    user_id: str,
) -> SuccessfulTaskResponse:
    logger.info(
        "Recebida tarefa para processamento%s: %s",
        f" do usuário {user_id}" if AUTH_REQUIRED else "",
        task_request.task_description,
    )
    result = await supervisor_agent.process_task(task_request.task_description)
    return SuccessfulTaskResponse.model_validate(result)


@router.post(
    "/tasks",
    response_model=SuccessfulTaskResponse,
    deprecated=True,
    summary="(Deprecated) Processa tarefa — use POST /api/v1/tasks",
)
async def process_task(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> SuccessfulTaskResponse:
    """Processa uma tarefa jurídica utilizando o SupervisorAgent."""

    return await _process_task_internal(task_request, user_id)


@router.post("/api/v1/tasks", response_model=SuccessfulTaskResponse, tags=["MCP"])
async def process_task_v1(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> SuccessfulTaskResponse:
    """Processa tarefa jurídica utilizando o padrão MCP."""

    return await _process_task_internal(task_request, user_id)


@router.post(
    "/api/v1/tasks/advanced",
    tags=["Advanced AI Agent"],
    summary="Processa tarefa com orquestração completa de agentes",
    description="""
    Endpoint avançado que ativa o UnifiedOrchestrator com:
    - Squad completo de agentes especializados
    - RAG para enriquecimento de contexto
    - Chain-of-Thought para raciocínio
    - Consensus mechanism para decisões complexas
    - Adaptive planning com replanning automático
    """,
    responses={
        200: {"description": "Tarefa processada com sucesso pelo squad"},
        400: {"model": ProblemDetail},
        500: {"model": ProblemDetail},
    },
)
async def process_advanced_task(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Processa uma tarefa jurídica complexa utilizando o UnifiedOrchestrator."""

    logger.info(
        "🚀 ADVANCED MODE: Tarefa recebida do usuário %s: %s",
        user_id if AUTH_REQUIRED else "anonymous",
        task_request.task_description,
    )

    try:
        task_payload = {
            "task_id": f"adv_{user_id}_{int(time.time())}",
            "description": task_request.task_description,
            "priority": "high",
            "user_id": user_id,
            "requires_consensus": True,
        }

        result = await unified_orchestrator.execute_complex_task(task_payload)
        result["api_mode"] = "advanced"
        result["api_version"] = "1.1.0"

        logger.info(
            "✅ ADVANCED MODE: Tarefa concluída com sucesso=%s, confidence=%s",
            result.get("success"),
            result.get("consensus_strength", "N/A"),
        )

        return result

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive safeguard
        # SECURITY (SEC-004 / CWE-209): não devolver str(exc) ao cliente.
        correlation_id = uuid.uuid4().hex
        logger.error(
            "❌ ADVANCED MODE: erro no processamento [%s]: %s",
            correlation_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Erro interno ao processar a tarefa avançada. "
                f"Referência para suporte: {correlation_id}"
            ),
        )


@router.post(
    "/api/v1/tasks/compare",
    tags=["Advanced AI Agent"],
    summary="Compara processamento simples vs avançado (restrito a admin)",
    description="Executa a mesma tarefa nos dois modos e retorna comparação",
    responses={403: {"model": ProblemDetail}},
)
async def compare_modes(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _principal: Principal = Depends(require_permissions("tasks:compare")),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Compara resultado do modo simples vs avançado para análise."""

    simple_result = await supervisor_agent.process_task(task_request.task_description)

    advanced_payload = {
        "task_id": f"cmp_{user_id}_{int(time.time())}",
        "description": task_request.task_description,
        "priority": "medium",
        "requires_consensus": False,
    }
    advanced_result = await unified_orchestrator.execute_complex_task(advanced_payload)

    advanced_mode_data = advanced_result.get("advanced_result", {})

    return {
        "comparison": {
            "simple_mode": simple_result,
            "advanced_mode": advanced_result,
            "differences": {
                "reasoning_depth": (
                    "advanced" if "reasoning" in advanced_mode_data else "simple"
                ),
                "consensus_used": bool(advanced_mode_data.get("consensus")),
                "rag_enabled": any(
                    "rag" in str(value).lower() for value in advanced_mode_data.values()
                ),
            },
        },
        "recommendation": "Use /api/v1/tasks/advanced para tarefas complexas",
    }
