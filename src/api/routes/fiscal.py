"""Rotas do módulo Fiscal — Bloco A (S-A.1 Due Diligência 360° e S-A.2 Consultoria)."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from src.api.auth import AuthManager
from src.api.rate_limit import enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fiscal", tags=["Fiscal"])

# Aceita apenas formatos sem '/' para evitar ambiguidade com separadores de URL.
# Exemplos válidos: "11222333000181", "11.222.333.0001-81".
# CNPJ com barra (11.222.333/0001-81) deve ser passado codificado (%2F) ou sem barra.
_CNPJ_RE = re.compile(r"^\d{14}$|^\d{2}\.?\d{3}\.?\d{3}\.?\d{4}-?\d{2}$")

_ALLOWED_REGIMES = frozenset(
    {"simples_nacional", "lucro_presumido", "lucro_real", "mei"}
)
_ALLOWED_PORTES = frozenset({"mei", "me", "epp", "medio", "grande"})


class ConsultoriaRequest(BaseModel):
    """Payload para consultoria tributária assistida (S-A.2)."""

    regime: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=f"Regime tributário. Permitidos: {sorted(_ALLOWED_REGIMES)}",
    )
    cnae: str = Field(
        ...,
        min_length=4,
        max_length=16,
        description="Código CNAE da atividade principal (ex: 6201-5/01)",
    )
    porte: str = Field(
        ...,
        min_length=2,
        max_length=32,
        description=f"Porte da empresa. Permitidos: {sorted(_ALLOWED_PORTES)}",
    )
    pergunta: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Pergunta ou tema tributário a ser consultado",
    )
    n_citacoes: int = Field(3, ge=1, le=10, description="Número máximo de citações")

    @field_validator("regime")
    @classmethod
    def _validate_regime(cls, value: str) -> str:
        v = value.strip().lower()
        if v not in _ALLOWED_REGIMES:
            raise ValueError(
                f"Regime '{value}' inválido. Permitidos: {sorted(_ALLOWED_REGIMES)}"
            )
        return v

    @field_validator("porte")
    @classmethod
    def _validate_porte(cls, value: str) -> str:
        v = value.strip().lower()
        if v not in _ALLOWED_PORTES:
            raise ValueError(
                f"Porte '{value}' inválido. Permitidos: {sorted(_ALLOWED_PORTES)}"
            )
        return v


@router.get(
    "/due-diligence/{cnpj}",
    summary="Due Diligência Fiscal 360°",
    description=(
        "Relatório 360° jurídico+fiscal por CNPJ cruzando dados societários, "
        "situação fiscal (Receita Federal), pendências (CADIN) e protestos. "
        "Módulo: Cadastro e Risco (S-A.1)."
    ),
    responses={
        200: {"description": "Relatório gerado com sucesso"},
        400: {"description": "CNPJ inválido"},
        500: {"description": "Erro interno"},
    },
)
async def due_diligence_report(
    cnpj: str,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Gera relatório 360° jurídico+fiscal para o CNPJ informado."""

    if not _CNPJ_RE.match(cnpj.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Formato de CNPJ inválido. Use 14 dígitos ou XX.XXX.XXX/XXXX-XX."),
        )

    try:
        from src.fiscal.due_diligence import DueDiligenceService

        svc = DueDiligenceService()
        return await svc.generate_report(cnpj.strip(), principal_id=user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        correlation_id = uuid.uuid4().hex
        logger.error(
            "Due diligence falhou [%s]: %s", correlation_id, exc, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {correlation_id}",
        ) from exc


@router.post(
    "/consultoria",
    status_code=status.HTTP_200_OK,
    summary="Consultoria Tributária Assistida (RAG)",
    description=(
        "Gera parecer tributário preliminar com citações verificáveis via RAG. "
        "CJ-001: sem invenção de normas. Não substitui consultoria profissional. "
        "Módulo: Consultoria Tributária (S-A.2)."
    ),
    responses={
        200: {"description": "Parecer gerado com sucesso"},
        422: {"description": "Payload inválido"},
        500: {"description": "Erro interno"},
    },
)
async def consultoria_tributaria(
    request: ConsultoriaRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Gera parecer tributário assistido por RAG (S-A.2)."""

    try:
        from src.fiscal.consultoria import ConsultoriaService

        svc = ConsultoriaService()
        return await svc.gerar_parecer(
            regime=request.regime,
            cnae=request.cnae,
            porte=request.porte,
            pergunta=request.pergunta,
            n_citations=request.n_citacoes,
        )
    except HTTPException:
        raise
    except Exception as exc:
        correlation_id = uuid.uuid4().hex
        logger.error(
            "Consultoria tributária falhou [%s]: %s",
            correlation_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {correlation_id}",
        ) from exc
