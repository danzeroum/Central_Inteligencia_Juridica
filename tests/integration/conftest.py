"""Configuração compartilhada dos testes de integração.

Isola o armazenamento de memória vetorial (ChromaDB) por sessão de teste. Sem
isto, todos os testes que instanciam ``SupervisorAgent``/``VectorMemory`` usam o
diretório padrão ``.vector_memory/`` no repositório, compartilhando estado entre
arquivos de teste. Isso causa "cache hits" cruzados não determinísticos (ainda
mais com hash embeddings, cujo limiar de similaridade é baixo) e falhas
dependentes de ordem de execução — exatamente o tipo de flakiness que só aparece
no CI (onde o chromadb está instalado).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def relax_auth():
    """Garante acesso anônimo determinístico nos testes de integração.

    Os testes de integração exercitam os endpoints sem emitir JWT. Como a
    configuração de autenticação do ``AuthManager`` é estado de classe global,
    outro teste (ex.: ``test_security_hardening``) pode tê-la deixado em
    ``required=True`` num run combinado (``pytest`` na raiz). Forçar
    ``required=False`` por teste remove essa contaminação cruzada. A enforcement
    real de autenticação é coberta pelos testes unitários dedicados.
    """

    from src.api.auth import AuthManager

    AuthManager.configure(required=False)
    yield


@pytest.fixture(autouse=True)
def isolate_vector_memory(monkeypatch, tmp_path_factory):
    """Aponta o VectorMemory para um diretório temporário exclusivo por teste."""

    persist_dir = tmp_path_factory.mktemp("vector_memory")
    monkeypatch.setenv("VECTOR_MEMORY_MODE", "local")
    monkeypatch.setenv("VECTOR_MEMORY_PERSIST_PATH", str(persist_dir))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield
