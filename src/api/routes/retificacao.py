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
    registros_originais: List[RegistroCanonicoInput]
    registros_retificados: List[RegistroCanonicoInput]

    @field_validator("registros_originais", "registros_retificados")
    @classmethod
    def lista_nao_vazia(cls, v: list) -> list:
        if not v:
            raise ValueError("A lista de registros não pode ser vazia.")
        return v


class NotaCorrecaoRequest(BaseModel):
    escrituracao_original_id: str
    escrituracao_retificada_id: str
    motivo: str
    resumo_mudancas: Optional[Dict[str, Any]] = None
    aprovado_por: Optional[str] = None

    @field_validator("motivo")
    @classmethod
    def motivo_nao_vazio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("motivo não pode ser vazio.")
        if len(v) > 1000:
            raise ValueError("motivo excede 1000 caracteres.")
        return v

    @field_validator("escrituracao_original_id", "escrituracao_retificada_id")
    @classmethod
    def uuid_valido(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("ID deve ser um UUID válido.")
        return v


class ValidarLayoutRequest(BaseModel):
    registros: List[RegistroCanonicoInput]

    @field_validator("registros")
    @classmethod
    def lista_nao_vazia(cls, v: list) -> list:
        if not v:
            raise ValueError("A lista de registros não pode ser vazia.")
        return v


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
    """
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
    """Valida a contagem de campos de cada registro contra o leiaute oficial
    EFD ICMS/IPI v3.1.5.  Registros desconhecidos geram aviso, não erro.
    """
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

    if not os.environ.get("DATABASE_URL"):
        logger.info(
            "nota_correcao simulada (sem DATABASE_URL): original=%s retificada=%s",
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
