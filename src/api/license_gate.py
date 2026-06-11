"""Dependency FastAPI para gating de licença por módulo.

``require_module(module_id)`` retorna uma dependência que:
- Verifica se o módulo está ativo no registry (503 se não).
- Verifica licença ativa do tenant na tabela ``License`` (403 se ausente).
- É no-op quando ``DATABASE_URL`` não está configurado ou ``ENVIRONMENT=test``
  (compatibilidade retroativa com Onda 1 e suíte de testes).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, HTTPException, status

from src.api.config import ENVIRONMENT
from src.api.rbac import Principal, current_principal

logger = logging.getLogger(__name__)


def require_module(module_id: str) -> Callable:
    """Factory de dependência FastAPI: exige módulo ativo e licença válida para o tenant."""

    async def _gate(principal: Principal = Depends(current_principal)) -> None:
        from src.modules.registry import get_module_registry

        registry = get_module_registry()
        manifest = registry.get(module_id)

        if manifest is None or not manifest.is_active:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Módulo '{module_id}' não está disponível.",
            )

        # Sem DB ou em ambiente de test: sem gating de licença (retrocompat)
        if not os.getenv("DATABASE_URL") or ENVIRONMENT == "test":
            return

        # Tenant anônimo (AUTH_REQUIRED=false em dev): sem gating
        if principal.is_anonymous:
            return

        _check_license(principal.user_id, module_id)

    return _gate


def _check_license(tenant_id: str, module_id: str) -> None:
    """Verifica no banco se o tenant possui licença ativa para o módulo."""
    try:
        from sqlalchemy import and_, or_, select
        from sqlalchemy.orm import Session

        from src.db.engine import get_sync_engine
        from src.db.models import License

        engine = get_sync_engine()
        if engine is None:
            return

        now = datetime.now(timezone.utc)
        with Session(engine) as session:
            lic = session.execute(
                select(License).where(
                    and_(
                        License.tenant_id == tenant_id,
                        License.module_id == module_id,
                        License.valid_from <= now,
                        or_(License.valid_until.is_(None), License.valid_until > now),
                    )
                )
            ).scalar_one_or_none()

        if lic is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant não possui licença ativa para o módulo '{module_id}'.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "Erro ao verificar licença (%s/%s): %s", tenant_id, module_id, exc
        )
