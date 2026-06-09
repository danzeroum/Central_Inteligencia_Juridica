"""KnowledgeManager — ingestão e atualização incremental da base de conhecimento."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from src.memory.chunker import LegalDocumentChunker
from src.memory.vector_memory import VectorMemory
from src.tools.rag_tool import RAGTool

logger = logging.getLogger(__name__)


class KnowledgeManager:
    """Gerencia a base de conhecimento jurídico por área/namespace."""

    def __init__(self, memory: Optional[VectorMemory] = None) -> None:
        self._memory = memory or VectorMemory()
        self._rag = RAGTool(memory=self._memory)
        self._chunker = LegalDocumentChunker()

    def _select_chunking(
        self, tipo_documento: str, content: str
    ) -> List[Dict[str, Any]]:
        """Seleciona estratégia de chunking por tipo de documento."""
        tipo = tipo_documento.lower()
        if tipo in {"lei", "decreto", "medida_provisoria", "emenda_constitucional"}:
            return self._chunker.chunk_by_article(content)
        if tipo in {"codigo", "consolidacao", "regulamento"}:
            return self._chunker.chunk_by_section(content)
        # acordao, parecer, doutrina, generico
        return self._chunker.chunk_by_semantic(content)

    def ingest_document(
        self,
        area_key: str,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Chunking + indexação de documento jurídico.

        Metadados obrigatórios: area, doc_id, chunk_index, tipo_documento.
        Opcionais: tribunal, data_vigencia, ementa.
        """
        if not content or not content.strip():
            logger.warning("Documento vazio ignorado: %s/%s", area_key, doc_id)
            return

        base_meta = metadata or {}
        tipo = base_meta.get("tipo_documento", "generico")
        chunks = self._select_chunking(tipo, content)

        documents = []
        for idx, chunk in enumerate(chunks):
            chunk_meta: Dict[str, Any] = {
                "area": area_key,
                "doc_id": doc_id,
                "chunk_index": idx,
                "tipo_documento": tipo,
                **base_meta,
                **chunk.get("metadata", {}),
            }
            documents.append(
                {
                    "id": f"{doc_id}_chunk_{idx}",
                    "text": chunk["text"],
                    "metadata": chunk_meta,
                }
            )

        self._rag.add_documents_to_namespace(area_key, documents)
        logger.info(
            "Documento '%s' ingerido na área '%s': %d chunks.",
            doc_id,
            area_key,
            len(documents),
        )

    def incremental_update(
        self,
        area_key: str,
        doc_id: str,
        new_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Atualiza documento por exclusão dos chunks anteriores + reingestão."""
        collection = self._memory.get_or_create_collection(area_key)
        if collection is not None:
            try:
                collection.delete(where={"doc_id": doc_id})
                logger.info(
                    "Chunks anteriores de '%s' excluídos para atualização.", doc_id
                )
            except Exception as exc:
                logger.warning(
                    "Falha ao excluir chunks de '%s': %s. Prosseguindo.", doc_id, exc
                )

        self.ingest_document(area_key, doc_id, new_content, metadata)


__all__ = ["KnowledgeManager"]
