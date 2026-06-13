"""Endpoints de retificação SPED ponta-a-ponta (S-D.2).

RBAC:
  - retificacao:read  → ADMIN, AUDITOR (comparação e leitura de notas)
  - retificacao:write → ADMIN, OPERATOR (criação de retificação e nota de correção)

Não persiste escriturações diretamente — delega ao fluxo existente de
upload/parse.  Aqui: comparação antes/depois e gestão da nota de correção.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from src.fiscal.retificacao.comparador import comparar_registros
from src.fiscal.writer.layout_validator import validar_layout

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fiscal/retificacao", tags=["Retificação SPED"])


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class RegistroCanonicoInput(BaseModel):
    tipo_registro: str
    numero_linha: int
    dados: Optional[Dict[str, Any]] = None

    @field_validator("tipo_registro")
    @classmethod
    def tipo_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("tipo_registro não pode ser vazio.")
        return v.strip().upper()


class ComparacaoRequest(BaseModel):
    # Contrato completo
    registros_originais: Optional[List[RegistroCanonicoInput]] = None
    registros_retificados: Optional[List[RegistroCanonicoInput]] = None
    # Contrato simplificado (frontend envia apenas escrituracao_id)
    escrituracao_id: Optional[str] = None


class NotaCorrecaoRequest(BaseModel):
    # Contrato completo
    escrituracao_original_id: Optional[str] = None
    escrituracao_retificada_id: Optional[str] = None
    motivo: Optional[str] = None
    resumo_mudancas: Optional[Dict[str, Any]] = None
    aprovado_por: Optional[str] = None
    # Contrato simplificado (frontend envia escrituracao_id)
    escrituracao_id: Optional[str] = None


class ValidarLayoutRequest(BaseModel):
    # Contrato completo
    registros: Optional[List[RegistroCanonicoInput]] = None
    # Contrato simplificado
    escrituracao_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/comparar",
    summary="Compara registros originais vs retificados (S-D.2)",
    status_code=status.HTTP_200_OK,
)
async def comparar(body: ComparacaoRequest) -> Dict[str, Any]:
    """Retorna diferenças (adicionados, removidos, modificados) entre dois
    conjuntos de registros canônicos SPED.
    Aceita contrato simplificado com escrituracao_id (retorna diff stub).
    """
    if body.escrituracao_id and not body.registros_originais:
        logger.info("retificacao comparar stub: escrituracao_id=%s", body.escrituracao_id)
        return {
            "diff": [],
            "alteracoes": [],
            "adicionados": 0,
            "removidos": 0,
            "modificados": 0,
            "escrituracao_id": body.escrituracao_id,
            "is_stub": True,
        }

    if not body.registros_originais or not body.registros_retificados:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Forneça registros_originais + registros_retificados, ou apenas escrituracao_id.",
        )

    originais = [r.model_dump() for r in body.registros_originais]
    retificados = [r.model_dump() for r in body.registros_retificados]

    try:
        comparacao = comparar_registros(originais, retificados)
        return comparacao.to_dict()
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("retificacao comparar [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao comparar registros. Referência: {cid}",
        )


@router.post(
    "/validar-layout",
    summary="Valida layout EFD ICMS/IPI dos registros retificados (S-D.2)",
    status_code=status.HTTP_200_OK,
)
async def validar_layout_retificado(body: ValidarLayoutRequest) -> Dict[str, Any]:
    """Valida o leiaute EFD ICMS/IPI v3.1.5.
    Aceita contrato simplificado com escrituracao_id (retorna validação stub ok).
    """
    if body.escrituracao_id and not body.registros:
        logger.info("retificacao validar-layout stub: escrituracao_id=%s", body.escrituracao_id)
        return {
            "valido": True,
            "erros": [],
            "avisos": [],
            "escrituracao_id": body.escrituracao_id,
            "is_stub": True,
        }

    if not body.registros:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Forneça registros, ou apenas escrituracao_id.",
        )

    registros = [r.model_dump() for r in body.registros]

    try:
        resultado = validar_layout(registros)
        return resultado.to_dict()
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("retificacao validar-layout [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao validar layout. Referência: {cid}",
        )


@router.post(
    "/nota-correcao",
    summary="Registra nota de correção de uma retificação (S-D.2)",
    status_code=status.HTTP_201_CREATED,
)
async def criar_nota_correcao(body: NotaCorrecaoRequest) -> Dict[str, Any]:
    """Cria uma nota de correção associando a escrituração original à retificada.

    Em ambiente sem banco de dados configurado, retorna a nota apenas em memória
    (sem persistência) com status ``simulado=true``.  Com banco ativo, persiste
    via ORM e retorna o registro criado.
    """
    import os

    nota_id = str(uuid.uuid4())
    resumo = body.resumo_mudancas or {}

    # Contrato simplificado: apenas escrituracao_id
    eid = body.escrituracao_id
    orig_id = body.escrituracao_original_id or eid
    ret_id  = body.escrituracao_retificada_id or eid

    if not orig_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Forneça escrituracao_original_id + escrituracao_retificada_id, ou escrituracao_id.",
        )

    if not os.environ.get("DATABASE_URL"):
        logger.info(
            "nota_correcao simulada (sem DATABASE_URL): original=%s retificada=%s",
            orig_id,
            ret_id,
        )
        return {
            "id": nota_id,
            "escrituracao_original_id": orig_id,
            "escrituracao_retificada_id": ret_id,
            "motivo": body.motivo or "retificação gerada pelo sistema",
            "resumo_mudancas": resumo,
            "aprovado_por": body.aprovado_por,
            "simulado": True,
        }

    try:
        from src.db.session import get_sync_session

        from src.db.models import NotaCorrecao

        with get_sync_session() as session:
            nota = NotaCorrecao(
                id=uuid.UUID(nota_id),
                escrituracao_original_id=uuid.UUID(body.escrituracao_original_id),
                escrituracao_retificada_id=uuid.UUID(body.escrituracao_retificada_id),
                motivo=body.motivo,
                resumo_mudancas=resumo,
                aprovado_por=body.aprovado_por,
            )
            session.add(nota)
            session.commit()
            session.refresh(nota)

        logger.info(
            "nota_correcao criada: id=%s original=%s retificada=%s",
            nota_id,
            body.escrituracao_original_id,
            body.escrituracao_retificada_id,
        )
        return {
            "id": nota_id,
            "escrituracao_original_id": body.escrituracao_original_id,
            "escrituracao_retificada_id": body.escrituracao_retificada_id,
            "motivo": body.motivo,
            "resumo_mudancas": resumo,
            "aprovado_por": body.aprovado_por,
            "simulado": False,
        }
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("nota_correcao criar [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar nota de correção. Referência: {cid}",
        )
