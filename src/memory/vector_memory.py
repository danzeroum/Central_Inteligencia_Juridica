"""Vector Memory System powered by ChromaDB and OpenAI Embeddings."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - import guard for optional dependency
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except (
    ImportError,
    AttributeError,
):  # pragma: no cover - handled gracefully at runtime
    chromadb = None
    Settings = None
    embedding_functions = None

logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


class HashEmbeddingFunction:
    """Deterministic embedding fallback when OpenAI embeddings are unavailable."""

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def __call__(
        self, input: List[str]
    ) -> List[List[float]]:  # pragma: no cover - simple math
        embeddings: List[List[float]] = []
        for text in input:
            vector = [0.0] * self.dimensions
            if not text:
                embeddings.append(vector)
                continue

            encoded = text.encode("utf-8", "ignore")
            for idx, byte in enumerate(encoded):
                bucket = idx % self.dimensions
                vector[bucket] += byte / 255.0

            tokens = text.lower().split()
            if not tokens:
                tokens = [text]

            for token in tokens:
                digest = hashlib.sha256(token.encode("utf-8", "ignore")).digest()
                for offset in range(0, len(digest), 4):
                    chunk = digest[offset : offset + 4]
                    if not chunk:
                        continue
                    bucket = int.from_bytes(chunk, "big") % self.dimensions
                    vector[bucket] += 1.0

            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            embeddings.append([value / norm for value in vector])
        return embeddings


class VectorMemory:
    """Manages long-term agent memory using ChromaDB with OpenAI embeddings."""

    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        collection_name: str = "tribunal_interactions",
        persist_directory: str | None = None,
    ) -> None:
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.collection_name = collection_name
        self.persist_directory = (
            Path(persist_directory)
            if persist_directory is not None
            else Path(os.getenv("VECTOR_MEMORY_PERSIST_PATH", ".vector_memory"))
        )

        self.mode = (os.getenv("VECTOR_MEMORY_MODE", "auto").strip().lower()) or "auto"

        self.client: Optional[Any] = None
        self.collection: Optional[Any] = None
        self._use_manual_embeddings = False
        self._hash_embedding = HashEmbeddingFunction()

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

        mode = self.mode

        if mode not in {"auto", "remote", "local"}:
            logger.warning(
                "Unknown VECTOR_MEMORY_MODE '%s'. Falling back to auto.", mode
            )
            mode = "auto"

        api_key = os.getenv("OPENAI_API_KEY")

        if mode in {"auto", "remote"}:
            if api_key is None and mode == "remote":
                logger.warning(
                    "VECTOR_MEMORY_MODE=remote but OPENAI_API_KEY not set. Skipping remote setup."
                )
            else:
                if self._initialize_http_client(api_key):
                    return
                if mode == "remote":
                    return

        if mode in {"auto", "local"}:
            self._initialize_local_client(api_key)

    def _initialize_http_client(self, api_key: Optional[str]) -> bool:
        """Try to configure HTTP client. Returns True if successful."""

        if api_key is None:
            logger.warning(
                "OPENAI_API_KEY not set. Skipping HTTP VectorMemory initialization."
            )
            return False

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                self.client = chromadb.HttpClient(
                    host=self.chroma_host,
                    port=self.chroma_port,
                    settings=Settings(anonymized_telemetry=False),
                )

                # Verificar conexão
                self.client.heartbeat()

                embedding_function = self._resolve_embedding_function(api_key)

                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=embedding_function,
                    metadata={
                        "description": "Long-term memory for tribunal agent interactions",
                        "mode": "remote",
                    },
                )

                logger.info(
                    "VectorMemory connected to ChromaDB at %s:%d (collection=%s)",
                    self.chroma_host,
                    self.chroma_port,
                    self.collection_name,
                )
                self.mode = "remote"
                self._use_manual_embeddings = False
                return True

            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "Failed to connect to ChromaDB (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    logger.error(
                        "Could not connect to ChromaDB after %d attempts. "
                        "Memory features will be disabled.",
                        max_retries,
                    )
                    self.client = None
                    self.collection = None
        return False

    def _initialize_local_client(self, api_key: Optional[str]) -> None:
        """Configure an embedded Chroma client for local/offline usage."""

        try:
            self.persist_directory.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to prepare local persist directory: %s", exc)

        try:
            # Desabilita a telemetria anônima do ChromaDB (PostHog), que faz
            # chamadas de rede de saída — problemáticas em runners de CI com rede
            # restrita. O cliente HTTP já fazia isso; alinhamos o cliente local.
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(anonymized_telemetry=False),
            )

            embedding_function = None
            if api_key:
                embedding_function = self._resolve_embedding_function(api_key)
                self._use_manual_embeddings = False
            else:
                # Sem API key: usamos a HashEmbeddingFunction determinística como
                # embedding_function da coleção. Isso impede que o ChromaDB use seu
                # modelo ONNX padrão (ONNXMiniLM_L6_V2), que baixa um modelo pela
                # rede no primeiro uso — o que falha em runners de CI com rede
                # restrita. Mantém os testes herméticos e o CI determinístico.
                embedding_function = self._hash_embedding
                self._use_manual_embeddings = True

            collection_kwargs = {
                "name": self.collection_name,
                "metadata": {
                    "description": "Long-term memory for tribunal agent interactions",
                    "mode": "local",
                },
            }

            if embedding_function is not None:
                collection_kwargs["embedding_function"] = embedding_function

            self.collection = self.client.get_or_create_collection(**collection_kwargs)

            logger.info(
                "VectorMemory using local Chroma persistence at %s (collection=%s)",
                self.persist_directory,
                self.collection_name,
            )
            self.mode = "local"
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to initialize local VectorMemory client: %s", exc)
            self.client = None
            self.collection = None

    def _resolve_embedding_function(self, api_key: Optional[str]):
        """Return appropriate embedding function depending on environment."""

        if api_key:
            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=api_key,
                model_name="text-embedding-3-small",
            )

        logger.info(
            "OPENAI_API_KEY not set. Falling back to deterministic hash embeddings."
        )
        return HashEmbeddingFunction()

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

            # Persistir um snapshot compacto do resultado para cache futuro
            try:
                metadata["result_snapshot"] = json.dumps(result, ensure_ascii=False)
            except (TypeError, ValueError):
                logger.debug("Result snapshot could not be serialized for memory cache")

            # Criar documento rico para embedding
            document = self._create_document(task, result, metadata)

            # Adicionar timestamp ao metadata se não existir
            if "timestamp" not in metadata:
                metadata["timestamp"] = time.time()

            # Adicionar task original ao metadata para facilitar debugging
            metadata["original_task"] = task[:200]  # Limitar tamanho

            metadata = self._prepare_metadata_for_storage(metadata)

            start = time.perf_counter()

            add_kwargs: Dict[str, Any] = {}
            if self._use_manual_embeddings:
                add_kwargs["embeddings"] = [self._compute_manual_embedding(task)]
                metadata.setdefault("_embedding_mode", "hash")

            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[interaction_id],
                **add_kwargs,
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
        min_similarity: float | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve K most similar past interactions.

        Args:
            query: User's current task/question
            k: Number of memories to retrieve
            min_similarity: Minimum similarity score (0-1). If ``None`` the
                adaptive threshold is used (default behaviour).

        Returns:
            List of metadata dicts from similar past interactions
        """
        if not self.is_available():
            logger.warning("Cannot recall: VectorMemory not available")
            return []

        try:
            if min_similarity is None:
                min_similarity = 0.7
                adaptive_threshold = True
            else:
                adaptive_threshold = False

            start = time.perf_counter()

            query_kwargs: Dict[str, Any] = {"n_results": k}
            if self._use_manual_embeddings:
                query_kwargs["query_embeddings"] = [
                    self._compute_manual_embedding(query)
                ]
            else:
                query_kwargs["query_texts"] = [query]

            results = self.collection.query(**query_kwargs)

            elapsed = time.perf_counter() - start

            # Extrair metadatas
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            # Filtrar por similaridade mínima
            # ChromaDB retorna L2 distance; menor = mais similar
            # Converter para similarity score (1 - normalized_distance)
            recalled = []
            effective_min_similarity = min_similarity
            if self._use_manual_embeddings and adaptive_threshold:
                effective_min_similarity = 0.1

            for metadata, distance in zip(metadatas, distances):
                metadata_copy = self._restore_metadata(metadata)
                # Normalizar distância para similarity (aproximação)
                similarity = max(0.0, 1.0 - (distance / 2.0))

                if similarity >= effective_min_similarity:
                    metadata_copy["similarity_score"] = similarity
                    recalled.append(metadata_copy)

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

    def _prepare_metadata_for_storage(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Convert metadata into Chroma-friendly primitives."""

        sanitized: Dict[str, Any] = {}
        json_serialized_keys: List[str] = []

        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                sanitized[key] = value
            else:
                try:
                    sanitized[key] = json.dumps(value, ensure_ascii=False)
                except (TypeError, ValueError):
                    sanitized[key] = str(value)
                else:
                    json_serialized_keys.append(key)

        if json_serialized_keys:
            sanitized["_json_fields"] = json.dumps(json_serialized_keys)

        return sanitized

    def _restore_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Restore metadata to original rich types when possible."""

        restored = dict(metadata)
        json_fields_raw = restored.pop("_json_fields", None)

        json_fields: List[str] = []
        if isinstance(json_fields_raw, str):
            try:
                parsed = json.loads(json_fields_raw)
                if isinstance(parsed, list):
                    json_fields = [str(item) for item in parsed]
            except (TypeError, ValueError):
                json_fields = []

        for key in json_fields:
            value = restored.get(key)
            if isinstance(value, str):
                try:
                    restored[key] = json.loads(value)
                except (TypeError, ValueError):
                    # Keep original string if not valid JSON
                    pass

        return restored

    def _compute_manual_embedding(self, text: str) -> List[float]:
        """Generate deterministic embedding used for offline/local mode."""

        return self._hash_embedding([text])[0]

    @property
    def using_manual_embeddings(self) -> bool:
        """Expose whether VectorMemory relies on deterministic local embeddings."""

        return self._use_manual_embeddings


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
        },
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
