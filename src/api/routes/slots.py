"""Rota de slots de navegação — consumida pela SPA no startup para montar o menu."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas.responses import FrontendSlotResponse, SlotsResponse
from src.modules.registry import get_module_registry

router = APIRouter(tags=["Frontend"])


@router.get(
    "/api/v1/slots",
    response_model=SlotsResponse,
    summary="Slots de navegação ativos",
    description=(
        "Retorna a lista ordenada de slots de menu para os módulos ativos. "
        "Consumido pela SPA no startup, sem autenticação obrigatória."
    ),
)
async def list_slots() -> SlotsResponse:
    """Retorna slots de navegação dos módulos ativos, ordenados por ``order``."""

    registry = get_module_registry()
    active = registry.list_active()

    slots = sorted(
        (
            FrontendSlotResponse(**m.slot.to_dict())
            for m in active
            if m.slot is not None and m.slot.enabled
        ),
        key=lambda s: s.order,
    )

    return SlotsResponse(total=len(slots), slots=slots)
