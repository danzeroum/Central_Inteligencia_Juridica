"""Endpoints do gerador PER/DCOMP (S-F.2).

RBAC:
  - per_dcomp:generate → ADMIN, OPERATOR (geração e validação de fichas)
  - per_dcomp:validate → ADMIN, OPERATOR, AUDITOR (validação somente)

Segurança:
  - LGPD: CNPJ armazenado e retornado apenas mascarado.
  - XML gerado contém apenas dados fornecidos pelo chamador (sem acesso a DB).
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator, model_validator

from src.api.rbac import Principal, require_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fiscal/per-dcomp", tags=["PER/DCOMP"])

# ─────────────────────────────────────────────────────────────────────────────
# Schemas de request / response
# ─────────────────────────────────────────────────────────────────────────────


class DebitoInput(BaseModel):
    tributo: str
    periodo_apuracao: str
    valor_debito: str
    descricao: Optional[str] = None

    @field_validator("valor_debito")
    @classmethod
    def valor_positivo(cls, v: str) -> str:
        try:
            if Decimal(v) <= Decimal("0"):
                raise ValueError("valor_debito deve ser maior que zero.")
        except InvalidOperation:
            raise ValueError("valor_debito deve ser um número decimal válido.")
        return v


class GerarRequest(BaseModel):
    # Contrato completo (original)
    cnpj_masked: Optional[str] = None
    nome_empresarial: Optional[str] = None
    tributo: Optional[str] = None
    periodo_apuracao: Optional[str] = None
    valor_credito: Optional[str] = None
    tipo_ficha: Optional[str] = None
    debitos: List[DebitoInput] = []
    # Contrato simplificado (frontend envia apenas escrituracao_id + tipo)
    escrituracao_id: Optional[str] = None
    tipo: Optional[str] = None

    @field_validator("valor_credito", mode="before")
    @classmethod
    def valor_nao_negativo(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            if Decimal(v) < Decimal("0"):
                raise ValueError("valor_credito não pode ser negativo.")
        except InvalidOperation:
            raise ValueError("valor_credito deve ser um número decimal válido.")
        return v


class ApuracaoInput(BaseModel):
    tributo: str
    periodo_competencia: str
    saldo_apurado: str
    situacao: str
    total_debitos: Optional[str] = None
    total_creditos: Optional[str] = None


class GerarDeApuracaoRequest(BaseModel):
    apuracao: ApuracaoInput
    cnpj_masked: str
    nome_empresarial: str
    tipo_ficha: Optional[str] = None
    debitos: List[DebitoInput] = []

    @field_validator("cnpj_masked")
    @classmethod
    def cnpj_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("cnpj_masked é obrigatório.")
        return v.strip()


class ValidarRequest(BaseModel):
    cnpj_masked: str
    nome_empresarial: str
    tributo: str
    periodo_apuracao: str
    valor_credito: str
    tipo_ficha: str
    debitos: List[DebitoInput] = []


class TipoFichaInfo(BaseModel):
    tipo: str
    nome: str
    descricao: str
    tributos_elegiveis: List[str]
    requer_debitos: bool


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo de tipos disponíveis
# ─────────────────────────────────────────────────────────────────────────────

_TIPOS_DISPONIVEIS: List[TipoFichaInfo] = [
    TipoFichaInfo(
        tipo="per_restituicao",
        nome="PER — Pedido de Restituição",
        descricao=(
            "Pedido de devolução em espécie de crédito de PIS/COFINS apurado "
            "no EFD-Contribuições. Indicado quando o contribuinte apura saldo credor "
            "e não tem débitos a compensar."
        ),
        tributos_elegiveis=["PIS", "COFINS"],
        requer_debitos=False,
    ),
    TipoFichaInfo(
        tipo="per_ressarcimento",
        nome="PER — Pedido de Ressarcimento",
        descricao=(
            "Pedido de ressarcimento de crédito de PIS/COFINS do regime não-cumulativo "
            "que não pode ser compensado (ex.: contribuinte com saídas predominantemente "
            "isentas ou para exportação)."
        ),
        tributos_elegiveis=["PIS", "COFINS"],
        requer_debitos=False,
    ),
    TipoFichaInfo(
        tipo="dcomp_credito_apuracao",
        nome="DCOMP — Compensação de Crédito de Apuração",
        descricao=(
            "Declaração de compensação de saldo credor de PIS/COFINS (apurado no "
            "EFD-Contribuições) contra débitos tributários vencidos ou a vencer. "
            "O valor dos débitos não pode superar o crédito disponível."
        ),
        tributos_elegiveis=["PIS", "COFINS"],
        requer_debitos=True,
    ),
    TipoFichaInfo(
        tipo="dcomp_pagamento_indevido",
        nome="DCOMP — Compensação de Pagamento Indevido",
        descricao=(
            "Declaração de compensação de crédito originado de pagamento indevido "
            "ou a maior de qualquer tributo federal. "
            "Requer processo administrativo ou decisão judicial."
        ),
        tributos_elegiveis=["PIS", "COFINS", "IRPJ", "CSLL", "IPI"],
        requer_debitos=True,
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _stub_ficha_de_escrituracao(
    escrituracao_id: str, tipo: Optional[str]
) -> Dict[str, Any]:
    """Retorna ficha stub quando apenas escrituracao_id é fornecido (sem dados completos)."""
    import datetime

    ficha_id = str(uuid.uuid4())
    tipo_str = tipo or "dcomp_credito_apuracao"
    periodo = datetime.date.today().strftime("%Y-%m")
    return {
        "ficha_id": ficha_id,
        "tipo": tipo_str,
        "status": "em_elaboracao",
        "escrituracao_id": escrituracao_id,
        "numero": f"DCOMP-{ficha_id[:8].upper()}",
        "periodo": periodo,
        "periodo_competencia": periodo,
        "origem": "EFD-Contribuições",
        "tipo_credito": "PIS/COFINS",
        "credito": "0.00",
        "valor_credito": "0.00",
        "selic": None,
        "total": "0.00",
        "valor_total": "0.00",
        "situacao": "em_elaboracao",
        "is_stub": True,
        "xml_b64": None,
    }


def _build_debitos_dcomp(inputs: List[DebitoInput]):
    from src.fiscal.per_dcomp.models import DebitoCompensacao, TipoTributo

    debitos = []
    for d in inputs:
        try:
            tributo = TipoTributo(d.tributo.upper())
        except ValueError:
            tributo = TipoTributo.PIS
        debitos.append(
            DebitoCompensacao(
                tributo=tributo,
                periodo_apuracao=d.periodo_apuracao,
                valor_debito=Decimal(d.valor_debito),
                descricao=d.descricao,
            )
        )
    return debitos


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tipos",
    response_model=List[TipoFichaInfo],
    summary="Lista tipos de PER/DCOMP disponíveis (S-F.2)",
)
async def listar_tipos(
    principal: Principal = Depends(require_permissions("per_dcomp:validate")),
) -> List[TipoFichaInfo]:
    return _TIPOS_DISPONIVEIS


@router.post(
    "/gerar",
    status_code=status.HTTP_201_CREATED,
    summary="Gera ficha PER/DCOMP a partir de parâmetros diretos (S-F.2)",
)
async def gerar_ficha(
    body: GerarRequest,
    principal: Principal = Depends(require_permissions("per_dcomp:generate")),
) -> Dict[str, Any]:
    # Contrato simplificado: apenas escrituracao_id + tipo (frontend fiscal flow)
    if body.escrituracao_id and not body.cnpj_masked:
        logger.info(
            "per_dcomp gerar stub: escrituracao_id=%s tipo=%s user=%s",
            body.escrituracao_id,
            body.tipo,
            principal.user_id,
        )
        return _stub_ficha_de_escrituracao(
            body.escrituracao_id, body.tipo or body.tipo_ficha
        )

    # Contrato completo: valida campos obrigatórios
    if not body.cnpj_masked:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Forneça cnpj_masked + campos completos, ou apenas escrituracao_id.",
        )

    from src.fiscal.per_dcomp.factory import PERDCOMPFactory
    from src.fiscal.per_dcomp.models import TipoFicha, TipoTributo
    from src.fiscal.per_dcomp.serializer import to_xml_b64
    from src.fiscal.per_dcomp.validator import PERDCOMPValidator

    try:
        tributo = TipoTributo(body.tributo.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"tributo '{body.tributo}' inválido. Valores aceitos: {[t.value for t in TipoTributo]}",
        )

    tipo_ficha = None
    if body.tipo_ficha:
        try:
            tipo_ficha = TipoFicha(body.tipo_ficha)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"tipo_ficha '{body.tipo_ficha}' inválido.",
            )

    debitos = _build_debitos_dcomp(body.debitos)

    try:
        if (
            tipo_ficha
            in (
                None,
                TipoFicha.PER_RESTITUICAO,
            )
            and not debitos
        ):
            ficha = PERDCOMPFactory.create_per_restituicao(
                cnpj_masked=body.cnpj_masked,
                nome_empresarial=body.nome_empresarial,
                tributo_str=tributo,
                periodo_apuracao=body.periodo_apuracao,
                valor_credito=Decimal(body.valor_credito),
            )
        elif tipo_ficha == TipoFicha.PER_RESSARCIMENTO:
            ficha = PERDCOMPFactory.create_per_ressarcimento(
                cnpj_masked=body.cnpj_masked,
                nome_empresarial=body.nome_empresarial,
                tributo_str=tributo,
                periodo_apuracao=body.periodo_apuracao,
                valor_credito=Decimal(body.valor_credito),
            )
        else:
            ficha = PERDCOMPFactory.create_dcomp(
                cnpj_masked=body.cnpj_masked,
                nome_empresarial=body.nome_empresarial,
                tributo_str=tributo,
                periodo_apuracao=body.periodo_apuracao,
                valor_credito=Decimal(body.valor_credito),
                debitos=debitos,
            )

        ficha = PERDCOMPValidator.validate(ficha)
        result = ficha.to_dict()
        result["xml_b64"] = to_xml_b64(ficha)
        logger.info(
            "per_dcomp gerar: ficha_id=%s tipo=%s status=%s user=%s",
            ficha.ficha_id,
            ficha.tipo.value,
            ficha.status.value,
            principal.user_id,
        )
        return result
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("per_dcomp gerar [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar ficha. Referência: {cid}",
        )


@router.post(
    "/gerar-de-apuracao",
    status_code=status.HTTP_201_CREATED,
    summary="Gera ficha PER/DCOMP a partir de dados de apuração SPED (S-F.2)",
)
async def gerar_de_apuracao(
    body: GerarDeApuracaoRequest,
    principal: Principal = Depends(require_permissions("per_dcomp:generate")),
) -> Dict[str, Any]:
    from src.fiscal.per_dcomp.factory import PERDCOMPFactory
    from src.fiscal.per_dcomp.models import TipoFicha
    from src.fiscal.per_dcomp.serializer import to_xml_b64
    from src.fiscal.per_dcomp.validator import PERDCOMPValidator

    tipo_ficha = None
    if body.tipo_ficha:
        try:
            tipo_ficha = TipoFicha(body.tipo_ficha)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"tipo_ficha '{body.tipo_ficha}' inválido.",
            )

    debitos = _build_debitos_dcomp(body.debitos)
    apuracao_dict = body.apuracao.model_dump()

    try:
        ficha = PERDCOMPFactory.create_from_apuracao(
            apuracao=apuracao_dict,
            cnpj_masked=body.cnpj_masked,
            nome_empresarial=body.nome_empresarial,
            debitos=debitos or None,
            tipo_ficha=tipo_ficha,
        )
        ficha = PERDCOMPValidator.validate(ficha)
        result = ficha.to_dict()
        result["xml_b64"] = to_xml_b64(ficha)
        logger.info(
            "per_dcomp gerar-de-apuracao: ficha_id=%s tipo=%s status=%s user=%s",
            ficha.ficha_id,
            ficha.tipo.value,
            ficha.status.value,
            principal.user_id,
        )
        return result
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("per_dcomp gerar-de-apuracao [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar ficha. Referência: {cid}",
        )


@router.post(
    "/validar",
    summary="Valida uma ficha PER/DCOMP sem persistir (S-F.2)",
)
async def validar_ficha(
    body: ValidarRequest,
    principal: Principal = Depends(require_permissions("per_dcomp:validate")),
) -> Dict[str, Any]:
    from src.fiscal.per_dcomp.factory import PERDCOMPFactory
    from src.fiscal.per_dcomp.models import TipoFicha, TipoTributo
    from src.fiscal.per_dcomp.validator import PERDCOMPValidator

    try:
        tributo = TipoTributo(body.tributo.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"tributo '{body.tributo}' inválido.",
        )
    try:
        tipo_ficha = TipoFicha(body.tipo_ficha)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"tipo_ficha '{body.tipo_ficha}' inválido.",
        )

    debitos = _build_debitos_dcomp(body.debitos)

    try:
        ficha = PERDCOMPFactory.create_per_restituicao(
            cnpj_masked=body.cnpj_masked,
            nome_empresarial=body.nome_empresarial,
            tributo_str=tributo,
            periodo_apuracao=body.periodo_apuracao,
            valor_credito=Decimal(body.valor_credito),
        )
        ficha.tipo = tipo_ficha
        ficha.debitos = debitos

        erros_sint = PERDCOMPValidator.validate_sintatica(ficha)
        erros_sem = PERDCOMPValidator.validate_semantica(ficha)
        _, avisos = PERDCOMPValidator._validate_semantica_com_avisos(ficha)

        valido = not (erros_sint + erros_sem)
        return {
            "valido": valido,
            "erros_sintaticos": erros_sint,
            "erros_semanticos": erros_sem,
            "avisos": avisos,
        }
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("per_dcomp validar [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao validar ficha. Referência: {cid}",
        )
