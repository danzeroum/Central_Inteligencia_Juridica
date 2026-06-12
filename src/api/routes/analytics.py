"""Rotas de analytics fiscal — KPIs, histórico de apurações, achados e anomalias (S-E.1).

Todos os endpoints requerem autenticação e retornam 503 quando o banco de dados
não está disponível. Em ambiente de teste (sem DB) as rotas são acessíveis mas
retornam estruturas vazias a partir do guard de RuntimeError.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.api.auth import AuthManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fiscal/analytics", tags=["Fiscal Analytics"])


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────


class KpisResponse(BaseModel):
    total_escrituracoes: int = 0
    por_status: Dict[str, int] = {}
    por_tipo: Dict[str, int] = {}
    total_apuracoes: int = 0
    por_situacao: Dict[str, int] = {}
    total_achados: int = 0
    por_severidade: Dict[str, int] = {}


class HistoricoItem(BaseModel):
    periodo: str
    tributo: str
    total_debitos: str
    total_creditos: str
    saldo_apurado: str
    situacao: str
    escrituracao_id: str


class AchadosDistribuicao(BaseModel):
    total: int = 0
    por_severidade: Dict[str, int] = {}
    por_regra: Dict[str, int] = {}
    por_tipo_registro: Dict[str, int] = {}


class AnomaliaItem(BaseModel):
    escrituracao_id: str
    tipo: str
    periodo: Optional[str] = None
    divergencias_count: int
    severidade_maxima: str


class RetificacaoHistoricoItem(BaseModel):
    audit_id: str
    escrituracao_id: str
    operation: str
    status: str
    total_registros: Optional[int] = None
    total_bytes: Optional[int] = None
    user_id: Optional[str] = None
    created_at: str


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _safe_int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _count_dict(rows, key_fn) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for row in rows:
        k = key_fn(row)
        result[k] = result.get(k, 0) + 1
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/kpis",
    response_model=KpisResponse,
    summary="KPIs do módulo fiscal (S-E.1)",
    description=(
        "Agrega contadores principais: escriturações por status/tipo, "
        "apurações por situação e achados por severidade."
    ),
)
async def get_kpis(
    user_id: str = Depends(AuthManager.verify_token),
) -> KpisResponse:
    """KPIs agregados do pipeline fiscal."""
    try:
        from sqlalchemy import func, select

        from src.db.models import ApuracaoFiscal, EscrituracaoFiscal
        from src.db.session import get_async_session

        async with get_async_session() as session:
            # Escriturações
            escrit_rows = (
                (await session.execute(select(EscrituracaoFiscal))).scalars().all()
            )

            por_status = _count_dict(escrit_rows, lambda r: r.status or "desconhecido")
            por_tipo = _count_dict(escrit_rows, lambda r: r.tipo or "desconhecido")

            total_achados = 0
            por_severidade: Dict[str, int] = {}
            for e in escrit_rows:
                achados = (e.details or {}).get("achados", [])
                for a in achados:
                    total_achados += 1
                    sev = a.get("severidade", "desconhecido")
                    por_severidade[sev] = por_severidade.get(sev, 0) + 1

            # Apurações
            apur_rows = (await session.execute(select(ApuracaoFiscal))).scalars().all()
            por_situacao = _count_dict(apur_rows, lambda r: r.situacao or "equilibrado")

        return KpisResponse(
            total_escrituracoes=len(escrit_rows),
            por_status=por_status,
            por_tipo=por_tipo,
            total_apuracoes=len(apur_rows),
            por_situacao=por_situacao,
            total_achados=total_achados,
            por_severidade=por_severidade,
        )

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("get_kpis [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )


@router.get(
    "/apuracoes/historico",
    response_model=List[HistoricoItem],
    summary="Histórico de apurações por tributo e período (S-E.1)",
    description=(
        "Retorna evolução temporal das apurações filtrada por tributo e/ou período. "
        "Ordenada por periodo_competencia ascendente."
    ),
)
async def get_historico_apuracoes(
    tributo: Optional[str] = Query(
        None, description="Filtrar por tributo: ICMS, PIS, COFINS, ICMS-ST, IPI"
    ),
    periodo_inicio: Optional[str] = Query(None, description="Período início AAAA-MM"),
    periodo_fim: Optional[str] = Query(None, description="Período fim AAAA-MM"),
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(AuthManager.verify_token),
) -> List[HistoricoItem]:
    """Histórico de apurações com filtros opcionais."""
    try:
        from sqlalchemy import select

        from src.db.models import ApuracaoFiscal
        from src.db.session import get_async_session

        async with get_async_session() as session:
            stmt = select(ApuracaoFiscal).order_by(ApuracaoFiscal.periodo_competencia)

            if tributo:
                stmt = stmt.where(ApuracaoFiscal.tributo == tributo.upper())
            if periodo_inicio:
                stmt = stmt.where(ApuracaoFiscal.periodo_competencia >= periodo_inicio)
            if periodo_fim:
                stmt = stmt.where(ApuracaoFiscal.periodo_competencia <= periodo_fim)

            stmt = stmt.limit(limit)
            rows = (await session.execute(stmt)).scalars().all()

        return [
            HistoricoItem(
                periodo=r.periodo_competencia or "",
                tributo=r.tributo,
                total_debitos=r.total_debitos or "0",
                total_creditos=r.total_creditos or "0",
                saldo_apurado=r.saldo_apurado or "0",
                situacao=r.situacao or "equilibrado",
                escrituracao_id=str(r.escrituracao_id),
            )
            for r in rows
        ]

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("get_historico_apuracoes [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )


@router.get(
    "/achados/distribuicao",
    response_model=AchadosDistribuicao,
    summary="Distribuição de achados por severidade e regra (S-E.1)",
    description=(
        "Agrega todos os achados armazenados nas escriturações (campo details.achados) "
        "e retorna distribuição por severidade, regra e tipo de registro."
    ),
)
async def get_achados_distribuicao(
    user_id: str = Depends(AuthManager.verify_token),
) -> AchadosDistribuicao:
    """Distribuição de achados agregados de todas as escriturações."""
    try:
        from sqlalchemy import select

        from src.db.models import EscrituracaoFiscal
        from src.db.session import get_async_session

        async with get_async_session() as session:
            rows = (await session.execute(select(EscrituracaoFiscal))).scalars().all()

        total = 0
        por_severidade: Dict[str, int] = {}
        por_regra: Dict[str, int] = {}
        por_tipo_registro: Dict[str, int] = {}

        for e in rows:
            for a in (e.details or {}).get("achados", []):
                total += 1
                sev = a.get("severidade", "desconhecido")
                regra = a.get("regra_id", "desconhecido")
                tipo = a.get("tipo_registro", "desconhecido")
                por_severidade[sev] = por_severidade.get(sev, 0) + 1
                por_regra[regra] = por_regra.get(regra, 0) + 1
                por_tipo_registro[tipo] = por_tipo_registro.get(tipo, 0) + 1

        return AchadosDistribuicao(
            total=total,
            por_severidade=por_severidade,
            por_regra=por_regra,
            por_tipo_registro=por_tipo_registro,
        )

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("get_achados_distribuicao [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )


@router.get(
    "/anomalias",
    response_model=List[AnomaliaItem],
    summary="Escriturações com anomalias/divergências (S-E.1)",
    description=(
        "Lista escriturações com pelo menos um achado de severidade 'erro' ou 'aviso'. "
        "Ordenadas por número de divergências decrescente. Limite 50."
    ),
)
async def get_anomalias(
    severidade_minima: str = Query("aviso", description="'erro' ou 'aviso'"),
    user_id: str = Depends(AuthManager.verify_token),
) -> List[AnomaliaItem]:
    """Lista escriturações com anomalias detectadas."""
    if severidade_minima not in ("erro", "aviso", "informacao"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="severidade_minima deve ser 'erro', 'aviso' ou 'informacao'.",
        )

    filtro = {"erro", "aviso", "informacao"}
    if severidade_minima == "erro":
        filtro = {"erro"}
    elif severidade_minima == "aviso":
        filtro = {"erro", "aviso"}

    try:
        from sqlalchemy import select

        from src.db.models import EscrituracaoFiscal
        from src.db.session import get_async_session

        async with get_async_session() as session:
            rows = (await session.execute(select(EscrituracaoFiscal))).scalars().all()

        result: List[AnomaliaItem] = []
        for e in rows:
            achados = (e.details or {}).get("achados", [])
            candidatos = [a for a in achados if a.get("severidade") in filtro]
            if not candidatos:
                continue
            count_erro = sum(1 for a in candidatos if a.get("severidade") == "erro")
            sev_max = "erro" if count_erro > 0 else "aviso"
            periodo = None
            if e.details:
                periodo = e.details.get("periodo") or e.details.get("mes") or None
            result.append(
                AnomaliaItem(
                    escrituracao_id=str(e.id),
                    tipo=e.tipo or "desconhecido",
                    periodo=str(periodo) if periodo else None,
                    divergencias_count=len(candidatos),
                    severidade_maxima=sev_max,
                )
            )

        result.sort(key=lambda x: x.divergencias_count, reverse=True)
        return result[:50]

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("get_anomalias [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )


@router.get(
    "/retificacoes",
    response_model=List[RetificacaoHistoricoItem],
    summary="Histórico de retificações SPED geradas (S-D.2)",
    description=(
        "Lista todas as operações de geração de arquivo retificado registradas "
        "no FiscalAudit (operation='gerar_retificado'). Ordenadas por data decrescente."
    ),
)
async def get_historico_retificacoes(
    escrituracao_id: Optional[str] = Query(
        None, description="Filtrar por escrituração"
    ),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(AuthManager.verify_token),
) -> List[RetificacaoHistoricoItem]:
    """Histórico de retificações a partir do FiscalAudit."""
    try:
        from sqlalchemy import select

        from src.db.models import FiscalAudit
        from src.db.session import get_async_session

        async with get_async_session() as session:
            stmt = (
                select(FiscalAudit)
                .where(FiscalAudit.operation == "gerar_retificado")
                .order_by(FiscalAudit.created_at.desc())
                .limit(limit)
            )
            if escrituracao_id:
                stmt = stmt.where(FiscalAudit.entity_ref == escrituracao_id)

            rows = (await session.execute(stmt)).scalars().all()

        return [
            RetificacaoHistoricoItem(
                audit_id=str(r.id),
                escrituracao_id=r.entity_ref or "",
                operation=r.operation,
                status=r.status or "completed",
                total_registros=(r.details or {}).get("total_registros"),
                total_bytes=(r.details or {}).get("total_bytes"),
                user_id=(r.details or {}).get("user_id"),
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ]

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("get_historico_retificacoes [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )
