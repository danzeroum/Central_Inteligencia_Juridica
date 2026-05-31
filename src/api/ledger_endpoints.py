"""FastAPI endpoints para leitura e exportação do Decision Ledger.

Expõe a trilha de auditoria imutável (quem decidiu o quê, quando e sob qual
regra) para a tela de Auditoria — base de conformidade LGPD. Apenas leitura e
exportação sobre o estado já persistido por :class:`DecisionLedger`.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from src.utils.ledger import get_ledger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ledger", tags=["Ledger"])

# Mesma instância (singleton) usada pelos endpoints HITL para registrar decisões.
ledger = get_ledger()


@router.get("", summary="Lista entradas da trilha de auditoria")
async def list_ledger(
    agent_type: Optional[str] = Query(None, description="Filtra por tipo de agente"),
    decision_type: Optional[str] = Query(
        None, description="Filtra por tipo de decisão"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de entradas"),
) -> Dict[str, Any]:
    """Retorna as entradas mais recentes do Decision Ledger (ordem cronológica)."""

    entries = ledger.get_entries(
        agent_type=agent_type,
        decision_type=decision_type,
        limit=limit,
    )
    return {
        "count": len(entries),
        "stats": ledger.get_agent_stats(agent_type=agent_type),
        "entries": list(reversed(entries)),  # mais recentes primeiro
    }


@router.get("/export.csv", summary="Exporta a trilha de auditoria em CSV")
async def export_ledger_csv(
    agent_type: Optional[str] = Query(None),
    decision_type: Optional[str] = Query(None),
) -> StreamingResponse:
    """Exporta as entradas como CSV para conformidade/arquivamento."""

    entries = ledger.get_entries(agent_type=agent_type, decision_type=decision_type)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "timestamp",
            "agent_type",
            "decision_type",
            "approved",
            "operator",
            "agent_alvo",
        ]
    )
    for entry in entries:
        meta = entry.get("metadata", {})
        writer.writerow(
            [
                entry.get("id", ""),
                entry.get("timestamp", ""),
                entry.get("agent_type", ""),
                entry.get("decision_type", ""),
                meta.get("approved", ""),
                meta.get("operator_id", ""),
                meta.get("agent", ""),
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=decision_ledger.csv"},
    )


__all__ = ["router"]
