"""Rota de slots de navegação — consumida pela SPA no startup para montar o menu."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

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


@router.get(
    "/api/v1/slots/stream",
    summary="SSE — mudanças de slots em tempo real",
    description=(
        "Server-Sent Events: notifica a SPA sempre que um módulo é ativado ou "
        "desativado via ``PATCH /api/v1/modules/{module_id}``. Sem autenticação "
        "obrigatória — os dados são apenas metadados de navegação (não sensíveis). "
        "Keepalive a cada 30 s para manter proxies abertos."
    ),
    response_class=StreamingResponse,
)
async def stream_slots(request: Request) -> StreamingResponse:
    """SSE stream — publica eventos de mudança de módulos para a SPA."""

    registry = get_module_registry()
    queue = registry.subscribe()

    async def generator():
        # Enviar snapshot imediatamente ao conectar — cliente não precisa
        # chamar GET /api/v1/slots separadamente ao reconectar.
        active = registry.list_active()
        connected_payload = json.dumps(
            {"event": "connected", "active_count": len(active)}, ensure_ascii=False
        )
        yield f"data: {connected_payload}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            registry.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
