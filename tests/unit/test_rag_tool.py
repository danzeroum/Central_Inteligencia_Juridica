"""Testes unitários — RAGTool namespace e filtros."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.tools.rag_tool import RAGTool


def _make_rag_with_mock_memory():
    memory = MagicMock()
    memory.is_available.return_value = False
    memory.collection = None
    rag = RAGTool(memory=memory)
    return rag, memory


def test_rag_tool_unavailable_returns_empty():
    rag, _ = _make_rag_with_mock_memory()
    assert rag.query("query") == []
    assert rag.query_rag("query") == []


def test_add_documents_to_namespace_unavailable():
    rag, memory = _make_rag_with_mock_memory()
    memory.get_or_create_collection.return_value = None
    # Não deve levantar exceção
    rag.add_documents_to_namespace("trabalhista", [{"text": "doc", "id": "d1"}])


def test_query_with_filter_unavailable():
    rag, memory = _make_rag_with_mock_memory()
    memory.get_or_create_collection.return_value = None
    result = rag.query_with_filter("query", "trabalhista")
    assert result == []


def test_query_rag_empty_query():
    rag, _ = _make_rag_with_mock_memory()
    result = rag.query_rag("")
    assert result == []


def test_query_rag_max_namespaces_respected():
    rag, memory = _make_rag_with_mock_memory()
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["doc1"]],
        "metadatas": [[{}]],
        "distances": [[0.3]],
    }
    memory.get_or_create_collection.return_value = mock_collection

    areas = ["trabalhista", "civil", "penal", "tributario", "empresarial"]
    rag.query_rag("query", areas=areas, max_namespaces=4)

    # juridico_generico + 4 áreas = 5 chamadas total
    assert memory.get_or_create_collection.call_count <= 5


def test_add_documents_skips_empty_text():
    rag, memory = _make_rag_with_mock_memory()
    mock_collection = MagicMock()
    memory.get_or_create_collection.return_value = mock_collection

    rag.add_documents_to_namespace(
        "area", [{"text": "", "id": "d1"}, {"content": None}]
    )
    mock_collection.add.assert_not_called()


def test_query_with_filter_score_filtering():
    rag, memory = _make_rag_with_mock_memory()
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["doc_relevant", "doc_irrelevant"]],
        "metadatas": [[{}, {}]],
        "distances": [[0.2, 1.8]],  # scores: 0.9 e 0.1
    }
    memory.get_or_create_collection.return_value = mock_collection

    results = rag.query_with_filter("query", "trabalhista", min_score=0.5)
    assert len(results) == 1
    assert results[0]["text"] == "doc_relevant"
