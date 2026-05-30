"""FastAPI endpoints de monitoramento operacional.

Agrega saúde do sistema para a tela de Monitoramento: estados dos circuit
breakers, profundidade da fila HITL e saúde do canal A2A. Apenas leitura sobre
estado em memória já mantido pelos componentes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

from src.hitl.hitl_queue import get_hitl_queue
from src.protocols.a2a_channel import get_a2a_channel
from src.tools.circuit_breaker import get_all_circuit_breakers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/monitoring", tags=["Monitoring"])


@router.get("/health", summary="Saúde agregada do sistema")
async def monitoring_health() -> Dict[str, Any]:
    """Retorna circuit breakers, fila HITL e canal A2A num único payload."""

    breakers = [breaker.get_state() for breaker in get_all_circuit_breakers().values()]

    a2a_channel = get_a2a_channel()
    try:
        a2a_health = await a2a_channel.health_check()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Falha ao checar saúde A2A: %s", exc)
        a2a_health = {"status": "unknown", "error": str(exc)}

    pending = get_hitl_queue().get_pending_requests()

    return {
        "circuit_breakers": breakers,
        "hitl_queue_depth": len(pending),
        "a2a": a2a_health,
    }


__all__ = ["router"]
