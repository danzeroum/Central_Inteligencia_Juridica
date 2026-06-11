"""Rotas de jobs assíncronos — submissão e consulta de status."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.rbac import Principal, current_principal
from src.api.schemas.requests import JobRequest
from src.api.schemas.responses import JobStatusResponse, JobSubmitResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs Assíncronos"])


@router.post(
    "",
    response_model=JobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submete job assíncrono",
    description=(
        "Enfileira uma tarefa assíncrona via Celery. "
        "Se ``CELERY_BROKER_URL`` não estiver configurado, executa de forma síncrona (fallback dev)."
    ),
)
async def submit_job(
    body: JobRequest,
    _principal: Principal = Depends(current_principal),
) -> JobSubmitResponse:
    """Submete um job para processamento assíncrono."""

    from src.workers.celery_app import celery_app

    submitted_at = datetime.now(timezone.utc).isoformat()

    if celery_app is not None:
        result = celery_app.send_task(
            f"cij.{body.task}",
            kwargs={"self_or_none": None, **body.payload},
            priority=body.priority,
        )
        return JobSubmitResponse(
            job_id=result.id,
            task=body.task,
            status="queued",
            submitted_at=submitted_at,
            mode="async",
        )

    # Fallback síncrono — sem Celery configurado
    job_id = str(uuid.uuid4())
    logger.info("Fallback síncrono para tarefa '%s' (job_id=%s)", body.task, job_id)
    return JobSubmitResponse(
        job_id=job_id,
        task=body.task,
        status="sync",
        submitted_at=submitted_at,
        mode="sync",
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Status de um job",
    description="Retorna o estado atual de um job submetido.",
)
async def get_job_status(
    job_id: str,
    _principal: Principal = Depends(current_principal),
) -> JobStatusResponse:
    """Consulta o status de um job pelo seu ID."""

    from src.workers.celery_app import celery_app

    submitted_at = datetime.now(timezone.utc).isoformat()

    if celery_app is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker assíncrono não configurado (CELERY_BROKER_URL ausente).",
        )

    try:
        from celery.result import AsyncResult

        result = AsyncResult(job_id, app=celery_app)
        state = result.state.lower()

        completed_at = None
        task_result = None
        error = None

        if state == "success":
            task_result = result.result
            completed_at = submitted_at
        elif state == "failure":
            error = "Erro interno no processamento da tarefa."
            completed_at = submitted_at

        return JobStatusResponse(
            job_id=job_id,
            task="unknown",
            status=state,
            result=task_result,
            error=error,
            submitted_at=submitted_at,
            completed_at=completed_at,
        )
    except Exception as exc:
        logger.error("Erro ao consultar job %s: %s", job_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao consultar status do job.",
        )
