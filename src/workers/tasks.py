"""Tarefas Celery da plataforma.

Cada tarefa é decorada condicionalmente: se o Celery não estiver disponível
(sem broker), as funções são executadas de forma síncrona como fallback.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _task(func):
    """Decorator que registra a função como task Celery ou mantém síncrona."""
    if celery_app is not None:
        return celery_app.task(bind=True, name=f"cij.{func.__name__}")(func)
    return func


@_task
def analyze_document(
    self_or_none,
    document_id: str,
    tenant_id: str,
    options: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Análise assíncrona de documento jurídico.

    Quando executada via Celery, ``self_or_none`` é a instância da task (``bind=True``).
    No fallback síncrono, é ``None``.
    """
    logger.info("analyze_document: document_id=%s tenant=%s", document_id, tenant_id)
    return {
        "document_id": document_id,
        "tenant_id": tenant_id,
        "status": "analyzed",
        "summary": "Documento processado (placeholder — pipeline SPED em S-B.1).",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


@_task
def process_sped_file(
    self_or_none,
    file_key: str,
    tenant_id: str,
    cnpj_masked: str,
    competencia: str,
) -> Dict[str, Any]:
    """Processa arquivo SPED armazenado no MinIO/S3.

    ``file_key`` é o path no bucket (ex.: ``tenants/{tenant_id}/sped/{uuid}.txt``).
    ``cnpj_masked`` segue LGPD: ``XX.XXX.XXX/XXXX-XX`` → ``**.***.***/**XX-**``.
    """
    logger.info(
        "process_sped_file: key=%s tenant=%s cnpj=%s competencia=%s",
        file_key,
        tenant_id,
        cnpj_masked,
        competencia,
    )
    return {
        "file_key": file_key,
        "tenant_id": tenant_id,
        "cnpj_masked": cnpj_masked,
        "competencia": competencia,
        "status": "queued",
        "job_id": str(uuid.uuid4()),
        "message": "SPED enfileirado — parser EFD em S-B.1.",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
