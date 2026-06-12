"""Rotas do módulo Fiscal — Bloco A + C (S-A.1/A.2 + S-C.2/S-C.3)."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
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


# ─────────────────────────────────────────────────────────────────────────────
# S-C.2 Parte A — status e achados de escrituração
# ─────────────────────────────────────────────────────────────────────────────


class EscrituracaoStatusResponse(BaseModel):
    id: str
    status: str
    tipo: str
    origem: str
    correlation_id: Optional[str] = None
    total_registros: Optional[int] = None
    registros_por_bloco: Optional[Dict[str, int]] = None
    total_erros: Optional[int] = None
    total_avisos: Optional[int] = None
    created_at: str
    updated_at: str


class AchadoItem(BaseModel):
    regra_id: str
    severidade: str
    campo: str
    descricao: str
    tipo_registro: str
    numero_linha: int
    valor_encontrado: Optional[Any] = None
    dica: str = ""


class AchadosResponse(BaseModel):
    escrituracao_id: str
    total: int
    offset: int
    limit: int
    achados: List[AchadoItem]


@router.get(
    "/escrituracoes/{escrituracao_id}",
    response_model=EscrituracaoStatusResponse,
    summary="Status da escrituração fiscal",
    description="Retorna status, contadores e correlation_id de uma escrituração.",
)
async def get_escrituracao_status(
    escrituracao_id: str,
    user_id: str = Depends(AuthManager.verify_token),
) -> EscrituracaoStatusResponse:
    """Consulta status de processamento de uma escrituração fiscal."""
    try:
        eid = uuid.UUID(escrituracao_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ID de escrituração inválido.",
        )

    try:
        from src.db.session import get_async_session
        from src.fiscal.repository import EscrituracaoRepository

        async with get_async_session() as session:
            repo = EscrituracaoRepository(session)
            escrit = await repo.get(eid)
            if escrit is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Escrituração {escrituracao_id} não encontrada.",
                )
            details = escrit.details or {}
            achados = details.get("achados", [])
            erros = sum(1 for a in achados if a.get("severidade") == "erro")
            avisos = sum(1 for a in achados if a.get("severidade") == "aviso")
            response = EscrituracaoStatusResponse(
                id=str(escrit.id),
                status=escrit.status,
                tipo=escrit.tipo,
                origem=escrit.origem,
                correlation_id=details.get("correlation_id"),
                total_registros=details.get("total_registros"),
                registros_por_bloco=details.get("registros_por_bloco"),
                total_erros=erros,
                total_avisos=avisos,
                created_at=escrit.created_at.isoformat(),
                updated_at=escrit.updated_at.isoformat(),
            )
    except HTTPException:
        raise
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("get_escrituracao_status [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )

    return response


@router.get(
    "/escrituracoes/{escrituracao_id}/achados",
    response_model=AchadosResponse,
    summary="Achados de regras fiscais",
    description="Lista paginada de achados do motor de regras para uma escrituração.",
)
async def get_escrituracao_achados(
    escrituracao_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user_id: str = Depends(AuthManager.verify_token),
) -> AchadosResponse:
    """Retorna achados (violações de regras fiscais) de uma escrituração."""
    try:
        eid = uuid.UUID(escrituracao_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ID de escrituração inválido.",
        )

    try:
        from src.db.session import get_async_session
        from src.fiscal.repository import EscrituracaoRepository

        async with get_async_session() as session:
            repo = EscrituracaoRepository(session)
            escrit = await repo.get(eid)
            if escrit is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Escrituração {escrituracao_id} não encontrada.",
                )
            all_achados = (escrit.details or {}).get("achados", [])
            page = all_achados[offset : offset + limit]
            response = AchadosResponse(
                escrituracao_id=escrituracao_id,
                total=len(all_achados),
                offset=offset,
                limit=limit,
                achados=[AchadoItem(**a) for a in page],
            )
    except HTTPException:
        raise
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("get_escrituracao_achados [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )

    return response


# ─────────────────────────────────────────────────────────────────────────────
# S-C.2 Parte B — apuração ICMS/PIS/COFINS
# ─────────────────────────────────────────────────────────────────────────────


class ApuracaoTriggerResponse(BaseModel):
    escrituracao_id: str
    aprovado: bool
    resumo: str
    items: List[Dict[str, Any]]


class ApuracaoListItem(BaseModel):
    id: str
    escrituracao_id: str
    tributo: str
    periodo_competencia: Optional[str]
    total_debitos: str
    total_creditos: str
    saldo_apurado: str
    situacao: str
    total_divergencias: int
    created_at: str


@router.post(
    "/escrituracoes/{escrituracao_id}/apuracao",
    response_model=ApuracaoTriggerResponse,
    status_code=status.HTTP_200_OK,
    summary="Calcular apuração fiscal",
    description=(
        "Calcula e persiste apuração ICMS/PIS/COFINS a partir dos registros "
        "canônicos da escrituração. Pode ser chamado múltiplas vezes (idempotente)."
    ),
)
async def calcular_apuracao(
    escrituracao_id: str,
    user_id: str = Depends(AuthManager.verify_token),
) -> ApuracaoTriggerResponse:
    """Calcula apuração para a escrituração fiscal indicada."""
    try:
        eid = uuid.UUID(escrituracao_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ID de escrituração inválido.",
        )

    try:
        from src.db.models import ApuracaoFiscal
        from src.db.session import get_async_session
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.base import SpedRecord
        from src.fiscal.repository import (
            ApuracaoFiscalRepository,
            EscrituracaoRepository,
            PeriodoFiscalRepository,
            RegistroFiscalRepository,
        )
        from datetime import datetime, timezone

        async with get_async_session() as session:
            async with session.begin():
                from sqlalchemy import delete as sa_delete

                escrit_repo = EscrituracaoRepository(session)
                escrit = await escrit_repo.get(eid)
                if escrit is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Escrituração {escrituracao_id} não encontrada.",
                    )

                # Reconstrói SpedRecord a partir dos RegistroFiscal persistidos
                reg_repo = RegistroFiscalRepository(session)
                registros_db = await reg_repo.list_by_escrituracao(eid, limit=5000)

                records = [
                    SpedRecord(
                        bloco=r.bloco,
                        tipo_registro=r.tipo_registro,
                        campos=r.dados or {},
                        numero_linha=r.numero_linha,
                    )
                    for r in registros_db
                ]

                # Calcula apuração (puro Python — sem acesso a DB)
                engine = get_apuracao_engine()
                resultado = engine.calcular(records, tipo=escrit.tipo)

                # Idempotência: apaga e regrava no mesmo session.begin()
                await session.execute(
                    sa_delete(ApuracaoFiscal).where(
                        ApuracaoFiscal.escrituracao_id == eid
                    )
                )
                apuracao_repo = ApuracaoFiscalRepository(session)
                periodo_repo = PeriodoFiscalRepository(session)

                for item in resultado.items:
                    periodo_str = item.periodo or ""
                    try:
                        ano_str, mes_str = periodo_str.split("-")
                        ano = int(ano_str)
                        mes: Optional[int] = int(mes_str)
                    except (ValueError, AttributeError):
                        ano = datetime.now(timezone.utc).year
                        mes = None

                    periodo = await periodo_repo.get_or_create(ano=ano, mes=mes)
                    apuracao_obj = ApuracaoFiscal(
                        escrituracao_id=eid,
                        periodo_id=periodo.id,
                        tributo=item.tributo,
                        periodo_competencia=item.periodo or None,
                        total_debitos=str(item.total_debitos),
                        total_creditos=str(item.total_creditos),
                        saldo_credor_anterior=str(item.saldo_credor_anterior),
                        saldo_apurado=str(item.saldo_apurado),
                        situacao=item.situacao,
                        divergencias=[d.to_dict() for d in item.divergencias],
                        detalhes=item.detalhes,
                    )
                    await apuracao_repo.save(apuracao_obj)

        return ApuracaoTriggerResponse(
            escrituracao_id=escrituracao_id,
            aprovado=resultado.aprovado,
            resumo=resultado.resumo,
            items=[i.to_dict() for i in resultado.items],
        )

    except HTTPException:
        raise
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("calcular_apuracao [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )


@router.get(
    "/apuracoes",
    response_model=List[ApuracaoListItem],
    summary="Listar apurações fiscais",
    description="Lista apurações calculadas, opcionalmente filtradas por período e tributo.",
)
async def listar_apuracoes(
    periodo: Optional[str] = Query(
        None,
        description="Competência AAAA-MM (ex: 2025-01)",
        pattern=r"^\d{4}-\d{2}$",
    ),
    tributo: Optional[str] = Query(None, description="ICMS | PIS | COFINS"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(AuthManager.verify_token),
) -> List[ApuracaoListItem]:
    """Lista apurações com filtros opcionais."""
    try:
        from src.db.models import ApuracaoFiscal, PeriodoFiscal
        from src.db.session import get_async_session
        from sqlalchemy import select

        async with get_async_session() as session:
            stmt = (
                select(ApuracaoFiscal)
                .order_by(ApuracaoFiscal.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            if tributo:
                stmt = stmt.where(ApuracaoFiscal.tributo == tributo.upper())
            if periodo:
                stmt = stmt.where(ApuracaoFiscal.periodo_competencia == periodo)

            result = await session.execute(stmt)
            items = [
                ApuracaoListItem(
                    id=str(a.id),
                    escrituracao_id=str(a.escrituracao_id),
                    tributo=a.tributo,
                    periodo_competencia=a.periodo_competencia,
                    total_debitos=a.total_debitos,
                    total_creditos=a.total_creditos,
                    saldo_apurado=a.saldo_apurado,
                    situacao=a.situacao,
                    total_divergencias=len(a.divergencias or []),
                    created_at=a.created_at.isoformat(),
                )
                for a in result.scalars().all()
            ]

        return items

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("listar_apuracoes [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# S-C.3 — Registros da escrituração + Edição em lote transacional
# ─────────────────────────────────────────────────────────────────────────────

_CAMPOS_PII = frozenset({"cnpj", "cpf", "cod_part", "nome"})


def _mask_campos(campos: Dict[str, Any]) -> Dict[str, Any]:
    """Mascara campos PII (LGPD) em dados de registros fiscais."""
    result: Dict[str, Any] = {}
    for k, v in campos.items():
        if k.lower() in _CAMPOS_PII and v:
            s = str(v)
            result[k] = (
                s[:2] + "*" * max(0, len(s) - 4) + s[-2:] if len(s) > 4 else "****"
            )
        else:
            result[k] = v
    return result


class RegistroFiscalItem(BaseModel):
    id: str
    tipo_registro: str
    bloco: str
    numero_linha: int
    campos: Dict[str, Any]


class RegistrosResponse(BaseModel):
    escrituracao_id: str
    total: int
    offset: int
    limit: int
    registros: List[RegistroFiscalItem]


@router.get(
    "/escrituracoes/{escrituracao_id}/registros",
    response_model=RegistrosResponse,
    summary="Listar registros fiscais de uma escrituração",
    description=(
        "Retorna registros canônicos parseados de uma escrituração. "
        "Campos PII mascarados (LGPD)."
    ),
)
async def listar_registros(
    escrituracao_id: str,
    tipo_registro: Optional[str] = Query(
        None, description="Filtrar por tipo (ex: C100)"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user_id: str = Depends(AuthManager.verify_token),
) -> RegistrosResponse:
    """Lista registros canônicos de uma escrituração com campos PII mascarados."""
    try:
        eid = uuid.UUID(escrituracao_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ID de escrituração inválido.",
        )

    try:
        from src.db.session import get_async_session
        from src.fiscal.repository import (
            EscrituracaoRepository,
            RegistroFiscalRepository,
        )

        async with get_async_session() as session:
            escrit_repo = EscrituracaoRepository(session)
            escrit = await escrit_repo.get(eid)
            if escrit is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Escrituração {escrituracao_id} não encontrada.",
                )
            reg_repo = RegistroFiscalRepository(session)
            registros_db = await reg_repo.list_by_escrituracao(
                eid,
                tipo_registro=tipo_registro,
                limit=limit,
                offset=offset,
            )
            total = await reg_repo.count_by_escrituracao(eid)

        return RegistrosResponse(
            escrituracao_id=escrituracao_id,
            total=total,
            offset=offset,
            limit=limit,
            registros=[
                RegistroFiscalItem(
                    id=str(r.id),
                    tipo_registro=r.tipo_registro,
                    bloco=r.bloco,
                    numero_linha=r.numero_linha,
                    campos=_mask_campos(r.dados or {}),
                )
                for r in registros_db
            ],
        )

    except HTTPException:
        raise
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("listar_registros [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )


class OperacaoLote(BaseModel):
    registro_id: str = Field(..., description="UUID do RegistroFiscal a editar")
    campos: Dict[str, Any] = Field(
        ..., description="Campos a atualizar (merge parcial)"
    )


class LoteRequest(BaseModel):
    operacoes: List[OperacaoLote] = Field(..., min_length=1, max_length=500)
    dry_run: bool = Field(False, description="Se true, simula sem persistir")


class DiffRegistro(BaseModel):
    registro_id: str
    tipo_registro: str
    campos_antes: Dict[str, Any]
    campos_depois: Dict[str, Any]


class LoteResponse(BaseModel):
    escrituracao_id: str
    dry_run: bool
    operacoes_aplicadas: int
    diff: List[DiffRegistro]
    achados_antes: List[AchadoItem]
    achados_depois: List[AchadoItem]


@router.post(
    "/escrituracoes/{escrituracao_id}/registros/lote",
    response_model=LoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Edição em lote de registros fiscais (S-C.3)",
    description=(
        "Edita campos de registros canônicos em transação única. "
        "dry_run=true: preview com diff + revalidação simulada, sem persistir. "
        "dry_run=false: aplica tudo-ou-nada + FiscalAudit + revalidação automática. "
        "Bloqueado se escrituração estiver em status 'processando'. "
        "Campos PII mascarados na resposta (LGPD)."
    ),
)
async def editar_registros_lote(
    escrituracao_id: str,
    request: LoteRequest,
    user_id: str = Depends(AuthManager.verify_token),
) -> LoteResponse:
    """Edição em lote transacional de registros fiscais."""
    try:
        eid = uuid.UUID(escrituracao_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ID de escrituração inválido.",
        )

    try:
        from sqlalchemy import select
        from src.db.models import EscrituracaoFiscal, FiscalAudit, RegistroFiscal
        from src.db.session import get_async_session
        from src.fiscal.parser.base import SpedRecord
        from src.fiscal.repository import (
            EscrituracaoRepository,
            RegistroFiscalRepository,
        )
        from src.fiscal.rules_engine import get_rules_engine

        async with get_async_session() as session:
            async with session.begin():
                # ── Verificações de pré-condição ──────────────────────────────
                escrit_repo = EscrituracaoRepository(session)
                escrit = await escrit_repo.get(eid)
                if escrit is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Escrituração {escrituracao_id} não encontrada.",
                    )
                if escrit.status == "processando":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Escrituração em processamento — aguarde conclusão.",
                    )

                # ── Carrega registros solicitados ─────────────────────────────
                reg_ids_req = []
                for op in request.operacoes:
                    try:
                        reg_ids_req.append(uuid.UUID(op.registro_id))
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"registro_id inválido: {op.registro_id!r}",
                        )

                stmt = select(RegistroFiscal).where(
                    RegistroFiscal.escrituracao_id == eid,
                    RegistroFiscal.id.in_(reg_ids_req),
                )
                result = await session.execute(stmt)
                regs_db = {r.id: r for r in result.scalars().all()}

                missing = [str(rid) for rid in reg_ids_req if rid not in regs_db]
                if missing:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Registros não encontrados: {missing}",
                    )

                # ── Constrói diff e aplica mudanças em memória ────────────────
                diff: List[DiffRegistro] = []
                regs_modificados: Dict[uuid.UUID, Dict[str, Any]] = {}

                for op in request.operacoes:
                    rid = uuid.UUID(op.registro_id)
                    reg = regs_db[rid]
                    campos_antes = dict(reg.dados or {})
                    campos_depois = {**campos_antes, **op.campos}
                    diff.append(
                        DiffRegistro(
                            registro_id=str(rid),
                            tipo_registro=reg.tipo_registro,
                            campos_antes=_mask_campos(campos_antes),
                            campos_depois=_mask_campos(campos_depois),
                        )
                    )
                    regs_modificados[rid] = campos_depois

                # ── Revalidação (antes e depois) ──────────────────────────────
                reg_repo = RegistroFiscalRepository(session)
                todos_registros_db = await reg_repo.list_by_escrituracao(
                    eid, limit=5000
                )

                def _build_records(
                    registros: list, overrides: Dict[uuid.UUID, Dict[str, Any]]
                ) -> List[SpedRecord]:
                    return [
                        SpedRecord(
                            bloco=r.bloco,
                            tipo_registro=r.tipo_registro,
                            campos=overrides.get(r.id, r.dados or {}),
                            numero_linha=r.numero_linha,
                        )
                        for r in registros
                    ]

                rules_engine = get_rules_engine(
                    escrit.details.get("regime", "lucro_real")
                    if escrit.details
                    else "lucro_real"
                )

                records_antes = _build_records(todos_registros_db, {})
                result_antes = rules_engine.validate(records_antes)

                records_depois = _build_records(todos_registros_db, regs_modificados)
                result_depois = rules_engine.validate(records_depois)

                achados_antes = [
                    AchadoItem(
                        regra_id=r.regra_id,
                        severidade=r.severidade.value,
                        campo=r.campo,
                        descricao=r.descricao,
                        tipo_registro=r.tipo_registro,
                        numero_linha=r.numero_linha,
                        valor_encontrado=r.valor_encontrado,
                        dica=r.dica,
                    )
                    for r in result_antes.resultados
                ]
                achados_depois = [
                    AchadoItem(
                        regra_id=r.regra_id,
                        severidade=r.severidade.value,
                        campo=r.campo,
                        descricao=r.descricao,
                        tipo_registro=r.tipo_registro,
                        numero_linha=r.numero_linha,
                        valor_encontrado=r.valor_encontrado,
                        dica=r.dica,
                    )
                    for r in result_depois.resultados
                ]

                if not request.dry_run:
                    # ── Persiste mudanças ──────────────────────────────────────
                    from datetime import datetime, timezone

                    for op in request.operacoes:
                        rid = uuid.UUID(op.registro_id)
                        reg = regs_db[rid]
                        reg.dados = regs_modificados[rid]

                    # Atualiza achados na escrituração
                    details = dict(escrit.details or {})
                    details["achados"] = [
                        {
                            "regra_id": a.regra_id,
                            "severidade": a.severidade,
                            "campo": a.campo,
                            "descricao": a.descricao,
                            "tipo_registro": a.tipo_registro,
                            "numero_linha": a.numero_linha,
                            "valor_encontrado": a.valor_encontrado,
                            "dica": a.dica,
                        }
                        for a in achados_depois
                    ]
                    escrit.details = details
                    escrit.updated_at = datetime.now(timezone.utc)

                    # FiscalAudit
                    audit = FiscalAudit(
                        operation="batch_edit",
                        entity_type=escrit.tipo,
                        entity_ref=str(eid),
                        status="completed",
                        details={
                            "user_id": user_id,
                            "operacoes": len(request.operacoes),
                            "achados_antes": len(achados_antes),
                            "achados_depois": len(achados_depois),
                        },
                    )
                    session.add(audit)

        return LoteResponse(
            escrituracao_id=escrituracao_id,
            dry_run=request.dry_run,
            operacoes_aplicadas=len(request.operacoes),
            diff=diff,
            achados_antes=achados_antes,
            achados_depois=achados_depois,
        )

    except HTTPException:
        raise
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("editar_registros_lote [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )
