"""Vector Memory System powered by ChromaDB and OpenAI Embeddings."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - import guard for optional dependency
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except ImportError:  # pragma: no cover - handled gracefully at runtime
    chromadb = None
    Settings = None
    embedding_functions = None

logger = logging.getLogger(__name__)


class VectorMemory:
    """Manages long-term agent memory using ChromaDB with OpenAI embeddings."""

    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        collection_name: str = "tribunal_interactions",
    ) -> None:
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.collection_name = collection_name

        self.client: Optional[Any] = None
        self.collection: Optional[Any] = None

        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize connection to ChromaDB with retry logic."""

        if chromadb is None or Settings is None or embedding_functions is None:
            logger.error(
                "chromadb package not installed. Install dependencies from requirements.txt."
            )
            self.client = None
            self.collection = None
            return

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                self.client = chromadb.HttpClient(
                    host=self.chroma_host,
                    port=self.chroma_port,
                    settings=Settings(
                        anonymized_telemetry=False
                    )
                )

                # Verificar conexão
                self.client.heartbeat()

                # Configurar embedding function da OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.warning(
                        "OPENAI_API_KEY not set. Memory will not work properly."
                    )
                    return

                openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                    api_key=api_key,
                    model_name="text-embedding-3-small"
                )

                # Obter ou criar coleção
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=openai_ef,
                    metadata={"description": "Long-term memory for tribunal agent interactions"}
                )

                logger.info(
                    "VectorMemory connected to ChromaDB at %s:%d (collection=%s)",
                    self.chroma_host,
                    self.chroma_port,
                    self.collection_name,
                )
                return

            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "Failed to connect to ChromaDB (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(
                        "Could not connect to ChromaDB after %d attempts. "
                        "Memory features will be disabled.",
                        max_retries,
                    )
                    self.client = None
                    self.collection = None

    def is_available(self) -> bool:
        """Check if memory system is available."""
        return self.client is not None and self.collection is not None

    def remember(
        self,
        task: str,
        result: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Store an interaction in long-term memory.

        Args:
            task: User's original task description
            result: Agent's result/response
            metadata: Additional context (tribunals, intent, confidence, etc.)

        Returns:
            True if stored successfully, False otherwise
        """
        if not self.is_available():
            logger.warning("Cannot remember: VectorMemory not available")
            return False

        try:
            interaction_id = str(uuid.uuid4())

            # Evitar mutar metadata original
            metadata = dict(metadata)

            # Criar documento rico para embedding
            document = self._create_document(task, result, metadata)

            # Adicionar timestamp ao metadata se não existir
            if "timestamp" not in metadata:
                metadata["timestamp"] = time.time()

            # Adicionar task original ao metadata para facilitar debugging
            metadata["original_task"] = task[:200]  # Limitar tamanho

            start = time.perf_counter()

            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[interaction_id]
            )

            elapsed = time.perf_counter() - start

            logger.info(
                "Memory stored: id=%s, tribunals=%s, time=%.3fs",
                interaction_id[:8],
                metadata.get("tribunals", []),
                elapsed,
            )

            return True

        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to remember interaction: %s", exc, exc_info=True)
            return False

    def recall_similar(
        self,
        query: str,
        k: int = 3,
        min_similarity: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve K most similar past interactions.

        Args:
            query: User's current task/question
            k: Number of memories to retrieve
            min_similarity: Minimum similarity score (0-1)

        Returns:
            List of metadata dicts from similar past interactions
        """
        if not self.is_available():
            logger.warning("Cannot recall: VectorMemory not available")
            return []

        try:
            start = time.perf_counter()

            results = self.collection.query(
                query_texts=[query],
                n_results=k,
            )

            elapsed = time.perf_counter() - start

            # Extrair metadatas
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            # Filtrar por similaridade mínima
            # ChromaDB retorna L2 distance; menor = mais similar
            # Converter para similarity score (1 - normalized_distance)
            recalled = []
            for metadata, distance in zip(metadatas, distances):
                # Normalizar distância para similarity (aproximação)
                similarity = max(0.0, 1.0 - (distance / 2.0))

                if similarity >= min_similarity:
                    metadata["similarity_score"] = similarity
                    recalled.append(metadata)

            logger.info(
                "Memory recall: query='%s', found=%d/%d, time=%.3fs",
                query[:50],
                len(recalled),
                k,
                elapsed,
            )

            return recalled

        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to recall memories: %s", exc, exc_info=True)
            return []

    def _create_document(
        self,
        task: str,
        result: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> str:
        """Create rich document for embedding."""

        # Incluir contexto estruturado para melhor embedding
        operation = metadata.get("intent_operacao") or metadata.get(
            "intent_operation",
            "unknown",
        )

        parts = [
            f"User Task: {task}",
            f"Tribunals: {', '.join(metadata.get('tribunals', []))}",
            f"Operation: {operation}",
        ]

        # Adicionar resultado se não for muito grande
        result_str = json.dumps(result, ensure_ascii=False)[:500]
        parts.append(f"Result: {result_str}")

        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        if not self.is_available():
            return {
                "status": "unavailable",
                "total_memories": 0,
            }

        try:
            count = self.collection.count()
            return {
                "status": "healthy",
                "total_memories": count,
                "collection": self.collection_name,
                "host": f"{self.chroma_host}:{self.chroma_port}",
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to get memory stats: %s", exc)
            return {
                "status": "error",
                "error": str(exc),
            }


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    # Demo de uso
    logging.basicConfig(level=logging.INFO)

    memory = VectorMemory()

    if not memory.is_available():
        print("❌ ChromaDB not available. Start with: docker-compose up -d chromadb")
        raise SystemExit(1)

    # Teste 1: Armazenar memória
    print("\n🧠 Teste 1: Storing memory...")
    success = memory.remember(
        task="Qual o status do TJSP?",
        result={"tribunal": "TJSP", "status": "operacional"},
        metadata={
            "tribunals": ["TJSP"],
            "intent_operacao": "status_check",
            "confidence": 0.95,
        }
    )
    print(f"   Stored: {success}")

    # Aguardar indexação
    time.sleep(2)

    # Teste 2: Recuperar memória
    print("\n🔍 Teste 2: Recalling similar memory...")
    recalled = memory.recall_similar("Como está o sistema de São Paulo?", k=1)
    print(f"   Recalled {len(recalled)} memories")
    if recalled:
        print(f"   - Task: {recalled[0].get('original_task')}")
        print(f"   - Similarity: {recalled[0].get('similarity_score', 0):.2f}")

    # Teste 3: Estatísticas
    print("\n📊 Teste 3: Memory stats...")
    stats = memory.get_stats()
    print(f"   Total memories: {stats.get('total_memories')}")
    print(f"   Status: {stats.get('status')}")
