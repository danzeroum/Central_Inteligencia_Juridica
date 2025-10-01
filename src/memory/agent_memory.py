<<<<<<< HEAD
"""Persistent memory management utilities for agents."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
except Exception:  # pragma: no cover - fallback
    chromadb = None
    Settings = None  # type: ignore


class _FallbackCollection:
    def __init__(self) -> None:
        self._items: List[Dict[str, Any]] = []

    def add(self, *, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> None:
        for doc, meta, id_ in zip(documents, metadatas, ids):
            self._items.append({"id": id_, "document": doc, "metadata": meta})

    def query(self, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
        return {"ids": [], "metadatas": [], "documents": [], "query": query_texts, "n_results": n_results}


class AgentMemorySystem:
    """Manage short, long, and episodic memories for agents."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self.short_term: Dict[str, Any] = {}
        self.storage_dir = storage_dir or Path(".buildtoflip/ledger")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.episodic_path = self.storage_dir / "agent_memories.jsonl"

        self.collection = self._initialise_vector_store()

    def _initialise_vector_store(self):
        if chromadb is None or Settings is None:
            return _FallbackCollection()

        try:
            client = chromadb.Client(
                Settings(
                    chroma_server_host="localhost",
                    chroma_server_http_port=8000,
                    chroma_client_auth_provider="no_auth",  # matches open-source container defaults
                )
            )
            try:
                return client.create_collection("agent_memories")
            except Exception:
                return client.get_collection("agent_memories")
        except Exception:
            return _FallbackCollection()

    def remember_decision(self, agent: str, decision: Dict[str, Any]) -> None:
        """Persist an important decision to disk and vector storage."""

        memory = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "decision": decision,
            "confidence": float(decision.get("confidence", 0.0)),
        }
        with self.episodic_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(memory, ensure_ascii=False) + "\n")

        self.collection.add(
            documents=[json.dumps(decision, ensure_ascii=False)],
            metadatas=[{"agent": agent, "timestamp": memory["timestamp"]}],
            ids=[f"{agent}_{memory['timestamp']}"],
        )

    def recall_similar(self, query: str, k: int = 5) -> Dict[str, Any]:
        """Retrieve similar memories using the vector database (or fallback)."""

        return self.collection.query(query_texts=[query], n_results=k)
=======
"""High-level memory facade that wraps VectorMemory for agent usage."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.memory.vector_memory import VectorMemory

logger = logging.getLogger(__name__)


class AgentMemorySystem:
    """Convenience wrapper around :class:`VectorMemory` for RAG pipelines."""

    def __init__(self, vector_memory: VectorMemory | None = None) -> None:
        self.vector_memory = vector_memory or VectorMemory()
        self.logger = logging.getLogger(f"{__name__}.AgentMemorySystem")

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
                    "intent": item.get("intent_operacao")
                    or item.get("intent_operation")
                    or "unknown",
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
        """Persist an interaction using the underlying vector memory."""

        return self.vector_memory.remember(task, result, metadata)

>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
