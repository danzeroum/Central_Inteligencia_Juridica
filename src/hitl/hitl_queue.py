"""Queue manager for pending HITL approvals."""

from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class HITLRequest:
    """Representa uma solicitação de aprovação humana."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent: str = ""
    action: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "pending"  # pending, approved, rejected, timeout
    decision: Optional[Dict[str, Any]] = None
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para JSON."""
        return {
            "request_id": self.request_id,
            "agent": self.agent,
            "action": self.action,
            "context": self.context,
            "created_at": self.created_at,
            "status": self.status,
            "decision": self.decision,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
        }


class HITLQueue:
    """Gerencia fila de aprovações pendentes com suporte a notificações."""

    def __init__(self, timeout_seconds: int = 300) -> None:
        self.timeout_seconds = timeout_seconds
        self._queue: OrderedDict[str, HITLRequest] = OrderedDict()
        self._events: Dict[str, asyncio.Event] = {}
        self._websocket_callbacks: list = []

    def add_request(
        self, agent: str, action: Dict[str, Any], context: Dict[str, Any]
    ) -> HITLRequest:
        """Adiciona nova solicitação à fila."""
        request = HITLRequest(agent=agent, action=action, context=context)
        self._queue[request.request_id] = request
        self._events[request.request_id] = asyncio.Event()

        # Notificar WebSocket
        self._notify_websockets("new_request", request.to_dict())

        return request

    def get_pending_requests(self) -> list[Dict[str, Any]]:
        """Retorna todas as solicitações pendentes."""
        return [
            req.to_dict() for req in self._queue.values() if req.status == "pending"
        ]

    def get_request(self, request_id: str) -> Optional[HITLRequest]:
        """Busca uma solicitação específica."""
        return self._queue.get(request_id)

    async def wait_for_decision(self, request_id: str) -> Dict[str, Any]:
        """Aguarda decisão humana com timeout."""
        if request_id not in self._events:
            raise ValueError(f"Request {request_id} not found")

        event = self._events[request_id]

        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            # Timeout - marcar como tal
            request = self._queue[request_id]
            request.status = "timeout"
            request.decided_at = datetime.now(timezone.utc).isoformat()
            return {"approved": False, "reason": "timeout"}

        request = self._queue[request_id]
        return request.decision or {"approved": False}

    def record_decision(
        self,
        request_id: str,
        approved: bool,
        modifications: Optional[Dict[str, Any]] = None,
        feedback: Optional[str] = None,
        operator_id: str = "manual_operator",
    ) -> bool:
        """Registra decisão humana."""
        if request_id not in self._queue:
            return False

        request = self._queue[request_id]
        request.status = "approved" if approved else "rejected"
        request.decision = {
            "approved": approved,
            "modifications": modifications,
            "feedback": feedback,
        }
        request.decided_at = datetime.now(timezone.utc).isoformat()
        request.decided_by = operator_id

        # Liberar agente aguardando
        if request_id in self._events:
            self._events[request_id].set()

        # Notificar WebSocket
        self._notify_websockets("decision_made", request.to_dict())

        return True

    def register_websocket_callback(self, callback) -> None:
        """Registra callback para notificações WebSocket."""
        self._websocket_callbacks.append(callback)

    def clear(self) -> None:
        """Limpa fila e eventos pendentes (útil para testes)."""
        self._queue.clear()
        self._events.clear()

    def _notify_websockets(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notifica todos os WebSockets conectados."""
        for callback in self._websocket_callbacks:
            try:
                asyncio.create_task(callback(event_type, data))
            except Exception:  # pragma: no cover - defensive
                pass


# Instância global
_hitl_queue: Optional[HITLQueue] = None


def get_hitl_queue() -> HITLQueue:
    """Retorna instância global da fila HITL."""
    global _hitl_queue
    if _hitl_queue is None:
        _hitl_queue = HITLQueue()
    return _hitl_queue


__all__ = ["HITLRequest", "HITLQueue", "get_hitl_queue"]
