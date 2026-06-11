"""Queue manager for pending HITL approvals.

CLOUD-READINESS: o estado da fila fica atrás de uma interface (``HITLStore``).
O backend padrão (``memory``) mantém o comportamento histórico, orientado a
eventos asyncio, ideal para Docker single-node. Com ``HITL_BACKEND=redis`` as
solicitações e decisões passam a viver no Redis, compartilhadas entre réplicas;
nesse modo, ``wait_for_decision`` faz polling do store como fallback de wake-up
entre processos (a evolução natural é um canal pub/sub, deixada como próximo passo).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from src.utils.decision_metrics import DecisionMetricsCollector

logger = logging.getLogger(__name__)

# Intervalo de polling (s) usado pelo backend compartilhado para detectar
# decisões registradas por outra réplica.
_SHARED_POLL_INTERVAL = 0.5


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HITLRequest":
        """Reconstrói a solicitação a partir de um dicionário serializado."""
        return cls(
            request_id=data["request_id"],
            agent=data.get("agent", ""),
            action=data.get("action") or {},
            context=data.get("context") or {},
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            status=data.get("status", "pending"),
            decision=data.get("decision"),
            decided_at=data.get("decided_at"),
            decided_by=data.get("decided_by"),
        )


class HITLStore(Protocol):
    """Backend de armazenamento das solicitações HITL."""

    shared: bool

    def put(self, request: HITLRequest) -> None: ...

    def get(self, request_id: str) -> Optional[HITLRequest]: ...

    def all(self) -> List[HITLRequest]: ...

    def clear(self) -> None: ...


class MemoryHITLStore:
    """Armazenamento in-memory (single-process, orientado a eventos)."""

    shared = False

    def __init__(self) -> None:
        self._queue: "OrderedDict[str, HITLRequest]" = OrderedDict()

    def put(self, request: HITLRequest) -> None:
        self._queue[request.request_id] = request

    def get(self, request_id: str) -> Optional[HITLRequest]:
        return self._queue.get(request_id)

    def all(self) -> List[HITLRequest]:
        return list(self._queue.values())

    def clear(self) -> None:
        self._queue.clear()


class RedisHITLStore:
    """Armazenamento compartilhado das solicitações em um hash Redis."""

    shared = True

    def __init__(self, client, key: str = "hitl:requests") -> None:
        self._client = client
        self._key = key

    def put(self, request: HITLRequest) -> None:
        try:
            self._client.hset(
                self._key,
                request.request_id,
                json.dumps(request.to_dict(), ensure_ascii=False),
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error storing HITL request in Redis: %s", exc)

    def get(self, request_id: str) -> Optional[HITLRequest]:
        try:
            raw = self._client.hget(self._key, request_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error reading HITL request from Redis: %s", exc)
            return None
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return HITLRequest.from_dict(json.loads(raw))

    def all(self) -> List[HITLRequest]:
        try:
            raw = self._client.hgetall(self._key)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error listing HITL requests from Redis: %s", exc)
            return []
        requests: List[HITLRequest] = []
        for value in raw.values():
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            requests.append(HITLRequest.from_dict(json.loads(value)))
        return requests

    def clear(self) -> None:
        try:
            self._client.delete(self._key)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error clearing HITL requests in Redis: %s", exc)


def _build_store() -> HITLStore:
    backend = os.getenv("HITL_BACKEND", "memory").strip().lower()
    if backend == "redis":
        from src.utils.redis_client import get_shared_redis_client

        client = get_shared_redis_client()
        if client is not None:
            return RedisHITLStore(client)
        logger.warning(
            "HITL_BACKEND=redis mas nenhum cliente Redis disponível; "
            "usando fila in-memory (não compartilhada entre réplicas)."
        )
    return MemoryHITLStore()


class HITLQueue:
    """Gerencia fila de aprovações pendentes com suporte a notificações."""

    def __init__(self, timeout_seconds: int = 300) -> None:
        self.timeout_seconds = timeout_seconds
        self._store: HITLStore = _build_store()
        # Eventos asyncio são locais ao processo (wake-up imediato).
        self._events: Dict[str, asyncio.Event] = {}
        self._websocket_callbacks: list = []

    @property
    def _shared(self) -> bool:
        return getattr(self._store, "shared", False)

    def add_request(
        self, agent: str, action: Dict[str, Any], context: Dict[str, Any]
    ) -> HITLRequest:
        """Adiciona nova solicitação à fila."""
        request = HITLRequest(agent=agent, action=action, context=context)
        self._store.put(request)
        self._events[request.request_id] = asyncio.Event()

        DecisionMetricsCollector.record_hitl_request(
            agent=agent,
            status="pending",
        )
        DecisionMetricsCollector.update_hitl_queue_depth(
            len(self.get_pending_requests())
        )

        # Notificar WebSocket
        self._notify_websockets("new_request", request.to_dict())

        return request

    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """Retorna todas as solicitações pendentes."""
        return [req.to_dict() for req in self._store.all() if req.status == "pending"]

    def get_request(self, request_id: str) -> Optional[HITLRequest]:
        """Busca uma solicitação específica."""
        return self._store.get(request_id)

    async def wait_for_decision(self, request_id: str) -> Dict[str, Any]:
        """Aguarda decisão humana com timeout."""
        event = self._events.get(request_id)

        if event is None:
            # Sem evento local: ou a solicitação é desconhecida (backend in-memory)
            # ou foi criada em outra réplica (backend compartilhado → polling).
            if not self._shared:
                raise ValueError(f"Request {request_id} not found")
            return await self._poll_for_decision(request_id)

        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            return self._mark_timeout(request_id)

        request = self._store.get(request_id)
        return (request.decision if request else None) or {"approved": False}

    async def _poll_for_decision(self, request_id: str) -> Dict[str, Any]:
        """Fallback entre réplicas: aguarda mudança de status via polling."""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.timeout_seconds
        while loop.time() < deadline:
            request = self._store.get(request_id)
            if request is None:
                raise ValueError(f"Request {request_id} not found")
            if request.status != "pending":
                return request.decision or {"approved": request.status == "approved"}
            await asyncio.sleep(_SHARED_POLL_INTERVAL)
        return self._mark_timeout(request_id)

    def _mark_timeout(self, request_id: str) -> Dict[str, Any]:
        request = self._store.get(request_id)
        if request is not None:
            request.status = "timeout"
            request.decided_at = datetime.now(timezone.utc).isoformat()
            self._store.put(request)
        return {"approved": False, "reason": "timeout"}

    def record_decision(
        self,
        request_id: str,
        approved: bool,
        modifications: Optional[Dict[str, Any]] = None,
        feedback: Optional[str] = None,
        operator_id: str = "manual_operator",
    ) -> bool:
        """Registra decisão humana."""
        request = self._store.get(request_id)
        if request is None:
            return False

        created = datetime.fromisoformat(request.created_at.replace("Z", "+00:00"))
        decided = datetime.now(timezone.utc)
        response_time = (decided - created).total_seconds()

        request.status = "approved" if approved else "rejected"
        request.decision = {
            "approved": approved,
            "modifications": modifications,
            "feedback": feedback,
        }
        request.decided_at = decided.isoformat()
        request.decided_by = operator_id
        self._store.put(request)

        DecisionMetricsCollector.record_hitl_request(
            agent=request.agent,
            status="approved" if approved else "rejected",
            response_time_seconds=response_time,
        )
        DecisionMetricsCollector.update_hitl_queue_depth(
            len(self.get_pending_requests())
        )

        # Liberar agente aguardando (wake-up local imediato).
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
        self._store.clear()
        self._events.clear()

    def _notify_websockets(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notifica todos os WebSockets conectados."""
        for callback in self._websocket_callbacks:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                continue  # DT-01: avoid "coroutine never awaited" when no loop is running
            try:
                loop.create_task(callback(event_type, data))
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
