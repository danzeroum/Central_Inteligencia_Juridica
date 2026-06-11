"""Rotas de sistema — métricas, health check e histórico de consultas."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Response

from src.api.rbac import Principal, current_principal
from src.api.routes._shared import decode_cursor, encode_cursor
from src.api.schemas.responses import HistoryResponse
from src.api.state import a2a_channel, supervisor_agent
from src.hitl.hitl_queue import get_hitl_queue
from src.utils.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expõe as métricas Prometheus do registry padrão (observabilidade)."""

    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/health")
async def health_check(
    verbose: bool = Query(False, description="Inclui detalhes completos")
) -> Dict[str, Any]:
    """Endpoint simples de saúde da aplicação."""

    timestamp = datetime.now(timezone.utc).isoformat()
    overall_status = "ok"

    if not verbose:
        return {"status": overall_status, "timestamp": timestamp}

    agent_stats = {
        "supervisor_active": True,
        "active_delegates": list(supervisor_agent.active_delegates.keys()),
    }

    metrics_snapshot = MetricsCollector.snapshot()
    a2a_status = await a2a_channel.health_check()

    db_status: Dict[str, Any] = {"status": "not_configured"}
    if os.getenv("DATABASE_URL"):
        try:
            from sqlalchemy import text as _sql_text

            from src.db.engine import get_async_engine

            _engine = get_async_engine()
            if _engine:
                async with _engine.connect() as _conn:
                    await _conn.execute(_sql_text("SELECT 1"))
                db_status = {"status": "ok"}
        except Exception as _db_exc:
            logger.warning("DB health check failed: %s", _db_exc)
            db_status = {"status": "error"}

    return {
        "status": overall_status,
        "timestamp": timestamp,
        "details": {
            "agents": agent_stats,
            "metrics": metrics_snapshot,
            "a2a": a2a_status,
            "database": db_status,
        },
    }


@router.get(
    "/api/v1/history",
    tags=["Consultas"],
    summary="Histórico de consultas do consulente",
    response_model=HistoryResponse,
)
async def list_history(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(
        None, description="Cursor opaco para a próxima página (vindo de uma resposta)"
    ),
    _principal: Principal = Depends(current_principal),
) -> HistoryResponse:
    """Lista as consultas processadas pelo Supervisor.

    Frente B (API-07): a fonte é o DecisionLedger (entradas TASK_COMPLETED),
    durável e compartilhado entre réplicas quando LEDGER_BACKEND=redis/postgres.
    """

    pending_actions = {
        req.get("action", {}).get("task")
        for req in get_hitl_queue().get_pending_requests()
    }

    entries = supervisor_agent.ledger.get_entries(decision_type="TASK_COMPLETED")
    entries.reverse()
    total = len(entries)

    offset = decode_cursor(cursor)
    page = entries[offset : offset + limit]

    history = []
    for entry in page:
        metadata = entry.get("metadata", {}) or {}
        task = metadata.get("task", "")
        in_review = task in pending_actions
        history.append(
            {
                "task": task,
                "operation": metadata.get("operation", "generic"),
                "tribunals": metadata.get("tribunals", []),
                "timestamp": entry.get("timestamp"),
                "status": "em_revisao_humana" if in_review else "concluida",
            }
        )

    next_offset = offset + len(page)
    next_cursor = encode_cursor(next_offset) if next_offset < total else None

    return HistoryResponse(
        count=len(history),
        total=total,
        cursor=next_cursor,
        history=history,
    )
