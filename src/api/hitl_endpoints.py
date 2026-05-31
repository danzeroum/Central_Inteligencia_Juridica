"""FastAPI endpoints for Human-in-the-Loop operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from src.api.auth import AuthManager
from src.api.rbac import Principal, require_permissions
from src.hitl.hitl_queue import get_hitl_queue
from src.utils.ledger import get_ledger
from src.utils.request_context import get_audit_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/hitl", tags=["HITL"])
ledger = get_ledger()


def _authorize_ws(websocket: WebSocket) -> bool:
    """Valida o JWT do handshake do WebSocket HITL (H04).

    Retorna ``True`` quando a autenticação está desligada (dev/testes) ou quando
    o token é válido e concede ``hitl:write``. Caso contrário ``False``, levando
    o chamador a fechar a conexão.
    """

    if not AuthManager.REQUIRED:
        return True

    token = websocket.query_params.get("token")
    if not token:
        header = websocket.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1]
    if not token:
        return False

    try:
        payload = AuthManager.verify_token_payload(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )
    except HTTPException:
        return False

    # Reutiliza a álgebra de permissões do RBAC para exigir ``hitl:write``.
    from src.api.rbac import permissions_for, roles_from_payload

    return "hitl:write" in permissions_for(roles_from_payload(payload))


class HITLDecision(BaseModel):
    """Modelo para decisão do operador humano."""

    request_id: str = Field(..., description="ID da solicitação de aprovação")
    approved: bool = Field(..., description="Se a ação foi aprovada")
    modifications: Dict[str, Any] | None = Field(
        None, description="Modificações nos parâmetros"
    )
    feedback: str | None = Field(None, description="Feedback textual do operador")
    operator_id: str = Field(default="manual_operator", description="ID do operador")


@router.get("/pending", summary="Lista aprovações pendentes")
async def list_pending_approvals(
    _principal: Principal = Depends(require_permissions("hitl:write")),
) -> Dict[str, Any]:
    """Retorna todas as solicitações de aprovação aguardando decisão humana."""
    queue = get_hitl_queue()
    pending = queue.get_pending_requests()

    return {
        "count": len(pending),
        "requests": pending,
    }


@router.get("/stats", summary="Estatísticas da fila HITL")
async def hitl_stats(
    _principal: Principal = Depends(require_permissions("hitl:write")),
) -> Dict[str, Any]:
    """Resumo da fila para o cabeçalho do console de aprovações.

    As contagens de aprovadas/rejeitadas são derivadas do Decision Ledger
    (entradas ``HITL_DECISION``) do dia corrente.
    """
    queue = get_hitl_queue()
    pending = queue.get_pending_requests()

    today = datetime.now().strftime("%Y-%m-%d")
    approved = rejected = 0
    for entry in ledger.get_entries(decision_type="HITL_DECISION"):
        if not entry.get("timestamp", "").startswith(today):
            continue
        if entry.get("metadata", {}).get("approved"):
            approved += 1
        else:
            rejected += 1

    return {
        "pending": len(pending),
        "approved_today": approved,
        "rejected_today": rejected,
    }


@router.post(
    "/decisions",
    status_code=status.HTTP_200_OK,
    summary="Registra decisão humana",
)
async def record_decision(
    decision: HITLDecision,
    principal: Principal = Depends(require_permissions("hitl:write")),
) -> Dict[str, Any]:
    """
    Processa decisão do operador humano sobre uma ação proposta por agente.

    Esta é a interface crítica que permite supervisão humana em tempo real.

    SECURITY (IAM-003): o ``operator_id`` é derivado da identidade autenticada
    (JWT), não do corpo da requisição — impede que um operador seja forjado.
    Quando a autenticação está desligada (dev/testes), cai para o valor do corpo.
    """
    queue = get_hitl_queue()

    # IAM-003: identidade do operador vem do token autenticado, não do body.
    operator_id = (
        principal.user_id if not principal.is_anonymous else decision.operator_id
    )

    # Validar se o request existe
    request = queue.get_request(decision.request_id)
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request {decision.request_id} not found",
        )

    # Validar se ainda está pendente
    if request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request {decision.request_id} already decided: {request.status}",
        )

    # Registrar decisão
    success = queue.record_decision(
        request_id=decision.request_id,
        approved=decision.approved,
        modifications=decision.modifications,
        feedback=decision.feedback,
        operator_id=operator_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record decision",
        )

    # Gravar no ledger para auditoria. O contexto (correlation_id, IP de origem,
    # User-Agent) permite rastrear a decisão de volta à requisição HTTP original.
    ledger.log_decision(
        agent_type="HumanOperator",
        decision_type="HITL_DECISION",
        metadata={
            "request_id": decision.request_id,
            "agent": request.agent,
            "action": request.action,
            "approved": decision.approved,
            "modifications": decision.modifications,
            "feedback": decision.feedback,
            "operator_id": operator_id,
            **get_audit_context(),
        },
    )

    logger.info(
        "HITL decision recorded: %s - %s by %s",
        decision.request_id,
        "APPROVED" if decision.approved else "REJECTED",
        operator_id,
    )

    return {
        "success": True,
        "request_id": decision.request_id,
        "status": request.status,
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket para notificações em tempo real de novas solicitações HITL.

    Formato das mensagens:
    {
        "event": "new_request" | "decision_made",
        "data": { ... request details ... }
    }

    SECURITY (H04): quando a autenticação está ligada, o handshake exige um JWT
    válido com permissão ``hitl:write``. O token é aceito via query param
    ``?token=`` (WebSockets não carregam header ``Authorization`` de forma
    confiável em navegadores) ou via header ``Authorization: Bearer``. Sem token
    válido a conexão é fechada com *policy violation* (1008) antes do ``accept``.
    """
    if not _authorize_ws(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info("WebSocket HITL conectado: %s", websocket.client)

    queue = get_hitl_queue()

    async def send_notification(event_type: str, data: Dict[str, Any]) -> None:
        """Callback para enviar notificações ao WebSocket."""
        try:
            await websocket.send_json({"event": event_type, "data": data})
        except Exception as exc:  # pragma: no cover - network variability
            logger.warning("Failed to send WebSocket notification: %s", exc)

    # Registrar callback
    queue.register_websocket_callback(send_notification)

    try:
        # Enviar requests pendentes ao conectar
        pending = queue.get_pending_requests()
        for request in pending:
            await websocket.send_json({"event": "pending_request", "data": request})

        # Manter conexão viva
        while True:
            # Aguardar mensagens do cliente (se houver)
            data = await websocket.receive_text()
            logger.debug("Received from WebSocket: %s", data)

    except WebSocketDisconnect:
        logger.info("WebSocket HITL desconectado")


__all__ = ["router"]
