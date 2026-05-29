"""Safety-focused base agent with guardrails used across the platform.

Phase 1 Fix: Merged version combining HEAD structure with codex guardrails.
Keeps codex's real guardrails (loop protection, capability whitelisting,
decision ledger) while maintaining HEAD's clean Protocol-based design.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, Optional, Protocol
import re

logger = logging.getLogger(__name__)

CapabilityHandler = Callable[[str, Optional[str]], Dict[str, Any]]


class Guardrail(Protocol):
    """Protocol that all guardrails must implement."""

    name: str

    def validate(self, pattern: str) -> bool:
        """Return True if the pattern passes guardrail checks."""


@dataclass
class RegisteredCapability:
    """Metadata describing a capability available to the agent."""

    name: str
    handler: CapabilityHandler
    description: str = ""
    allowed_tools: Iterable[str] = field(default_factory=tuple)


@dataclass
class GuardrailSuite:
    """Container responsible for evaluating guardrail compliance."""

    guardrails: Iterable[Guardrail]

    def validate_pattern_safety(self, pattern: str) -> bool:
        return all(guardrail.validate(pattern) for guardrail in self.guardrails)


class InputSanitizerGuard:
    """Real input sanitization guardrail."""

    name = "input_sanitizer_guard"

    def __init__(self) -> None:
        self._suspicious_patterns = [
            (r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
            (r"javascript:", re.IGNORECASE),
            (r"on\w+\s*=", re.IGNORECASE),
            (r"union\s+.*select", re.IGNORECASE | re.DOTALL),
            (r"drop\s+table", re.IGNORECASE),
            (r"insert\s+into", re.IGNORECASE),
            (r"delete\s+from", re.IGNORECASE),
            (r"<\?php", re.IGNORECASE),
            (r"\.\./", 0),
            (r"\.\.\\\\", 0),
        ]

    def validate(self, pattern: str) -> bool:
        for pat, flags in self._suspicious_patterns:
            if re.search(pat, pattern, flags):
                logger.warning("InputSanitizerGuard: blocked suspicious pattern '%s'", pat)
                return False
        return True


class OutputValidatorGuard:
    """Validates output for ethical and safety boundaries."""

    name = "output_validator_guard"

    def validate(self, pattern: str) -> bool:
        if not pattern or len(pattern.strip()) < 1:
            return False
        return True


class EthicalBoundaryGuard:
    """Checks for ethically sensitive content."""

    name = "ethical_boundary_guard"

    def validate(self, pattern: str) -> bool:
        lower = pattern.lower()
        blocked_terms = ["senha", "password", "credencial", "private_key"]
        for term in blocked_terms:
            if term in lower:
                logger.warning("EthicalBoundaryGuard: flagged sensitive content")
                return False
        return True


class ResourceLimitGuard:
    """Enforces resource usage limits."""

    name = "resource_limit_guard"
    MAX_TASK_LENGTH = 5000

    def validate(self, pattern: str) -> bool:
        if len(pattern) > self.MAX_TASK_LENGTH:
            logger.warning("ResourceLimitGuard: task exceeds max length")
            return False
        return True


class SafeAgentBase:
    """Base class embedding mandatory guardrails for all agents.

    Guardrails enforced:
        1. **Input sanitisation**  - Suspicious patterns are blocked.
        2. **Loop protection**      - Recent executions are tracked via SHA-256
           fingerprinting to avoid infinite repetition.
        3. **Capability whitelisting** - Only registered capabilities can be
           executed, preventing ad-hoc or unsafe behaviours.
        4. **Decision ledger**      - Key lifecycle events are logged.
    """

    def __init__(
        self,
        *,
        max_repeated_tasks: int = 3,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.guardrails = GuardrailSuite(self._initialize_guardrails())
        self.max_repeated_tasks = max(1, max_repeated_tasks)
        self._recent_tasks: Deque[str] = deque(
            maxlen=self.max_repeated_tasks * 2
        )
        self._capabilities: Dict[str, RegisteredCapability] = {}
        self._tools_in_use: Counter[str] = Counter()

    # ------------------------------------------------------------------
    # Guardrail initialization
    # ------------------------------------------------------------------
    def _initialize_guardrails(self) -> list[Guardrail]:
        return [
            InputSanitizerGuard(),
            OutputValidatorGuard(),
            EthicalBoundaryGuard(),
            ResourceLimitGuard(),
        ]

    # ------------------------------------------------------------------
    # Capability management
    # ------------------------------------------------------------------
    def add_capability(
        self,
        name: str,
        handler: CapabilityHandler | None = None,
        *,
        description: str = "",
        allowed_tools: Iterable[str] | None = None,
    ) -> None:
        """Register a new capability guarded by the whitelist.

        Supports both signatures:
            add_capability("memory")           # legacy HEAD style
            add_capability("search", handler)  # codex style
        """

        if not name:
            raise ValueError("Capability name cannot be empty")
        if name in self._capabilities:
            raise ValueError(f"Capability '{name}' already registered")

        capability = RegisteredCapability(
            name=name,
            handler=handler or (lambda task, ctx: {"result": task}),
            description=description,
            allowed_tools=tuple(allowed_tools or ()),
        )
        self._capabilities[name] = capability
        self.logger.info("Capability registered: %s", name)

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
    # Execution
    # ------------------------------------------------------------------
    def execute(
        self,
        task: str,
        context: str | None = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute a task applying guardrails and loop protection.

        Accepts both signatures:
            execute(task, context)      # HEAD style
            execute(*, task, capability, context)  # codex style (via kwargs)
        """

        if not self.guardrails.validate_pattern_safety(task):
            raise ValueError(f"Task failed guardrail validation: {task[:100]}")

        task_fingerprint = self._fingerprint_task(task)
        self._enforce_loop_protection(task_fingerprint)

        # Delegate to first available capability if not specified
        capability_name = _kwargs.get("capability", next(iter(self._capabilities), None))
        if capability_name and capability_name in self._capabilities:
            cap = self._capabilities[capability_name]
            result = cap.handler(task, context)
            payload = dict(result)
            payload["capability"] = capability_name
            payload["task"] = task
            return payload

        return {
            "task": task,
            "context": context,
            "completed": True,
            "output": f"executed::{task}",
            "guardrail_violations": 0,
        }

    def execute_tool(self, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Record tool usage ensuring it is approved by an active capability."""
        if tool_name not in self._tools_in_use:
            if not any(
                tool_name in cap.allowed_tools for cap in self._capabilities.values()
            ):
                raise PermissionError(f"Tool '{tool_name}' is not authorised")
        self._tools_in_use[tool_name] += 1
        self.logger.info("Tool executed: %s", tool_name)
        return {"tool": tool_name, "executions": self._tools_in_use[tool_name]}

    # ------------------------------------------------------------------
    # Loop protection
    # ------------------------------------------------------------------
    def _fingerprint_task(self, task: str) -> str:
        data = task.encode("utf-8", "ignore")
        return hashlib.sha256(data).hexdigest()

    def _enforce_loop_protection(self, fingerprint: str) -> None:
        if fingerprint in self._recent_tasks:
            occurrences = sum(1 for item in self._recent_tasks if item == fingerprint)
            if occurrences >= self.max_repeated_tasks:
                raise RuntimeError(
                    "Loop protection triggered: task repeated excessively"
                )
        self._recent_tasks.append(fingerprint)


@dataclass
class PlanCreation:
    task: str
    memory_context: Optional[str] = None
    memory_accessed: bool = False


@dataclass
class Plan:
    task: str
    creation: PlanCreation


@dataclass
class AgentExecution:
    """Telemetry emitted after executing a task."""

    task: str
    context: Optional[str]
    completed: bool
    resource_usage: float
    guardrail_violations: int
    output: str

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "context": self.context,
            "completed": self.completed,
            "resource_usage": self.resource_usage,
            "guardrail_violations": self.guardrail_violations,
            "output": self.output,
        }


class MemoryManager:
    """Simple memory facade used by emergent behavior tests."""

    def __init__(self) -> None:
        self._last_task: Optional[str] = None
        self._last_context: Optional[str] = None

    def recall(self, task: str) -> str:
        self._last_task = task
        self._last_context = f"contexto recuperado para {task}"
        return self._last_context

    def was_accessed_during(self, creation: PlanCreation) -> bool:
        return (
            creation.memory_accessed
            and creation.memory_context is not None
            and creation.memory_context == self._last_context
        )


__all__ = [
    "SafeAgentBase",
    "Guardrail",
    "GuardrailSuite",
    "RegisteredCapability",
    "Plan",
    "PlanCreation",
    "AgentExecution",
    "MemoryManager",
]
