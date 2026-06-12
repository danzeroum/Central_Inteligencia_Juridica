"""Relatórios premium exportáveis (S-E.2).

Tipos de relatório disponíveis (hardcoded — sem SQL livre do usuário):
  - escrituracoes_status  : escriturações agrupadas por status e tipo
  - apuracoes_tributo     : apurações com totais por tributo e período
  - achados_severidade    : achados detalhados por severidade e regra
  - anomalias_completo    : escriturações com divergências, ordenadas por count

Exportação: JSON (padrão) ou CSV via query param ``formato=csv``.
Autenticação obrigatória + permissão ``reports:read``.
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.rbac import Principal, require_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fiscal/reports", tags=["Fiscal Reports"])

# ─────────────────────────────────────────────────────────────────────────────
# Catálogo de tipos de relatório
# ─────────────────────────────────────────────────────────────────────────────

REPORT_TYPES: Dict[str, Dict[str, str]] = {
    "escrituracoes_status": {
        "nome": "Escriturações por Status",
        "descricao": "Lista escriturações com status, tipo, período e achados.",
        "colunas": "id,tipo,status,periodo,total_achados,criado_em",
    },
    "apuracoes_tributo": {
        "nome": "Apurações por Tributo",
        "descricao": "Evolução de débitos, créditos e saldo por tributo e período.",
        "colunas": "id,tributo,periodo,total_debitos,total_creditos,saldo_apurado,situacao",
    },
    "achados_severidade": {
        "nome": "Achados por Severidade",
        "descricao": "Achados individuais extraídos das escriturações com regra e severidade.",
        "colunas": "escrituracao_id,severidade,regra_id,tipo_registro,descricao",
    },
    "anomalias_completo": {
        "nome": "Anomalias Completo",
        "descricao": "Escriturações com divergências detalhadas, ordenadas por count.",
        "colunas": "escrituracao_id,tipo,periodo,divergencias_count,severidade_maxima",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────


class ReportTipo(BaseModel):
    tipo: str
    nome: str
    descricao: str
    colunas: List[str]


class ReportResponse(BaseModel):
    report_id: str
    tipo: str
    total_linhas: int
    dados: List[Dict[str, Any]]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _to_csv(rows: List[Dict[str, Any]], columns: List[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


async def _fetch_escrituracoes(
    session,
    tributo: Optional[str],
    periodo_inicio: Optional[str],
    periodo_fim: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    from sqlalchemy import select

    from src.db.models import EscrituracaoFiscal

    stmt = select(EscrituracaoFiscal).limit(limit)
    if tributo:
        stmt = stmt.where(EscrituracaoFiscal.tipo == tributo.upper())
    rows = (await session.execute(stmt)).scalars().all()

    result = []
    for r in rows:
        achados = (r.details or {}).get("achados", [])
        result.append(
            {
                "id": str(r.id),
                "tipo": r.tipo or "",
                "status": r.status or "",
                "periodo": (r.details or {}).get("periodo", ""),
                "total_achados": len(achados),
                "criado_em": r.created_at.isoformat() if r.created_at else "",
            }
        )
    return result


async def _fetch_apuracoes(
    session,
    tributo: Optional[str],
    periodo_inicio: Optional[str],
    periodo_fim: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    from sqlalchemy import select

    from src.db.models import ApuracaoFiscal

    stmt = (
        select(ApuracaoFiscal).order_by(ApuracaoFiscal.periodo_competencia).limit(limit)
    )
    if tributo:
        stmt = stmt.where(ApuracaoFiscal.tributo == tributo.upper())
    if periodo_inicio:
        stmt = stmt.where(ApuracaoFiscal.periodo_competencia >= periodo_inicio)
    if periodo_fim:
        stmt = stmt.where(ApuracaoFiscal.periodo_competencia <= periodo_fim)
    rows = (await session.execute(stmt)).scalars().all()

    return [
        {
            "id": str(r.id),
            "tributo": r.tributo,
            "periodo": r.periodo_competencia or "",
            "total_debitos": r.total_debitos or "0",
            "total_creditos": r.total_creditos or "0",
            "saldo_apurado": r.saldo_apurado or "0",
            "situacao": r.situacao or "equilibrado",
        }
        for r in rows
    ]


async def _fetch_achados(session, limit: int) -> List[Dict[str, Any]]:
    from sqlalchemy import select

    from src.db.models import EscrituracaoFiscal

    rows = (
        (await session.execute(select(EscrituracaoFiscal).limit(limit))).scalars().all()
    )

    result = []
    for e in rows:
        for a in (e.details or {}).get("achados", []):
            result.append(
                {
                    "escrituracao_id": str(e.id),
                    "severidade": a.get("severidade", ""),
                    "regra_id": a.get("regra_id", ""),
                    "tipo_registro": a.get("tipo_registro", ""),
                    "descricao": a.get("descricao", ""),
                }
            )
            if len(result) >= limit:
                break
        if len(result) >= limit:
            break
    return result


async def _fetch_anomalias(session, limit: int) -> List[Dict[str, Any]]:
    from sqlalchemy import select

    from src.db.models import EscrituracaoFiscal

    rows = (await session.execute(select(EscrituracaoFiscal))).scalars().all()

    result = []
    for e in rows:
        achados = (e.details or {}).get("achados", [])
        candidatos = [a for a in achados if a.get("severidade") in ("erro", "aviso")]
        if not candidatos:
            continue
        sev_max = (
            "erro"
            if any(a.get("severidade") == "erro" for a in candidatos)
            else "aviso"
        )
        periodo = None
        if e.details:
            periodo = e.details.get("periodo") or e.details.get("mes")
        result.append(
            {
                "escrituracao_id": str(e.id),
                "tipo": e.tipo or "",
                "periodo": str(periodo) if periodo else "",
                "divergencias_count": len(candidatos),
                "severidade_maxima": sev_max,
            }
        )

    result.sort(key=lambda x: x["divergencias_count"], reverse=True)
    return result[:limit]


async def _generate_report(
    tipo: str,
    tributo: Optional[str],
    periodo_inicio: Optional[str],
    periodo_fim: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    from src.db.session import get_async_session

    async with get_async_session() as session:
        if tipo == "escrituracoes_status":
            return await _fetch_escrituracoes(
                session, tributo, periodo_inicio, periodo_fim, limit
            )
        elif tipo == "apuracoes_tributo":
            return await _fetch_apuracoes(
                session, tributo, periodo_inicio, periodo_fim, limit
            )
        elif tipo == "achados_severidade":
            return await _fetch_achados(session, limit)
        elif tipo == "anomalias_completo":
            return await _fetch_anomalias(session, limit)
        else:
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/tipos",
    response_model=List[ReportTipo],
    summary="Lista tipos de relatório disponíveis (S-E.2)",
)
async def list_tipos(
    principal=Depends(require_permissions("reports:read")),
) -> List[ReportTipo]:
    return [
        ReportTipo(
            tipo=k,
            nome=v["nome"],
            descricao=v["descricao"],
            colunas=v["colunas"].split(","),
        )
        for k, v in REPORT_TYPES.items()
    ]


@router.get(
    "/gerar",
    summary="Gera relatório premium (JSON ou CSV) (S-E.2)",
    description=(
        "Executa um relatório pré-definido com filtros opcionais. "
        "Use ``formato=csv`` para download direto em CSV."
    ),
)
async def gerar_relatorio(
    tipo: str = Query(..., description="Tipo de relatório (ver /tipos)"),
    tributo: Optional[str] = Query(None, description="Filtrar por tributo"),
    periodo_inicio: Optional[str] = Query(None, description="Período início AAAA-MM"),
    periodo_fim: Optional[str] = Query(None, description="Período fim AAAA-MM"),
    limit: int = Query(500, ge=1, le=2000),
    formato: str = Query("json", description="'json' ou 'csv'"),
    principal=Depends(require_permissions("reports:read")),
):
    if tipo not in REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tipo inválido. Válidos: {list(REPORT_TYPES)}",
        )
    if formato not in ("json", "csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="formato deve ser 'json' ou 'csv'",
        )

    try:
        dados = await _generate_report(
            tipo, tributo, periodo_inicio, periodo_fim, limit
        )
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("gerar_relatorio [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )

    if formato == "csv":
        columns = REPORT_TYPES[tipo]["colunas"].split(",")
        csv_content = _to_csv(dados, columns)
        filename = f"relatorio_{tipo}.csv"
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    report_id = uuid.uuid4().hex
    return ReportResponse(
        report_id=report_id, tipo=tipo, total_linhas=len(dados), dados=dados
    )
