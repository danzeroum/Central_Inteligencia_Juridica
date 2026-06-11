"""Endpoint de upload seguro de arquivos fiscais (Bloco B — S-B.1).

POST /api/v1/fiscal/upload
  - Aceita SPED TXT, XML (NF-e/CT-e/NFS-e), PDF, ZIP de um único arquivo
  - Valida via UploadGuard (zip-bomb, xml-bomb, tamanho, tipo)
  - Sanitiza metadados com InputSanitizer
  - Persiste no S3/MinIO via S3Client
  - Registra entrada em EscrituracaoFiscal + FiscalAudit (quando DB disponível)
  - Retorna correlation_id + storage_key para rastreabilidade
"""

from __future__ import annotations

import io
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from src.api.rbac import Principal, current_principal
from src.fiscal.upload import UploadGuard, UploadResult, get_upload_guard
from src.utils.input_sanitizer import InputSanitizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fiscal", tags=["Fiscal"])

_sanitizer = InputSanitizer(max_length=256)

_ALLOWED_TIPOS = {"efd_icms", "efd_contrib", "xml", "pdf", "outro"}


class UploadResponse(BaseModel):
    correlation_id: str
    filename: str
    file_type: str
    size_bytes: int
    sha256: str
    storage_key: Optional[str]
    db_id: Optional[str]
    message: str


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload de arquivo fiscal",
    description=(
        "Faz upload seguro de um arquivo fiscal (SPED TXT, XML, PDF, ZIP). "
        "Valida tamanho, zip-bomb e xml-bomb antes de aceitar. "
        "Grava no storage (MinIO/S3) e registra em FiscalAudit."
    ),
)
async def upload_fiscal(
    file: UploadFile = File(..., description="Arquivo fiscal (SPED/XML/PDF/ZIP)"),
    tipo: str = Form(
        "outro",
        description="Tipo da escrituração: efd_icms | efd_contrib | xml | pdf | outro",
    ),
    ano: int = Form(..., description="Ano de competência (ex: 2025)"),
    mes: Optional[int] = Form(
        None, description="Mês de competência (1-12); None para anual"
    ),
    cnpj_masked: Optional[str] = Form(
        None,
        description="CNPJ mascarado do contribuinte (LGPD — somente forma mascarada)",
    ),
    _principal: Principal = Depends(current_principal),
    guard: UploadGuard = Depends(get_upload_guard),
) -> UploadResponse:
    """Faz upload e registra arquivo fiscal com validações de segurança."""

    if tipo not in _ALLOWED_TIPOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"tipo inválido. Valores aceitos: {sorted(_ALLOWED_TIPOS)}",
        )

    if mes is not None and not (1 <= mes <= 12):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="mes deve estar entre 1 e 12.",
        )

    if ano < 2000 or ano > 2100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ano deve estar entre 2000 e 2100.",
        )

    filename = _sanitizer.sanitize_text(file.filename or "arquivo")

    try:
        raw_data = await file.read()
    except Exception as exc:
        logger.error("Erro ao ler arquivo enviado: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erro ao ler o arquivo enviado.",
        )

    # ── Validação de segurança ────────────────────────────────────────────────
    result: UploadResult = guard.validate(
        filename=filename,
        data=raw_data,
        content_type=file.content_type or "application/octet-stream",
    )

    correlation_id = str(uuid.uuid4())
    storage_key: Optional[str] = None
    db_id: Optional[str] = None

    # ── Upload para S3/MinIO ──────────────────────────────────────────────────
    try:
        from src.storage.s3_client import get_s3_client

        s3 = get_s3_client()
        if s3.is_configured:
            storage_key = f"fiscal/{ano}/{mes or 'anual'}/{correlation_id}/{filename}"
            ok = s3.upload_file(
                file_obj=io.BytesIO(result.data),
                key=storage_key,
                content_type=file.content_type or "application/octet-stream",
            )
            if not ok:
                storage_key = None
                logger.warning(
                    "Upload S3 falhou (correlation_id=%s) — prosseguindo sem storage.",
                    correlation_id,
                )
    except Exception as exc:
        logger.warning(
            "Erro ao acessar S3Client (correlation_id=%s): %s", correlation_id, exc
        )

    # ── Registro em DB (opcional — sem DB disponível continua) ────────────────
    try:
        from src.db.session import get_async_session
        from src.db.models import EscrituracaoFiscal, FiscalAudit, PeriodoFiscal
        from src.fiscal.repository import (
            EscrituracaoRepository,
            PeriodoFiscalRepository,
        )

        async with get_async_session() as session:
            async with session.begin():
                periodo_repo = PeriodoFiscalRepository(session)
                periodo = await periodo_repo.get_or_create(ano=ano, mes=mes)

                escrit = EscrituracaoFiscal(
                    periodo_id=periodo.id,
                    tipo=tipo,
                    origem="upload",
                    status="pendente",
                    storage_key=storage_key,
                    cnpj_masked=cnpj_masked,
                    checksum_sha256=result.sha256,
                    file_size_bytes=result.size_bytes,
                    details={
                        "correlation_id": correlation_id,
                        "original_filename": filename,
                    },
                )
                escrit_repo = EscrituracaoRepository(session)
                await escrit_repo.save(escrit)
                db_id = str(escrit.id)

                audit = FiscalAudit(
                    operation="import",
                    entity_type=tipo,
                    entity_ref=correlation_id,
                    status="pending",
                    details={
                        "sha256": result.sha256,
                        "size_bytes": result.size_bytes,
                        "storage_key": storage_key,
                        "escrituracao_id": db_id,
                    },
                )
                session.add(audit)
    except RuntimeError:
        # DATABASE_URL não configurada — modo sem persistência
        pass
    except Exception as exc:
        logger.warning(
            "Erro ao persistir escrituração (correlation_id=%s): %s",
            correlation_id,
            exc,
        )

    logger.info(
        "Upload recebido: correlation_id=%s filename=%s size=%d sha256=%s storage_key=%s",
        correlation_id,
        filename,
        result.size_bytes,
        result.sha256[:8],
        storage_key,
    )

    # ── Disparo do processamento (DT-05) ──────────────────────────────────────
    # Celery disponível → enfileira task; caso contrário → executa inline.
    competencia = f"{ano}-{mes:02d}" if mes else str(ano)
    _regime = "lucro_real"  # TODO(S-C.3): extrair regime dos metadados do upload

    try:
        from src.workers.celery_app import celery_app as _celery
        from src.workers.tasks import _execute_processing, process_sped_file

        if _celery is not None and storage_key:
            process_sped_file.delay(
                file_key=storage_key,
                tenant_id=(
                    str(_principal.user_id)
                    if hasattr(_principal, "user_id")
                    else "anon"
                ),
                cnpj_masked=cnpj_masked or "",
                competencia=competencia,
                escrituracao_id=db_id,
                tipo=tipo,
                regime=_regime,
            )
            logger.info(
                "process_sped_file enfileirado via Celery (correlation_id=%s)",
                correlation_id,
            )
        else:
            # Inline: executa no mesmo loop assíncrono (sem Celery/MinIO)
            await _execute_processing(
                file_key=storage_key or "",
                tenant_id=(
                    str(_principal.user_id)
                    if hasattr(_principal, "user_id")
                    else "anon"
                ),
                cnpj_masked=cnpj_masked or "",
                competencia=competencia,
                escrituracao_id=db_id,
                tipo=tipo,
                regime=_regime,
                correlation_id=correlation_id,
                raw_data=result.data,
            )
            logger.info(
                "process_sped_file executado inline (correlation_id=%s)", correlation_id
            )
    except Exception as exc:
        logger.warning(
            "Falha ao disparar processamento (correlation_id=%s): %s",
            correlation_id,
            exc,
        )

    return UploadResponse(
        correlation_id=correlation_id,
        filename=filename,
        file_type=result.file_type,
        size_bytes=result.size_bytes,
        sha256=result.sha256,
        storage_key=storage_key,
        db_id=db_id,
        message="Arquivo recebido e processamento iniciado.",
    )
