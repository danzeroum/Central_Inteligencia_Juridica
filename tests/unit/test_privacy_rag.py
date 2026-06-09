"""Testes — PII é detectado e redigido ANTES da ingestão no ChromaDB."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.memory.vector_memory import VectorMemory
from src.safety.pii import redact_pii


def test_redact_pii_cpf():
    text = "O CPF do cliente é 123.456.789-09 e precisa de ajuda."
    redacted = redact_pii(text)
    assert "123.456.789-09" not in redacted


def test_redact_pii_cnpj():
    text = "CNPJ 12.345.678/0001-95 da empresa."
    redacted = redact_pii(text)
    assert "12.345.678/0001-95" not in redacted


def test_redact_pii_email():
    text = "Contato: advogado@escritorio.com.br"
    redacted = redact_pii(text)
    assert "advogado@escritorio.com.br" not in redacted


def test_pii_redacted_before_remember():
    """Verificar que VectorMemory.remember() redige PII antes de indexar."""
    memory = VectorMemory.__new__(VectorMemory)
    memory._use_manual_embeddings = False
    memory._hash_embedding = MagicMock()
    memory.client = MagicMock()
    memory.collection = MagicMock()
    memory._prepare_metadata_for_storage = lambda x: x

    cpf_task = "Consulta para CPF 123.456.789-09"
    stored_documents = []

    def capture_add(documents, metadatas, ids, **kwargs):
        stored_documents.extend(documents)

    memory.collection.add.side_effect = capture_add

    import os

    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
        memory.remember(
            task=cpf_task,
            result={"status": "ok"},
            metadata={"tribunals": ["TJSP"]},
        )

    # O documento armazenado NÃO deve conter o CPF em texto limpo
    for doc in stored_documents:
        assert "123.456.789-09" not in doc


def test_pii_not_leaked_in_metadata_original_task():
    """metadata['original_task'] deve ser a versão REDIGIDA do CPF."""
    memory = VectorMemory.__new__(VectorMemory)
    memory._use_manual_embeddings = False
    memory._hash_embedding = MagicMock()
    memory.client = MagicMock()
    memory.collection = MagicMock()

    stored_metadatas = []

    def capture_add(documents, metadatas, ids, **kwargs):
        stored_metadatas.extend(metadatas)

    memory.collection.add.side_effect = capture_add

    cpf_task = "Consulta para CPF 987.654.321-00"
    memory.remember(
        task=cpf_task,
        result={},
        metadata={"tribunals": []},
    )

    for meta in stored_metadatas:
        original = meta.get("original_task", "")
        assert "987.654.321-00" not in original
