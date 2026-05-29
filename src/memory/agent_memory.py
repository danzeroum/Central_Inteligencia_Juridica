"""High-level memory facade that wraps VectorMemory for agent usage.

Provides:
- Vector similarity search via VectorMemory (primary)
- JSONL episodic persistence for audit trails (optional)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.memory.vector_memory import VectorMemory

logger = logging.getLogger(__name__)


class AgentMemorySystem:
    """Convenience wrapper around :class:`VectorMemory` for RAG pipelines.

    Also supports optional JSONL episodic persistence for audit trails.
    """

    def __init__(
        self,
        vector_memory: VectorMemory | None = None,
        storage_dir: Optional[Path] = None,
    ) -> None:
        self.vector_memory = vector_memory or VectorMemory()
        self.logger = logging.getLogger(f"{__name__}.AgentMemorySystem")

        # Optional JSONL episodic persistence
        self.storage_dir = storage_dir or Path("logs/memory")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.episodic_path = self.storage_dir / "agent_memories.jsonl"

    def is_available(self) -> bool:
        """Return ``True`` if the underlying vector memory is available."""

        return self.vector_memory.is_available()

    def recall_similar(self, query: str, k: int = 3) -> Dict[str, Any]:
        """Retrieve context documents that are similar to ``query``."""

        if not query:
            return {"documents": [[]], "metadatas": [[]], "note": "empty_query"}

        results = self.vector_memory.recall_similar(query, k=k)
        if not results:
            return {"documents": [[]], "metadatas": [[]], "note": "no_memories"}

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for item in results:
            snapshot = item.get("result_snapshot")
            if isinstance(snapshot, str) and snapshot:
                documents.append(snapshot)
            else:
                documents.append(item.get("original_task") or "")

            metadatas.append(
                {
                    "similarity": float(item.get("similarity_score", 0.0)),
                    "tribunals": item.get("tribunals", []),
                    "timestamp": item.get("timestamp"),
                    "intent": (
                        item.get("intent_operacao")
                        or item.get("intent_operation")
                        or "unknown"
                    ),
                }
            )

        return {
            "documents": [documents],
            "metadatas": [metadatas],
            "note": "vector_memory_recall",
        }

    def remember(
        self,
        task: str,
        result: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> bool:
        """Persist an interaction using the underlying vector memory + JSONL."""

        vector_ok = self.vector_memory.remember(task, result, metadata)

        # Always persist to JSONL for audit trail
        try:
            memory = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task": task[:200],
                "metadata": metadata,
                "result_status": result.get("status", "unknown"),
            }
            with self.episodic_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(memory, ensure_ascii=False) + "\n")
        except OSError as exc:
            self.logger.warning("Failed to write episodic memory: %s", exc)

        return vector_ok
