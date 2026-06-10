"""REST endpoints mínimos para monitoração da camada de integrações.

GET /api/v1/intelligence/health — status de cada fonte.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from src.api.rbac import Principal, require_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


@router.get("/health")
async def intelligence_health(
    principal: Principal = Depends(require_permissions("intelligence:query")),
) -> Dict[str, Any]:
    """Retorna status de cada adaptador de integração."""
    from src.integrations.registry import get_registry

    registry = get_registry()
    adapters_health: List[Dict[str, Any]] = []
    for name in registry.names():
        adapter = registry.get(name)
        if adapter:
            adapters_health.append(
                {
                    "source": name,
                    "enabled": adapter.enabled,
                    "mode": adapter.settings.mode,
                    "zone": adapter.zone.value,
                    "data_type": adapter.data_type,
                }
            )
    return {
        "status": "ok",
        "adapters": adapters_health,
        "count": len(adapters_health),
    }
