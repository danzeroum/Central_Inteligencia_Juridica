"""Mixin to add A2A capabilities to agents."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from src.protocols.a2a_channel import A2AMessage, get_a2a_channel

logger = logging.getLogger(__name__)


class A2ACapable:
    """Mixin to add Agent-to-Agent communication capabilities."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.a2a_channel = get_a2a_channel()
        self.a2a_handlers: Dict[str, Callable] = {}
        self._a2a_initialized = False

    def get_agent_id(self) -> str:
        """Get unique identifier for this agent (must be implemented by subclass)."""
        # Try common patterns
        if hasattr(self, "agent_id"):
            return str(self.agent_id)
        if hasattr(self, "tribunal_code"):
            return f"{self.tribunal_code.lower()}_agent"
        if hasattr(self, "agent_type"):
            return f"{self.agent_type.lower()}_agent"
        return "unknown_agent"

    async def send_to_agent(
        self,
        target_agent_id: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: int = 1,
        requires_response: bool = False,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Send message to another agent."""
        sender_id = self.get_agent_id()

        message_id = await self.a2a_channel.send_message(
            sender_id=sender_id,
            receiver_id=target_agent_id,
            message_type=message_type,
            payload=payload,
            priority=priority,
            requires_response=requires_response,
            correlation_id=correlation_id,
        )

        logger.info(
            "%s sent A2A message to %s: %s",
            sender_id,
            target_agent_id,
            message_type,
        )

        return message_id

    async def request_from_agent(
        self,
        target_agent_id: str,
        message_type: str,
        payload: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        """Request data from another agent and wait for response."""
        sender_id = self.get_agent_id()

        response = await self.a2a_channel.request_response(
            sender_id=sender_id,
            receiver_id=target_agent_id,
            message_type=message_type,
            payload=payload,
            timeout=timeout,
        )

        if response:
            logger.info(
                "%s received response from %s for %s",
                sender_id,
                target_agent_id,
                message_type,
            )
        else:
            logger.warning(
                "%s did not receive response from %s (timeout)",
                sender_id,
                target_agent_id,
            )

        return response

    async def check_messages(self, limit: int = 10) -> List[A2AMessage]:
        """Check for pending messages."""
        agent_id = self.get_agent_id()
        messages = await self.a2a_channel.receive_messages(agent_id, limit)

        if messages:
            logger.info("%s received %d A2A messages", agent_id, len(messages))

        return messages

    async def process_messages(self) -> List[Dict[str, Any]]:
        """Process all pending messages and return results."""
        messages = await self.check_messages()
        results = []

        for message in messages:
            result = await self._handle_message(message)
            results.append(result)

        return results

    async def _handle_message(self, message: A2AMessage) -> Dict[str, Any]:
        """Handle incoming message based on type."""
        handler = self.a2a_handlers.get(message.message_type)

        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    response_payload = await handler(message)
                else:
                    response_payload = handler(message)

                # Send response if required
                if message.requires_response and response_payload:
                    await self.send_to_agent(
                        target_agent_id=message.sender_id,
                        message_type=f"{message.message_type}_response",
                        payload=response_payload,
                        priority=message.priority,
                        correlation_id=message.correlation_id,
                    )

                return {
                    "status": "handled",
                    "message_id": message.message_id,
                    "handler": handler.__name__,
                }
            except Exception as exc:
                logger.error(
                    "Error handling message %s: %s",
                    message.message_id,
                    exc,
                )
                return {
                    "status": "error",
                    "message_id": message.message_id,
                    "error": str(exc),
                }
        else:
            logger.warning(
                "No handler for message type '%s' from %s",
                message.message_type,
                message.sender_id,
            )
            return {
                "status": "no_handler",
                "message_id": message.message_id,
                "message_type": message.message_type,
            }

    def register_handler(self, message_type: str, handler: Callable) -> None:
        """Register handler for specific message type."""
        self.a2a_handlers[message_type] = handler
        logger.info(
            "%s registered handler for '%s'",
            self.get_agent_id(),
            message_type,
        )

    async def broadcast_to_agents(
        self,
        agent_ids: List[str],
        message_type: str,
        payload: Dict[str, Any],
        priority: int = 1,
    ) -> List[str]:
        """Broadcast message to multiple agents."""
        message_ids = []

        for agent_id in agent_ids:
            msg_id = await self.send_to_agent(
                target_agent_id=agent_id,
                message_type=message_type,
                payload=payload,
                priority=priority,
            )
            message_ids.append(msg_id)

        logger.info(
            "%s broadcasted '%s' to %d agents",
            self.get_agent_id(),
            message_type,
            len(agent_ids),
        )

        return message_ids

    def get_message_history(self, limit: int = 50) -> List[A2AMessage]:
        """Get A2A message history for this agent."""
        agent_id = self.get_agent_id()
        return self.a2a_channel.get_message_history(agent_id, limit)


# Example handlers that agents can use
def create_status_handler() -> Callable:
    """Create a standard status request handler."""

    async def status_handler(message: A2AMessage) -> Dict[str, Any]:
        return {
            "status": "operational",
            "agent_id": message.receiver_id,
            "timestamp": message.timestamp,
        }

    return status_handler


def create_data_request_handler(data_source: Callable) -> Callable:
    """Create a handler for data requests."""

    async def data_handler(message: A2AMessage) -> Dict[str, Any]:
        query = message.payload.get("query")

        if asyncio.iscoroutinefunction(data_source):
            data = await data_source(query)
        else:
            data = data_source(query)

        return {
            "data": data,
            "query": query,
            "source_agent": message.receiver_id,
        }

    return data_handler


__all__ = [
    "A2ACapable",
    "create_status_handler",
    "create_data_request_handler",
]
