"""RAG (Retrieval Augmented Generation) integration helper."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence

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

_GENERIC_NAMESPACE = "juridico_generico"


class RAGTool:
    """High-level helper that wraps :class:`VectorMemory` for RAG pipelines."""

    def __init__(
        self, memory: VectorMemory | None = None, **memory_kwargs: Any
    ) -> None:
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

    def similarity_search(
        self, query_embeddings: Iterable[List[float]], n_results: int = 3
    ) -> List[str]:
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

    # --- Namespace-aware methods (Item 12) ---

    def add_documents_to_namespace(
        self,
        namespace: str,
        documents: Sequence[Dict[str, Any]],
    ) -> None:
        """Persiste documentos em coleção de área jurídica específica."""
        collection = self.memory.get_or_create_collection(namespace)
        if collection is None:
            logger.warning(
                "Namespace '%s' indisponível, ignorando ingestão.", namespace
            )
            return

        ids: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        texts: List[str] = []

        for doc in documents:
            text = doc.get("content") or doc.get("text")
            if not text:
                continue
            ids.append(str(doc.get("id") or uuid.uuid4()))
            meta = dict(doc.get("metadata") or {})
            meta["namespace"] = namespace
            metadatas.append(meta)
            texts.append(text)

        if not texts:
            return

        try:
            collection.add(ids=ids, metadatas=metadatas, documents=texts)
            logger.info(
                "Ingeridos %d documentos no namespace '%s'.", len(texts), namespace
            )
        except Exception as exc:
            logger.error("Falha ao ingerir no namespace '%s': %s", namespace, exc)

    def query_with_filter(
        self,
        query: str,
        namespace: str,
        n_results: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Consulta com filtro por namespace e score mínimo."""
        collection = self.memory.get_or_create_collection(namespace)
        if collection is None:
            return []
        if not query:
            return []
        try:
            result = collection.query(
                query_texts=[query],
                n_results=max(1, n_results),
            )
        except Exception as exc:
            logger.error("Falha ao consultar namespace '%s': %s", namespace, exc)
            return []

        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        out = []
        for doc, meta, dist in zip(docs, metas, distances):
            if not doc:
                continue
            score = max(0.0, 1.0 - (dist / 2.0))
            if score >= min_score:
                out.append({"text": doc, "metadata": meta, "score": score})
        return out

    def query_rag(
        self,
        query: str,
        areas: Optional[List[str]] = None,
        n_results: int = 5,
        max_namespaces: int = 4,
    ) -> List[Dict[str, Any]]:
        """Busca no namespace genérico + até `max_namespaces` áreas específicas.

        Resultado das áreas específicas recebe peso 1.5x para priorizar
        conteúdo mais relevante ao perfil do usuário.
        """
        if not query:
            return []

        results: List[Dict[str, Any]] = []

        # Sempre busca no namespace genérico
        generic = self.query_with_filter(query, _GENERIC_NAMESPACE, n_results)
        results.extend(generic)

        # Áreas específicas do perfil (limitado a max_namespaces)
        limited_areas = (areas or [])[:max_namespaces]
        for area in limited_areas:
            if area == _GENERIC_NAMESPACE:
                continue
            area_results = self.query_with_filter(query, area, n_results)
            for r in area_results:
                r["score"] = r.get("score", 0.0) * 1.5  # peso 1.5x
            results.extend(area_results)

        # Ordena por score descendente e deduplica
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for r in sorted(results, key=lambda x: x.get("score", 0.0), reverse=True):
            key = r.get("text", "")[:100]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique[: n_results * 2]


__all__ = ["RAGTool"]
