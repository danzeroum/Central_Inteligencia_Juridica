"""Testes de integração — dados sensíveis não chegam ao ChromaDB."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.memory.vector_memory import VectorMemory
from src.safety.pii import has_pii, redact_pii


@pytest.mark.integration
def test_pii_redaction_in_remember():
    """CPF não deve aparecer no documento indexado no ChromaDB."""
    memory = VectorMemory.__new__(VectorMemory)
    memory._use_manual_embeddings = False
    memory._hash_embedding = MagicMock()
    memory.client = MagicMock()
    memory.collection = MagicMock()
    memory._prepare_metadata_for_storage = lambda x: x

    stored = []
    memory.collection.add.side_effect = lambda documents, **kw: stored.extend(documents)

    memory.remember(
        task="Análise para CPF 111.222.333-44",
        result={},
        metadata={"tribunals": ["STF"]},
    )

    for doc in stored:
        assert "111.222.333-44" not in doc, "CPF vazou para o ChromaDB"


@pytest.mark.integration
def test_cnpj_redacted_before_indexing():
    memory = VectorMemory.__new__(VectorMemory)
    memory._use_manual_embeddings = False
    memory._hash_embedding = MagicMock()
    memory.client = MagicMock()
    memory.collection = MagicMock()
    memory._prepare_metadata_for_storage = lambda x: x

    stored = []
    memory.collection.add.side_effect = lambda documents, **kw: stored.extend(documents)

    memory.remember(
        task="Empresa CNPJ 12.345.678/0001-95 em recuperação",
        result={},
        metadata={"tribunals": []},
    )

    for doc in stored:
        assert "12.345.678/0001-95" not in doc, "CNPJ vazou para o ChromaDB"


@pytest.mark.integration
def test_redact_pii_function_available():
    text = "Email: test@example.com e CPF 000.000.000-00"
    assert has_pii(text)
    redacted = redact_pii(text)
    assert "test@example.com" not in redacted
    assert "000.000.000-00" not in redacted
