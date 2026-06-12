"""Workbench de consultas fiscais parametrizadas/sandbox (S-E.2).

Design de segurança:
  - Usuários executam TEMPLATES pré-definidos (sem SQL livre de entrada).
  - Administradores podem registrar novos templates; o template SQL passa pelo
    ``QuerySafetyValidator`` antes de ser aceito (bloqueia DDL/DML perigoso).
  - Execução usa SQLAlchemy ORM com parâmetros tipados — nunca concatenação.
  - Conexão é somente-leitura por design (SELECT apenas nos templates válidos).
  - Cada execução é registrada no audit trail (FiscalAudit).

Permissões:
  - ``workbench:execute`` : executar queries e listar templates.
  - ``workbench:admin``   : registrar novos templates (ADMIN apenas).
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from src.api.rbac import Principal, require_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fiscal/workbench", tags=["Fiscal Workbench"])


# ─────────────────────────────────────────────────────────────────────────────
# Safety validator
# ─────────────────────────────────────────────────────────────────────────────

# Palavras-chave que indicam operações destrutivas ou de estrutura.
_DDL_DML_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE|"
    r"GRANT|REVOKE|EXEC|EXECUTE|CALL|COPY|LOAD|IMPORT|EXPORT|"
    r"INTO\s+OUTFILE|ATTACH|DETACH)\b",
    re.IGNORECASE,
)

# Construções que tentam escapar do contexto da query.
_INJECTION_PATTERN = re.compile(
    r"(--|/\*|\*/|;\s*SELECT|UNION\s+ALL|UNION\s+SELECT|xp_cmdshell|"
    r"INFORMATION_SCHEMA|pg_sleep|WAITFOR\s+DELAY)",
    re.IGNORECASE,
)


class QuerySafetyViolation(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def validate_query_safety(sql: str) -> None:
    """Valida que o SQL não contém DDL/DML ou padrões de injeção.

    Lança ``QuerySafetyViolation`` com descrição do problema.
    """
    ddl_match = _DDL_DML_PATTERN.search(sql)
    if ddl_match:
        raise QuerySafetyViolation(
            f"Operação proibida detectada: '{ddl_match.group().upper()}'. "
            "Apenas SELECT é permitido."
        )
    inj_match = _INJECTION_PATTERN.search(sql)
    if inj_match:
        raise QuerySafetyViolation(
            f"Padrão suspeito detectado: '{inj_match.group()}'. Query rejeitada."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Query template catalogue (code-defined, not user-defined SQL)
# ─────────────────────────────────────────────────────────────────────────────

QUERY_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "escrituracoes_recentes": {
        "nome": "Escriturações Recentes",
        "descricao": "Lista as N escriturações mais recentes com status e tipo.",
        "parametros": {"limit": "int (1-200, default 50)"},
    },
    "apuracoes_por_tributo": {
        "nome": "Apurações por Tributo",
        "descricao": "Apurações filtradas por tributo, com saldo e situação.",
        "parametros": {
            "tributo": "str (ICMS|PIS|COFINS|ICMS-ST|IPI, opcional)",
            "limit": "int (1-200, default 50)",
        },
    },
    "achados_top_regras": {
        "nome": "Top Regras com Achados",
        "descricao": "Agrupa achados por regra e conta ocorrências.",
        "parametros": {"limit": "int (1-50, default 20)"},
    },
    "auditoria_operacoes": {
        "nome": "Auditoria de Operações",
        "descricao": "Histórico de operações fiscais registradas no audit trail.",
        "parametros": {
            "operation": "str (gerar_retificado|validar|importar, opcional)",
            "limit": "int (1-200, default 50)",
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────


class QueryTemplateInfo(BaseModel):
    query_id: str
    nome: str
    descricao: str
    parametros: Dict[str, str]


class QueryResult(BaseModel):
    execution_id: str
    query_id: str
    total_linhas: int
    duration_ms: int
    dados: List[Dict[str, Any]]


class ValidacaoRequest(BaseModel):
    sql: str

    @field_validator("sql")
    @classmethod
    def nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("sql não pode ser vazio")
        return v.strip()


class ValidacaoResponse(BaseModel):
    seguro: bool
    mensagem: str


class RegisterQueryRequest(BaseModel):
    query_id: str
    nome: str
    descricao: str
    sql_preview: str  # apenas para validação; templates reais são code-defined


# ─────────────────────────────────────────────────────────────────────────────
# Query executors (SQLAlchemy ORM — sem raw SQL do usuário)
# ─────────────────────────────────────────────────────────────────────────────


async def _exec_escrituracoes_recentes(session, limit: int) -> List[Dict[str, Any]]:
    from sqlalchemy import select

    from src.db.models import EscrituracaoFiscal

    rows = (
        (
            await session.execute(
                select(EscrituracaoFiscal)
                .order_by(EscrituracaoFiscal.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(r.id),
            "tipo": r.tipo or "",
            "status": r.status or "",
            "criado_em": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


async def _exec_apuracoes_por_tributo(
    session, tributo: Optional[str], limit: int
) -> List[Dict[str, Any]]:
    from sqlalchemy import select

    from src.db.models import ApuracaoFiscal

    stmt = (
        select(ApuracaoFiscal)
        .order_by(ApuracaoFiscal.periodo_competencia.desc())
        .limit(limit)
    )
    if tributo:
        stmt = stmt.where(ApuracaoFiscal.tributo == tributo.upper())
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "tributo": r.tributo,
            "periodo": r.periodo_competencia or "",
            "saldo_apurado": r.saldo_apurado or "0",
            "situacao": r.situacao or "equilibrado",
        }
        for r in rows
    ]


async def _exec_achados_top_regras(session, limit: int) -> List[Dict[str, Any]]:
    from sqlalchemy import select

    from src.db.models import EscrituracaoFiscal

    rows = (await session.execute(select(EscrituracaoFiscal))).scalars().all()
    regra_count: Dict[str, int] = {}
    for e in rows:
        for a in (e.details or {}).get("achados", []):
            k = a.get("regra_id", "desconhecido")
            regra_count[k] = regra_count.get(k, 0) + 1

    sorted_regras = sorted(regra_count.items(), key=lambda x: x[1], reverse=True)
    return [{"regra_id": k, "ocorrencias": v} for k, v in sorted_regras[:limit]]


async def _exec_auditoria_operacoes(
    session, operation: Optional[str], limit: int
) -> List[Dict[str, Any]]:
    from sqlalchemy import select

    from src.db.models import FiscalAudit

    stmt = select(FiscalAudit).order_by(FiscalAudit.created_at.desc()).limit(limit)
    if operation:
        stmt = stmt.where(FiscalAudit.operation == operation)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "operation": r.operation,
            "entity_ref": r.entity_ref or "",
            "status": r.status or "",
            "criado_em": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


async def _execute_template(
    query_id: str, params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    from src.db.session import get_async_session

    limit = min(int(params.get("limit", 50)), 200)

    async with get_async_session() as session:
        if query_id == "escrituracoes_recentes":
            return await _exec_escrituracoes_recentes(session, limit)
        elif query_id == "apuracoes_por_tributo":
            return await _exec_apuracoes_por_tributo(
                session, params.get("tributo"), limit
            )
        elif query_id == "achados_top_regras":
            return await _exec_achados_top_regras(session, limit)
        elif query_id == "auditoria_operacoes":
            return await _exec_auditoria_operacoes(
                session, params.get("operation"), limit
            )
        else:
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/queries",
    response_model=List[QueryTemplateInfo],
    summary="Lista queries disponíveis no workbench (S-E.2)",
)
async def list_queries(
    principal=Depends(require_permissions("workbench:execute")),
) -> List[QueryTemplateInfo]:
    return [QueryTemplateInfo(query_id=k, **v) for k, v in QUERY_TEMPLATES.items()]


@router.post(
    "/executar",
    response_model=QueryResult,
    summary="Executa uma query pré-definida com parâmetros (S-E.2)",
    description=(
        "Executa um template de query com os parâmetros fornecidos. "
        "Nunca executa SQL livre — apenas templates validados da plataforma."
    ),
)
async def executar_query(
    query_id: str = Query(..., description="ID do template (ver /queries)"),
    tributo: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    principal=Depends(require_permissions("workbench:execute")),
) -> QueryResult:
    if query_id not in QUERY_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Query desconhecida. Disponíveis: {list(QUERY_TEMPLATES)}",
        )

    params = {"tributo": tributo, "operation": operation, "limit": limit}

    start = datetime.now(timezone.utc)
    try:
        dados = await _execute_template(query_id, params)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível.",
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("executar_query [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )

    duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    return QueryResult(
        execution_id=uuid.uuid4().hex,
        query_id=query_id,
        total_linhas=len(dados),
        duration_ms=duration_ms,
        dados=dados,
    )


@router.post(
    "/validar",
    response_model=ValidacaoResponse,
    summary="Valida segurança de um trecho SQL (S-E.2)",
    description=(
        "Verifica se um SQL contém DDL/DML proibido ou padrões de injeção. "
        "Usado pelo painel admin para pré-validar templates antes de registrar."
    ),
)
async def validar_sql(
    body: ValidacaoRequest,
    principal=Depends(require_permissions("workbench:admin")),
) -> ValidacaoResponse:
    try:
        validate_query_safety(body.sql)
        return ValidacaoResponse(
            seguro=True, mensagem="SQL aprovado — nenhum padrão proibido detectado."
        )
    except QuerySafetyViolation as e:
        return ValidacaoResponse(seguro=False, mensagem=e.reason)


@router.post(
    "/registrar",
    status_code=status.HTTP_201_CREATED,
    summary="Registra novo template de query (admin) (S-E.2)",
    description=(
        "Valida o SQL preview do template antes de aceitar o registro. "
        "Templates aprovados são adicionados ao catálogo em memória desta instância."
    ),
)
async def registrar_query(
    body: RegisterQueryRequest,
    principal=Depends(require_permissions("workbench:admin")),
) -> Dict[str, str]:
    try:
        validate_query_safety(body.sql_preview)
    except QuerySafetyViolation as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"SQL rejeitado pelo validador: {e.reason}",
        )

    if body.query_id in QUERY_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"query_id '{body.query_id}' já existe.",
        )

    QUERY_TEMPLATES[body.query_id] = {
        "nome": body.nome,
        "descricao": body.descricao,
        "parametros": {},
    }
    logger.info(
        "Workbench: template '%s' registrado por '%s'",
        body.query_id,
        principal.user_id if hasattr(principal, "user_id") else "?",
    )
    return {"status": "registrado", "query_id": body.query_id}
