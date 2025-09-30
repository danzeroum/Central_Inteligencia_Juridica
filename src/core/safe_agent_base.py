"""Safety-focused base agent with guardrails used across the platform."""

from __future__ import annotations

import hashlib
import logging
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, Optional

from src.utils.input_sanitizer import InputSanitizer
from src.utils.ledger import DecisionLedger
from src.utils.metrics_collector import MetricsCollector

CapabilityHandler = Callable[[str, Optional[str]], Dict[str, Any]]


@dataclass
class RegisteredCapability:
    """Metadata describing a capability available to the agent."""

    name: str
    handler: CapabilityHandler
    description: str = ""
    allowed_tools: Iterable[str] = field(default_factory=tuple)


class SafeAgentBase:
    """Base class embedding the mandatory BuildToFlip v6.1 guardrails.

    Guardrails enforced:
        1. **Input sanitisation** – All incoming tasks/contexts are normalised by
           :class:`InputSanitizer` before execution.
        2. **Decision ledger** – Key lifecycle events are written to the
           :class:`~src.utils.ledger.DecisionLedger` for traceability.
        3. **Capability whitelisting** – Only registered capabilities can be
           executed, preventing ad-hoc or unsafe behaviours.
        4. **Loop protection** – Recent executions are tracked to avoid infinite
           repetition of identical tasks.
    """

    def __init__(
        self,
        *,
        ledger: DecisionLedger | None = None,
        max_repeated_tasks: int = 3,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sanitizer = InputSanitizer()
        self.ledger = ledger or DecisionLedger()
        self.max_repeated_tasks = max(1, max_repeated_tasks)
        self._recent_tasks: Deque[str] = deque(maxlen=self.max_repeated_tasks * 2)
        self._capabilities: Dict[str, RegisteredCapability] = {}
        self._tools_in_use: Counter[str] = Counter()

        MetricsCollector.set_agent_active(self.__class__.__name__, True)

    # ------------------------------------------------------------------
    # Capability management
    # ------------------------------------------------------------------
    def add_capability(
        self,
        name: str,
        handler: CapabilityHandler,
        *,
        description: str = "",
        allowed_tools: Iterable[str] | None = None,
    ) -> None:
        """Register a new capability guarded by the whitelist."""

        if not name:
            raise ValueError("Capability name cannot be empty")
        if name in self._capabilities:
            raise ValueError(f"Capability '{name}' already registered")

        capability = RegisteredCapability(
            name=name,
            handler=handler,
            description=description,
            allowed_tools=tuple(allowed_tools or ()),
        )
        self._capabilities[name] = capability

        self.ledger.log_decision(
            agent_type=self.__class__.__name__,
            decision_type="CAPABILITY_REGISTERED",
            metadata={"capability": name, "description": description},
        )

    # ------------------------------------------------------------------
    def execute(
        self,
        *,
        task: str,
        capability: str,
        context: str | None = None,
    ) -> Dict[str, Any]:
        """Execute ``task`` using a registered capability applying guardrails."""

        sanitized_task = self.sanitizer.sanitize_text(task)
        sanitized_context = self.sanitizer.sanitize_text(context) if context else ""
        task_fingerprint = self._fingerprint_task(sanitized_task, capability)
        self._enforce_loop_protection(task_fingerprint)

        capability_info = self._capabilities.get(capability)
        if capability_info is None:
            raise PermissionError(f"Capability '{capability}' is not registered")

        self.ledger.log_decision(
            agent_type=self.__class__.__name__,
            decision_type="TASK_RECEIVED",
            metadata={
                "capability": capability,
                "task": sanitized_task,
                "context": sanitized_context,
            },
        )

        result = capability_info.handler(sanitized_task, sanitized_context or None)
        payload = dict(result)
        payload.setdefault("capability", capability)
        payload.setdefault("task", sanitized_task)

        self.ledger.log_decision(
            agent_type=self.__class__.__name__,
            decision_type="TASK_COMPLETED",
            metadata={"capability": capability, "result_keys": list(payload.keys())},
        )
        return payload

    # ------------------------------------------------------------------
    def execute_tool(self, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Record tool usage ensuring it is approved by the active capability."""

        if tool_name not in self._tools_in_use:
            # Tools must be declared as part of at least one capability
            if not any(tool_name in cap.allowed_tools for cap in self._capabilities.values()):
                raise PermissionError(f"Tool '{tool_name}' is not authorised")

        self._tools_in_use[tool_name] += 1
        self.ledger.log_decision(
            agent_type=self.__class__.__name__,
            decision_type="TOOL_EXECUTED",
            metadata={"tool": tool_name, "parameters": kwargs},
        )
        return {"tool": tool_name, "executions": self._tools_in_use[tool_name]}

    # ------------------------------------------------------------------
    def list_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Return metadata about registered capabilities."""

        return {
            name: {
                "description": cap.description,
                "allowed_tools": list(cap.allowed_tools),
            }
            for name, cap in self._capabilities.items()
        }

    # ------------------------------------------------------------------
    def _fingerprint_task(self, task: str, capability: str) -> str:
        data = f"{capability}:{task}".encode("utf-8", "ignore")
        return hashlib.sha256(data).hexdigest()

    def _enforce_loop_protection(self, fingerprint: str) -> None:
        if fingerprint in self._recent_tasks:
            occurrences = sum(1 for item in self._recent_tasks if item == fingerprint)
            if occurrences >= self.max_repeated_tasks:
                raise RuntimeError(
                    "Loop protection triggered: task repeated excessively"
                )
        self._recent_tasks.append(fingerprint)


__all__ = ["SafeAgentBase"]
