"""Rotas de descoberta de módulos da plataforma."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.rbac import Principal, current_principal
from src.api.schemas.responses import ModuleListResponse, ModuleResponse
from src.modules.registry import get_module_registry

router = APIRouter(prefix="/api/v1/modules", tags=["Módulos"])


@router.get(
    "",
    response_model=ModuleListResponse,
    summary="Lista módulos registrados",
    description="Retorna todos os módulos ativos da plataforma com suas capacidades.",
)
async def list_modules(
    _principal: Principal = Depends(current_principal),
) -> ModuleListResponse:
    """Lista todos os módulos ativos no registry."""

    registry = get_module_registry()
    modules = registry.list_active()
    return ModuleListResponse(
        total=len(modules),
        modules=[ModuleResponse(**m.to_dict()) for m in modules],
    )


@router.get(
    "/{module_id}",
    response_model=ModuleResponse,
    summary="Detalhes de um módulo",
    description="Retorna o manifesto completo de um módulo específico.",
    responses={404: {"description": "Módulo não encontrado"}},
)
async def get_module_detail(
    module_id: str,
    _principal: Principal = Depends(current_principal),
) -> ModuleResponse:
    """Retorna o manifesto de um módulo específico."""

    registry = get_module_registry()
    manifest = registry.get(module_id)
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Módulo '{module_id}' não encontrado.",
        )
    return ModuleResponse(**manifest.to_dict())
