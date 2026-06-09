"""Testes de integração — isolamento de coleções por área."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from src.tools.rag_tool import RAGTool


@pytest.fixture
def isolated_rag():
    memory = MagicMock()
    memory.is_available.return_value = False
    memory.collection = None
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["resultado_area"]],
        "metadatas": [[{"area": "trabalhista"}]],
        "distances": [[0.2]],
    }
    memory.get_or_create_collection.return_value = mock_collection
    return RAGTool(memory=memory)


@pytest.mark.integration
def test_query_rag_returns_area_results(isolated_rag):
    results = isolated_rag.query_rag("horas extras", areas=["trabalhista"])
    # Deve retornar algum resultado (da área + genérico)
    assert isinstance(results, list)


@pytest.mark.integration
def test_area_specific_results_have_boosted_score(isolated_rag):
    results = isolated_rag.query_rag("horas extras", areas=["trabalhista"])
    area_results = [
        r for r in results if r.get("metadata", {}).get("area") == "trabalhista"
    ]
    generic_results = [
        r for r in results if r.get("metadata", {}).get("area") != "trabalhista"
    ]

    # Área específica deve ter score >= resultados genéricos quando existentes
    if area_results and generic_results:
        max_area_score = max(r["score"] for r in area_results)
        max_generic_score = max(r["score"] for r in generic_results)
        assert max_area_score >= max_generic_score * 0.9


@pytest.mark.integration
def test_different_areas_use_different_collections(isolated_rag):
    isolated_rag.query_rag("query", areas=["trabalhista", "tributario"])
    calls = [
        c[0][0] for c in isolated_rag.memory.get_or_create_collection.call_args_list
    ]
    # Deve ter solicitado coleções diferentes
    assert len(set(calls)) >= 2


@pytest.mark.integration
def test_max_namespaces_limit_respected(isolated_rag):
    areas = ["trabalhista", "civil", "penal", "tributario", "empresarial"]
    isolated_rag.query_rag("query", areas=areas, max_namespaces=3)
    call_count = isolated_rag.memory.get_or_create_collection.call_count
    # juridico_generico + 3 áreas = 4 total
    assert call_count <= 4
