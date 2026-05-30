#!/usr/bin/env python3
"""
================================================================================
 FASE 2 - PARTE 2: Stubs e modulos ausentes
 Cria todos os modulos que origin/codex referencia mas que nao existem no repo
================================================================================

Uso:
  python fase2-stubs.py [--dry-run]

Executar APOS fase2-resolve.py na raiz do repositorio.
================================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def create_stubs(dry_run: bool = False) -> list[tuple[bool, str]]:
    results = []

    stubs: dict[str, str] = {
        # ── Protocols ──
        "src/protocols/__init__.py": '"""Agent communication protocols."""\n',
        "src/protocols/a2a_mixin.py": '''"""Agent-to-Agent communication mixin."""

from __future__ import annotations

import logging
from typing import Any, Dict


class A2ACapable:
    """Mixin providing Agent-to-Agent communication capabilities."""

    def __init__(self) -> None:
        self._a2a_handlers: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)

    def register_a2a_handler(self, message_type: str, handler: Any) -> None:
        """Register a handler for a specific A2A message type."""
        self._a2a_handlers[message_type] = handler

    async def send_a2a_message(
        self, target: str, message_type: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a message to another agent."""
        return {"status": "success", "target": target, "message_type": message_type}
''',
        "src/protocols/a2a_channel.py": '''"""Agent-to-Agent communication channel."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class A2AMessage:
    """A message sent between agents."""

    def __init__(
        self,
        sender: str,
        receiver: str,
        message_type: str,
        payload: Dict[str, Any],
    ) -> None:
        self.sender = sender
        self.receiver = receiver
        self.message_type = message_type
        self.payload = payload


class A2AChannel:
    """Communication channel for agent-to-agent messaging."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List] = {}

    def subscribe(self, agent_id: str, handler: Any) -> None:
        self._subscribers.setdefault(agent_id, []).append(handler)

    async def broadcast(self, message: A2AMessage) -> List[Dict[str, Any]]:
        results = []
        for agent_id, handlers in self._subscribers.items():
            for handler in handlers:
                try:
                    result = await handler(message)
                    results.append({"agent": agent_id, "result": result})
                except Exception as exc:
                    logger.warning("A2A broadcast to %s failed: %s", agent_id, exc)
        return results


_default_channel: Optional[A2AChannel] = None


def get_a2a_channel() -> A2AChannel:
    global _default_channel
    if _default_channel is None:
        _default_channel = A2AChannel()
    return _default_channel
