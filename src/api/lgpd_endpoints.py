"""Endpoints de direitos do titular (LGPD).

SECURITY/COMPLIANCE (LGPD-001 — Arts. 17-22 da LGPD): implementa os direitos do
titular sobre seus dados pessoais — acesso, portabilidade e exclusão.

A exclusão preserva a trilha de auditoria *append-only* (Decision Ledger):
em vez de apagar entradas, anonimiza os campos que referenciam o titular
(``subject_id``), e registra a própria operação de exclusão (quem, quando, por
quê) — atendendo simultaneamente ao direito de exclusão e à exigência de
auditabilidade. A identificação do titular usa ``metadata.subject_id``.

Autorização (RBAC): leitura exige ``lgpd:read`` (auditor/admin); exclusão exige
``lgpd:write`` (admin). Em dev/testes (auth desligada) as checagens são relaxadas.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.rbac import Principal, require_permissions
from src.utils.ledger import get_ledger
from src.utils.request_context import get_audit_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/lgpd", tags=["LGPD"])

# Campo de metadata usado para identificar o titular dos dados nas entradas.
SUBJECT_FIELD = "subject_id"

# SECURITY (M09): valida o formato do ``subject_id`` (allowlist estrito) antes de
# usá-lo em buscas/anonimização, fechando entradas malformadas/abusivas.
_SUBJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.@\-]{1,128}$")


def _validate_subject_id(subject_id: str) -> str:
    if not _SUBJECT_ID_PATTERN.match(subject_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="subject_id inválido (formato não permitido)",
        )
    return subject_id


def _entries_for_subject(subject_id: str) -> List[Dict[str, Any]]:
    """Entradas do ledger cuja metadata referencia o titular informado."""

    ledger = get_ledger()
    return [
        entry
        for entry in ledger.get_entries()
        if (entry.get("metadata") or {}).get(SUBJECT_FIELD) == subject_id
    ]


def _try_delete_vector_memory(subject_id: str) -> int:
    """Best-effort: remove embeddings do titular, se a memória estiver disponível."""

    try:
        from src.memory.vector_memory import VectorMemory

        memory = VectorMemory()
        if not memory.is_available():
            return 0
        return memory.delete_by_metadata({SUBJECT_FIELD: subject_id})
    except Exception as exc:  # pragma: no cover - memória opcional
        logger.warning("Memória vetorial indisponível para exclusão LGPD: %s", exc)
        return 0


@router.get(
    "/data/{subject_id}",
    summary="Acesso aos dados do titular (LGPD Art. 18, II)",
)
async def get_subject_data(
    subject_id: str,
    _principal: Principal = Depends(require_permissions("lgpd:read")),
) -> Dict[str, Any]:
    """Retorna os registros de auditoria associados ao titular."""

    _validate_subject_id(subject_id)
    entries = _entries_for_subject(subject_id)
    return {
        "subject_id": subject_id,
        "record_count": len(entries),
        "records": entries,
    }


@router.get(
    "/data/{subject_id}/export",
    summary="Portabilidade dos dados do titular (LGPD Art. 18, V)",
)
async def export_subject_data(
    subject_id: str,
    _principal: Principal = Depends(require_permissions("lgpd:read")),
) -> Dict[str, Any]:
    """Exporta os dados do titular em formato estruturado (JSON) e portável."""

    _validate_subject_id(subject_id)
    entries = _entries_for_subject(subject_id)
    return {
        "format": "json",
        "subject_id": subject_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(entries),
        "records": entries,
    }


@router.delete(
    "/data/{subject_id}",
    summary="Exclusão/anonimização dos dados do titular (LGPD Art. 18, VI)",
)
async def delete_subject_data(
    subject_id: str,
    justification: str = Query(
        ..., min_length=3, description="Base legal/justificativa da exclusão"
    ),
    principal: Principal = Depends(require_permissions("lgpd:write")),
) -> Dict[str, Any]:
    """Anonimiza os dados do titular e registra a operação para auditoria."""

    _validate_subject_id(subject_id)
    ledger = get_ledger()
    anonymized = ledger.anonymize_entries(field_name=SUBJECT_FIELD, value=subject_id)
    vector_deleted = _try_delete_vector_memory(subject_id)

    # Registra a própria operação de exclusão (accountability — Art. 37).
    operator = "anonymous" if principal.is_anonymous else principal.user_id
    ledger.log_decision(
        agent_type="DPO",
        decision_type="LGPD_DELETION",
        metadata={
            "subject_id": subject_id,
            "justification": justification,
            "operator_id": operator,
            "ledger_entries_anonymized": anonymized,
            "vector_records_deleted": vector_deleted,
            **get_audit_context(),
        },
    )

    logger.info(
        "LGPD deletion for subject=%s by %s (ledger=%d, vector=%d)",
        subject_id,
        operator,
        anonymized,
        vector_deleted,
    )

    return {
        "status": "completed",
        "subject_id": subject_id,
        "ledger_entries_anonymized": anonymized,
        "vector_records_deleted": vector_deleted,
    }


__all__ = ["router"]
