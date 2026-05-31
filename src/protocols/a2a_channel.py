"""Agent-to-Agent Communication Channel."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # type: ignore


@dataclass
class A2AMessage:
    """Message structure for agent-to-agent communication."""

    message_id: str
    sender_id: str
    receiver_id: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    priority: int = 1  # 1=low, 2=normal, 3=high
    requires_response: bool = False
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dictionary."""
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "requires_response": self.requires_response,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> A2AMessage:
        """Deserialize message from dictionary."""
        return cls(
            message_id=data["message_id"],
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            message_type=data["message_type"],
            payload=data["payload"],
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            priority=data.get("priority", 1),
            requires_response=data.get("requires_response", False),
            correlation_id=data.get("correlation_id"),
        )


@dataclass
class InMemoryChannel:
    """Fallback in-memory message queue."""

    queues: Dict[str, Deque[A2AMessage]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    handlers: Dict[str, List[Callable]] = field(
        default_factory=lambda: defaultdict(list)
    )
    message_history: List[A2AMessage] = field(default_factory=list)
    max_history: int = 1000

    async def publish(self, message: A2AMessage) -> None:
        """Publish message to receiver's queue."""
        self.queues[message.receiver_id].append(message)
        self.message_history.append(message)

        # Trim history
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history :]

        # Trigger handlers
        for handler in self.handlers.get(message.receiver_id, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as exc:
                logger.error("Handler error for %s: %s", message.receiver_id, exc)

    async def subscribe(self, agent_id: str, handler: Callable) -> None:
        """Subscribe to messages for specific agent."""
        self.handlers[agent_id].append(handler)

    async def get_messages(self, agent_id: str, limit: int = 10) -> List[A2AMessage]:
        """Get pending messages for agent."""
        messages = []
        queue = self.queues[agent_id]

        for _ in range(min(limit, len(queue))):
            if queue:
                messages.append(queue.popleft())

        return messages

    def get_history(
        self, agent_id: Optional[str] = None, limit: int = 50
    ) -> List[A2AMessage]:
        """Get message history for agent or all."""
        if agent_id:
            history = [
                msg
                for msg in self.message_history
                if msg.sender_id == agent_id or msg.receiver_id == agent_id
            ]
        else:
            history = self.message_history

        return history[-limit:]


class A2AChannel:
    """Agent-to-Agent communication channel with Redis backend and memory fallback."""

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self.redis_url = redis_url
        self.redis_client: Optional[Any] = None
        self.memory_channel = InMemoryChannel()
        self.using_redis = False
        self._initialize_redis()

    def _disable_redis(self) -> None:
        """Disable Redis backend and fallback to memory only."""
        if self.using_redis:
            logger.warning("Switching A2A channel to in-memory mode")
        self.using_redis = False
        self.redis_client = None

    def _initialize_redis(self) -> None:
        """Initialize Redis connection."""
        if not redis:
            logger.warning("Redis library not available. Using in-memory channel.")
            return

        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.using_redis = True
            logger.info("A2A Channel using Redis backend")
        except Exception as exc:
            logger.warning(
                "Could not connect to Redis: %s. Using memory fallback.", exc
            )
            self.redis_client = None

    async def send_message(
        self,
        sender_id: str,
        receiver_id: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: int = 1,
        requires_response: bool = False,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Send message from one agent to another."""
        message = A2AMessage(
            message_id=str(uuid.uuid4()),
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            payload=payload,
            priority=priority,
            requires_response=requires_response,
            correlation_id=correlation_id,
        )

        if self.using_redis and self.redis_client:
            try:
                await self._publish_redis(message)
            except Exception as exc:
                logger.error("Redis publish failed: %s. Using memory fallback.", exc)
                self._disable_redis()
                await self.memory_channel.publish(message)
        else:
            await self.memory_channel.publish(message)

        logger.info(
            "A2A: %s -> %s [%s] (priority=%d)",
            sender_id,
            receiver_id,
            message_type,
            priority,
        )

        return message.message_id

    async def _publish_redis(self, message: A2AMessage) -> None:
        """Publish message via Redis pub/sub."""
        channel = f"agent:{message.receiver_id}"
        await self.redis_client.publish(channel, json.dumps(message.to_dict()))

        # Also store in list for retrieval
        key = f"agent_queue:{message.receiver_id}"
        await self.redis_client.lpush(key, json.dumps(message.to_dict()))
        await self.redis_client.ltrim(key, 0, 99)  # Keep last 100 messages

    async def receive_messages(
        self, agent_id: str, limit: int = 10
    ) -> List[A2AMessage]:
        """Receive pending messages for agent."""
        if self.using_redis and self.redis_client:
            try:
                return await self._receive_redis(agent_id, limit)
            except Exception as exc:
                logger.error("Redis receive failed: %s. Using memory fallback.", exc)
                self._disable_redis()
                return await self.memory_channel.get_messages(agent_id, limit)
        else:
            return await self.memory_channel.get_messages(agent_id, limit)

    async def _receive_redis(self, agent_id: str, limit: int) -> List[A2AMessage]:
        """Receive messages from Redis."""
        key = f"agent_queue:{agent_id}"
        messages = []

        for _ in range(limit):
            data = await self.redis_client.rpop(key)
            if not data:
                break
            msg_dict = json.loads(data)
            messages.append(A2AMessage.from_dict(msg_dict))

        return messages

    async def subscribe_agent(self, agent_id: str, handler: Callable) -> None:
        """Subscribe agent to receive messages in real-time."""
        if self.using_redis and self.redis_client:
            # Redis pub/sub subscription (background task needed)
            logger.info("Redis subscription for %s requires background task", agent_id)

        await self.memory_channel.subscribe(agent_id, handler)

    def get_message_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[A2AMessage]:
        """Get message history for debugging/audit."""
        return self.memory_channel.get_history(agent_id, limit)

    async def request_response(
        self,
        sender_id: str,
        receiver_id: str,
        message_type: str,
        payload: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        """Send message and wait for response (request-response pattern)."""
        correlation_id = str(uuid.uuid4())

        message = A2AMessage(
            message_id=str(uuid.uuid4()),
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            payload=payload,
            requires_response=True,
            correlation_id=correlation_id,
        )

        # Send request
        if self.using_redis and self.redis_client:
            try:
                await self._publish_redis(message)
            except Exception as exc:
                logger.error("Redis publish failed: %s. Using memory fallback.", exc)
                self._disable_redis()
                await self.memory_channel.publish(message)
        else:
            await self.memory_channel.publish(message)

        # Wait for response
        # BUGFIX (CRÍTICO-15): o antigo acessor de loop é depreciado no Python
        # 3.10+ dentro de corrotinas; usamos ``get_running_loop()``, que é o
        # contrato correto quando já há um loop em execução.
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        while (loop.time() - start_time) < timeout:
            messages = await self.receive_messages(sender_id, limit=50)

            for msg in messages:
                if msg.correlation_id == correlation_id:
                    return msg.payload

            await asyncio.sleep(0.1)

        logger.warning(
            "Request-response timeout: %s -> %s (correlation=%s)",
            sender_id,
            receiver_id,
            correlation_id,
        )
        return None

    async def health_check(self) -> Dict[str, Any]:
        """Check A2A channel health."""
        if self.using_redis and self.redis_client:
            try:
                await self.redis_client.ping()
                backend = "redis"
                status = "healthy"
            except Exception as exc:
                backend = "redis"
                status = "degraded"
                return {"backend": backend, "status": status, "error": str(exc)}
        else:
            backend = "memory"
            status = "healthy"

        return {
            "backend": backend,
            "status": status,
            "message_history_size": len(self.memory_channel.message_history),
            "active_queues": len(self.memory_channel.queues),
        }


# Global A2A channel instance
_global_a2a_channel: Optional[A2AChannel] = None


def get_a2a_channel() -> A2AChannel:
    """Get or create global A2A channel instance."""
    global _global_a2a_channel
    if _global_a2a_channel is None:
        _global_a2a_channel = A2AChannel()
    return _global_a2a_channel


__all__ = ["A2AMessage", "A2AChannel", "get_a2a_channel"]
