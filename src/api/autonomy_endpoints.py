"""FastAPI endpoints para a regra de autonomia (tabela de decisão / DMN).

Permite ao jurídico inspecionar e ajustar os limiares que determinam "quando um
humano precisa decidir", sem tocar no código. Opera sobre o singleton
:func:`get_autonomy_manager`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.hitl.progressive_autonomy import get_autonomy_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/autonomy", tags=["Autonomy"])


class AutonomyConfigUpdate(BaseModel):
    """Atualização parcial dos limiares da regra de autonomia."""

    consensus_threshold: Optional[float] = Field(None, ge=0, le=1)
    trust_full_threshold: Optional[float] = Field(None, ge=0, le=1)
    trust_supervised_threshold: Optional[float] = Field(None, ge=0, le=1)


def _decision_table(manager: Any) -> List[Dict[str, Any]]:
    """Representação da tabela DMN 'Requer revisão humana?' (política First)."""

    threshold = manager.consensus_threshold
    return [
        {"rule": 1, "critical": "verdadeiro", "consensus": "—", "autonomy": "—", "requires_hitl": True},
        {"rule": 2, "critical": "falso", "consensus": f"< {threshold:.2f}", "autonomy": "—", "requires_hitl": True},
        {"rule": 3, "critical": "falso", "consensus": f"≥ {threshold:.2f}", "autonomy": "restrito", "requires_hitl": True},
        {"rule": 4, "critical": "falso", "consensus": f"≥ {threshold:.2f}", "autonomy": "supervisionado, pleno", "requires_hitl": False},
    ]


@router.get("/config", summary="Lê a configuração da regra de autonomia")
async def get_config() -> Dict[str, Any]:
    """Retorna os limiares e a tabela de decisão derivada."""

    manager = get_autonomy_manager()
    return {
        "config": manager.get_config(),
        "decision_table": _decision_table(manager),
    }


@router.put("/config", summary="Atualiza a configuração da regra de autonomia")
async def update_config(update: AutonomyConfigUpdate) -> Dict[str, Any]:
    """Atualiza os limiares (consenso e faixas de trust)."""

    manager = get_autonomy_manager()
    try:
        new_config = manager.update_config(
            consensus_threshold=update.consensus_threshold,
            trust_full_threshold=update.trust_full_threshold,
            trust_supervised_threshold=update.trust_supervised_threshold,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    logger.info("Configuração de autonomia atualizada: %s", new_config)
    return {
        "config": new_config,
        "decision_table": _decision_table(manager),
    }


__all__ = ["router"]
