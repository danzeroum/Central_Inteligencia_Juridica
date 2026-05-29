"""RAG (Retrieval Augmented Generation) integration helper."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Iterable, List, Sequence

# TODO: Upgrade to ChromaDB 0.5.0+ when stable (see ADR-012)
# Current version 0.4.18 requires NumPy < 2.0
# Breaking changes expected in 0.5.0 API - will need refactoring

try:  # pragma: no cover - optional dependency
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
except Exception:  # pragma: no cover - fallback
    chromadb = None  # type: ignore[assignment]
    Settings = None  # type: ignore[assignment]

from src.memory.vector_memory import VectorMemory

logger = logging.getLogger(__name__)


class RAGTool:
    """High-level helper that wraps :class:`VectorMemory` for RAG pipelines."""

    def __init__(self, memory: VectorMemory | None = None, **memory_kwargs: Any) -> None:
        self.memory = memory or VectorMemory(**memory_kwargs)

    def is_available(self) -> bool:
        """Return True when ChromaDB collection is ready to be used."""

        return bool(self.memory.collection)

    def add_documents(self, documents: Sequence[dict[str, Any]] | None) -> None:
        """Persist documents in the vector store if available."""

        if not documents:
            return

        if not self.is_available():
            logger.warning("RAGTool unavailable, skipping document ingestion.")
            return

        ids: List[str] = []
        metadatas: List[dict[str, Any]] = []
        texts: List[str] = []

        for document in documents:
            text = document.get("content") or document.get("text")
            if not text:
                continue

            ids.append(str(document.get("id") or uuid.uuid4()))
            metadatas.append(document.get("metadata") or {})
            texts.append(text)

        if not texts:
            logger.debug("No valid documents provided for ingestion.")
            return

        try:
            self.memory.collection.add(  # type: ignore[union-attr]
                ids=ids,
                metadatas=metadatas,
                documents=texts,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to ingest documents into ChromaDB: %s", exc)

    def query(self, query: str, n_results: int = 3) -> List[str]:
        """Retrieve the top matching documents for the provided query."""

        if not query:
            return []

        if not self.is_available():
            logger.warning("RAGTool unavailable, returning empty results.")
            return []

        try:
            result = self.memory.collection.query(  # type: ignore[union-attr]
                query_texts=[query],
                n_results=max(1, n_results),
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to query ChromaDB: %s", exc)
            return []

        documents = result.get("documents") or []
        if not documents:
            return []

        return [doc for doc in documents[0] if doc]

    def similarity_search(self, query_embeddings: Iterable[List[float]], n_results: int = 3) -> List[str]:
        """Query the store using pre-computed embeddings (fallback when needed)."""

        if not self.is_available():
            logger.warning("RAGTool unavailable, returning empty results.")
            return []

        try:
            result = self.memory.collection.query(  # type: ignore[union-attr]
                query_embeddings=list(query_embeddings),
                n_results=max(1, n_results),
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to query ChromaDB with embeddings: %s", exc)
            return []

        documents = result.get("documents") or []
        if not documents:
            return []

        return [doc for doc in documents[0] if doc]


__all__ = ["RAGTool"]