''',

        # ── Memory ──
        "src/memory/vector_memory.py": '''"""Vector memory abstraction for semantic search and RAG."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    import chromadb  # type: ignore
except Exception:
    chromadb = None  # type: ignore


class VectorMemory:
    """Vector memory store using ChromaDB with graceful degradation."""

    def __init__(self) -> None:
        self._client = None
        self._collection = None
        self._available = False
        self._manual_embeddings = True

        if chromadb is not None:
            try:
                self._client = chromadb.Client(
                    chromadb.Settings(
                        chroma_server_host="localhost",
                        chroma_server_http_port=8000,
                    )
                )
                try:
                    self._collection = self._client.create_collection("agent_memories")
                except Exception:
                    self._collection = self._client.get_collection("agent_memories")
                self._available = True
            except Exception as exc:
                logger.warning("ChromaDB unavailable: %s", exc)
        else:
            logger.info("ChromaDB not installed. Memory features disabled.")

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def using_manual_embeddings(self) -> bool:
        return self._manual_embeddings

    def recall_similar(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Recall similar items from vector store."""
        if not self._available or self._collection is None:
            return []
        try:
            results = self._collection.query(query_texts=[query], n_results=k)
            return self._format_results(results)
        except Exception as exc:
            logger.warning("Vector recall failed: %s", exc)
            return []

    def remember(
        self, task: str, result: Dict[str, Any], metadata: Dict[str, Any]
    ) -> bool:
        """Store a new memory entry."""
        if not self._available or self._collection is None:
            return False
        try:
            self._collection.add(
                documents=[task[:200]],
                metadatas=[{
                    "tribunals": str(metadata.get("tribunals", [])),
                    "intent_operacao": metadata.get("intent_operacao", ""),
                    "timestamp": metadata.get("timestamp", ""),
                }],
                ids=[f"mem_{len(task)}_{hash(task) % 100000:05d}"],
            )
            return True
        except Exception as exc:
            logger.warning("Vector store failed: %s", exc)
            return False

    def _format_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format ChromaDB query results into structured dicts."""
        formatted = []
        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])

        for i, doc_list in enumerate(documents):
            for j, doc in enumerate(doc_list):
                meta = {}
                if metadatas and i < len(metadatas) and j < len(metadatas[i]):
                    meta = metadatas[i][j]
                distance = 0.0
                if distances and i < len(distances) and j < len(distances[i]):
                    distance = distances[i][j]

                import ast
                tribunals = meta.get("tribunals", "[]")
                try:
                    tribunals = ast.literal_eval(str(tribunals))
                except (ValueError, SyntaxError):
                    tribunals = []

                formatted.append({
                    "original_task": doc,
                    "similarity_score": max(0.0, 1.0 - distance),
                    "tribunals": tribunals if isinstance(tribunals, list) else [],
                    "intent_operacao": meta.get("intent_operacao", ""),
                    "timestamp": meta.get("timestamp", ""),
                })
        return formatted
''',

        # ── Routing ──
        "src/routing/intent_classifier.py": '''"""Intent classifier for legal task routing."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedIntent:
    """Result of intent classification."""

    tribunais: List[str] = field(default_factory=lambda: ["TJSP"])
    operacao: str = "generic"
    parametros: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    reasoning: str = ""

    def model_dump(self) -> Dict[str, Any]:
        return {
            "tribunais": self.tribunais,
            "operacao": self.operacao,
            "parametros": self.parametros,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


class IntentClassifier:
    """Classify legal task intents for routing."""

    def __init__(self, confidence_threshold: float = 0.7) -> None:
        self.confidence_threshold = confidence_threshold
        self.llm_enabled = False
        self.logger = logging.getLogger(__name__)

    def should_use_llm(self, task: str) -> bool:
        return False

    async def classify(self, task: str) -> ClassifiedIntent:
        return ClassifiedIntent(
            tribunais=["TJSP"],
            operacao="generic",
            confidence=0.5,
            reasoning="Keyword fallback - LLM not enabled",
        )
''',

        # ── Utils ──
        "src/utils/decision_metrics.py": '''"""Decision metrics collector for tracking agent performance."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class DecisionMetricsCollector:
    """Collect and aggregate decision metrics for monitoring."""

    _decisions: List[Dict[str, Any]] = []

    @classmethod
    def record_decision(
        cls,
        agent: str,
        decision_type: str,
        outcome: str,
        confidence: float,
        duration_seconds: float,
    ) -> None:
        cls._decisions.append({
            "agent": agent,
            "decision_type": decision_type,
            "outcome": outcome,
            "confidence": confidence,
            "duration_seconds": duration_seconds,
        })

    @classmethod
    def record_consensus(
        cls,
        decision_type: str,
        strength: float,
        participants: int,
        winning_agent: str,
        outcome: str,
    ) -> None:
        cls._decisions.append({
            "decision_type": f"consensus_{decision_type}",
            "consensus_strength": strength,
            "participants": participants,
            "winning_agent": winning_agent,
            "outcome": outcome,
        })

    @classmethod
    def record_hitl_request(cls, agent: str, status: str = "pending") -> None:
        cls._decisions.append({"agent": agent, "decision_type": "hitl_request", "status": status})
''',

        # ── HITL ──
        "src/hitl/hitl_queue.py": '''"""Human-in-the-loop queue for pending reviews."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HITLRequest:
    """A request pending human review."""

    request_id: str
    agent: str
    reason: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"


@dataclass
class HITLQueue:
    """Queue for managing HITL requests."""

    _queue: deque = field(default_factory=deque)

    def enqueue(self, request: HITLRequest) -> None:
        self._queue.append(request)

    def dequeue(self) -> Optional[HITLRequest]:
        return self._queue.popleft() if self._queue else None

    def pending_count(self) -> int:
        return len(self._queue)


_default_queue: Optional[HITLQueue] = None


def get_hitl_queue() -> HITLQueue:
    global _default_queue
    if _default_queue is None:
        _default_queue = HITLQueue()
    return _default_queue
''',

        # ── Tools ──
        "src/tools/circuit_breaker.py": '''"""Circuit breaker pattern for resilient service calls."""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker with configurable thresholds."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "default",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._last_state_change: float = 0.0

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise RuntimeError(f"Circuit breaker '{self.name}' is OPEN")
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        self._failure_count = 0
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self._last_state_change = time.monotonic()

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self._last_state_change = time.monotonic()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
''',

        # ── Services ──
        "src/services/__init__.py": '"""External service integrations."""\n',
        "src/services/camara_client.py": '''"""Camara dos Deputados API client for legislative data."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class CamaraClient:
    """Client for the Camara dos Deputados open data API."""

    BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"

    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.Client(timeout=timeout)
        self.logger = logging.getLogger(__name__)

    def search_projetos(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for legislative projects (projetos de lei)."""
        try:
            response = self._client.get(
                f"{self.BASE_URL}/proposicoes",
                params={"keywords": query, "itens": limit},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("dados", [])
        except Exception as exc:
            self.logger.warning("Camara API search failed: %s", exc)
            return []

    def close(self) -> None:
        self._client.close()
''',

        # ── Training ──
        "src/training/__init__.py": '"""Agent training utilities."""\n',
        "src/safety/__init__.py": '"""Safety and guardrails package."""\n',
        "src/chains/__init__.py": '"""Chains for sequential agent orchestration."""\n',
        "src/parallel/__init__.py": '"""Parallel execution utilities."""\n',
        "src/planning/__init__.py": '"""Task planning utilities."""\n',
        "src/protocols/safety_protocol.py": '''"""Safety protocol for agent interactions."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SafetyProtocol:
    """Protocol for enforcing safety constraints on agent outputs."""

    def validate_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        return output
''',

        # ── Config ──
        "src/config.py": '''"""Application configuration via environment variables."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = ""
    db_password: str = ""
    db_name: str = "central_inteligencia"

    redis_url: str = "redis://localhost:6379/0"

    chroma_host: str = "localhost"
    chroma_port: int = 8000

    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
''',
    }

    for filepath, content in stubs.items():
        path = Path(filepath)
        if path.exists():
            results.append((True, f"[SKIP] {filepath} (ja existe)"))
            continue

        if dry_run:
            results.append((True, f"[DRY-RUN] Criaria {filepath}"))
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        # Verify syntax for .py files
        if filepath.endswith(".py"):
            import py_compile
            try:
                py_compile.compile(str(path), doraise=True)
                results.append((True, f"[OK] {filepath} criado + sintaxe OK"))
            except py_compile.PyCompileError as exc:
                results.append((False, f"[SYNTAX ERROR] {filepath}: {exc}"))
        else:
            results.append((True, f"[OK] {filepath} criado"))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 2 Part 2: Create missing module stubs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 78)
    print("  FASE 2 - PARTE 2: Stubs e Modulos Ausentes")
    print("=" * 78)
    print()

    results = create_stubs(dry_run=args.dry_run)
    for ok, msg in results:
        color = "\033[92m" if ok else "\033[91m"
        print(f"  {color}{msg}\033[0m")

    total_ok = sum(1 for ok, _ in results if ok)
    total = len(results)
    print()
    print(f"  Total: {total_ok}/{total} modulos criados com sucesso")

    if args.dry_run:
        print()
        print("  MODO DRY-RUN - Remova --dry-run para criar os arquivos")

    print("=" * 78)


if __name__ == "__main__":
    main()
