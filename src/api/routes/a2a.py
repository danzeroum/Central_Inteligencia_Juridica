"""Rotas do canal A2A (Agent-to-Agent) — envio, recepção, histórico e broadcast."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.rate_limit import enforce_rate_limit
from src.api.rbac import Principal, current_principal
from src.api.routes._shared import enforce_agent_identity, validate_agent_id
from src.api.schemas.requests import (
    A2ABroadcastRequest,
    A2AMessageRequest,
    ProblemDetail,
)
from src.api.schemas.responses import (
    A2ABroadcastResponse,
    A2AHistoryResponse,
    A2AMessageResponse,
    A2AMessagesResponse,
)
from src.api.state import a2a_channel

router = APIRouter(tags=["A2A"])


@router.post(
    "/api/v1/a2a/send",
    summary="Envia mensagem entre agentes",
    description=(
        "Permite enviar mensagem direta de um agente para outro. O ``sender_id`` "
        "deve vir no corpo (``A2AMessageRequest.sender_id``). O query param "
        "``sender_id`` é aceito apenas por retrocompatibilidade e está *deprecated*."
    ),
    response_model=A2AMessageResponse,
    responses={
        400: {"model": ProblemDetail},
        403: {"model": ProblemDetail},
    },
)
async def send_a2a_message(
    message: A2AMessageRequest,
    sender_id: Optional[str] = Query(
        None,
        deprecated=True,
        description="DEPRECATED — informe ``sender_id`` no corpo da requisição.",
    ),
    principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
) -> A2AMessageResponse:
    """Envia mensagem entre agentes utilizando o canal A2A."""

    effective_sender = message.sender_id or sender_id
    if not effective_sender:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sender_id é obrigatório (informe no corpo da requisição)",
        )

    validate_agent_id(effective_sender, "sender_id")
    validate_agent_id(message.receiver_id, "receiver_id")
    enforce_agent_identity(effective_sender, principal)

    message_id = await a2a_channel.send_message(
        sender_id=effective_sender,
        receiver_id=message.receiver_id,
        message_type=message.message_type,
        payload=message.payload,
        priority=message.priority,
        requires_response=message.requires_response,
    )

    return A2AMessageResponse(
        status="sent",
        message_id=message_id,
        sender=effective_sender,
        receiver=message.receiver_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/api/v1/a2a/messages/{agent_id}",
    summary="Recebe mensagens pendentes de um agente",
    description="Retorna lista de mensagens A2A pendentes para um agente.",
    response_model=A2AMessagesResponse,
)
async def get_agent_messages(
    agent_id: str,
    limit: int = Query(10, ge=1, le=100),
    _principal: Principal = Depends(current_principal),
) -> A2AMessagesResponse:
    """Recupera mensagens pendentes para um agente específico."""

    validate_agent_id(agent_id, "agent_id")
    messages = await a2a_channel.receive_messages(agent_id, limit)

    return A2AMessagesResponse(
        agent_id=agent_id,
        message_count=len(messages),
        messages=[msg.to_dict() for msg in messages],
    )


@router.get(
    "/api/v1/a2a/history/{agent_id}",
    summary="Histórico de mensagens A2A",
    description="Retorna histórico de mensagens enviadas/recebidas por um agente.",
    response_model=A2AHistoryResponse,
)
async def get_a2a_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    _principal: Principal = Depends(current_principal),
) -> A2AHistoryResponse:
    """Retorna histórico de mensagens para o agente informado."""

    validate_agent_id(agent_id, "agent_id")
    history = a2a_channel.get_message_history(agent_id, limit)

    return A2AHistoryResponse(
        agent_id=agent_id,
        total_messages=len(history),
        messages=[msg.to_dict() for msg in history],
    )


@router.post(
    "/api/v1/a2a/broadcast",
    summary="Broadcast para múltiplos agentes",
    description="Envia mensagem para múltiplos agentes simultaneamente.",
    response_model=A2ABroadcastResponse,
)
async def broadcast_a2a_message(
    request: A2ABroadcastRequest,
    principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
) -> A2ABroadcastResponse:
    """Realiza broadcast de mensagens para múltiplos agentes."""

    validate_agent_id(request.sender_id, "sender_id")
    for receiver_id in request.receiver_ids:
        validate_agent_id(receiver_id, "receiver_id")
    enforce_agent_identity(request.sender_id, principal)

    message_ids = []
    for receiver_id in request.receiver_ids:
        msg_id = await a2a_channel.send_message(
            sender_id=request.sender_id,
            receiver_id=receiver_id,
            message_type=request.message_type,
            payload=request.payload,
            priority=request.priority,
        )
        message_ids.append(msg_id)

    return A2ABroadcastResponse(
        status="broadcasted",
        sender=request.sender_id,
        receivers=request.receiver_ids,
        message_ids=message_ids,
        total_sent=len(message_ids),
    )


@router.get(
    "/api/v1/a2a/health",
    summary="Status do canal A2A",
    description="Verifica saúde do sistema de comunicação A2A.",
)
async def a2a_health_check() -> Dict[str, Any]:
    """Retorna informações de saúde do canal A2A."""

    return await a2a_channel.health_check()
