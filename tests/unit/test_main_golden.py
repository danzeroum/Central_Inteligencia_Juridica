"""Golden tests — snapshot das rotas de main.py (rede de proteção do S-0.2).

Devem passar NA ONDA 1 (baseline, main.py com 1280 LOC) e permanecer verdes
após a extração para routes/ + app_factory.py.

DoD S-0.2: OpenAPI idêntico antes/depois · main.py ≲ 150 linhas · 0 regressão.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from src.api.main import app

    with TestClient(app) as c:
        yield c


# Rotas definidas diretamente no main.py (em risco durante a extração).
# Todas devem existir no OpenAPI antes E depois do refactor.
_CORE_PATHS = frozenset(
    {
        "/health",
        # /metrics tem include_in_schema=False — não aparece no OpenAPI
        "/tasks",
        "/api/v1/tasks",
        "/api/v1/tasks/advanced",
        "/api/v1/tasks/compare",
        "/api/v1/agents/capabilities",
        "/api/v1/agents",
        "/api/v1/agents/by-capability/{capability}",
        "/api/v1/agents/{agent_id}",
        "/api/v1/agents/{agent_id}/trust",
        "/api/v1/agents/{agent_id}/invoke",
        "/api/v1/a2a/send",
        "/api/v1/a2a/messages/{agent_id}",
        "/api/v1/a2a/history/{agent_id}",
        "/api/v1/a2a/broadcast",
        "/api/v1/a2a/health",
        "/consultar-projetos-lei/",
        "/api/v1/proposicoes-legislativas",
        "/analise-legislativa/",
        "/api/v1/analises-legislativas",
        "/api/v1/history",
    }
)

# Prefixos reais dos routers incluídos (validado no OpenAPI gerado pela Onda 1)
_ROUTER_PATH_PREFIXES = (
    "/auth",  # auth_router → /auth/login
    "/api/v1/hitl",
    "/api/v1/ledger",
    "/api/v1/monitoring",
    "/api/v1/intelligence",
    "/api/v1/jurisprudencia",
)


def test_openapi_all_core_paths_present(client):
    """Snapshot: todas as rotas canônicas do main.py original devem existir."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = set(resp.json()["paths"].keys())
    missing = _CORE_PATHS - paths
    assert not missing, f"Rotas ausentes do OpenAPI após refatoração: {sorted(missing)}"


def test_openapi_app_title_unchanged(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Central Inteligência Jurídica"


def test_openapi_core_http_methods(client):
    """Verifica que cada rota crítica mantém o verbo HTTP correto."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]

    assert "get" in paths.get("/health", {}), "/health GET ausente"
    assert "get" in paths.get("/api/v1/agents", {}), "/api/v1/agents GET ausente"
    assert "post" in paths.get("/api/v1/tasks", {}), "/api/v1/tasks POST ausente"
    assert "post" in paths.get("/api/v1/tasks/advanced", {}), "tasks/advanced ausente"
    assert "post" in paths.get("/api/v1/a2a/send", {}), "a2a/send ausente"
    assert "get" in paths.get("/api/v1/a2a/health", {}), "a2a/health ausente"
    assert "get" in paths.get("/api/v1/history", {}), "history ausente"
    assert "patch" in paths.get(
        "/api/v1/agents/{agent_id}/trust", {}
    ), "agents trust PATCH ausente"


def test_openapi_router_paths_present(client):
    """Ao menos um path de cada router incluído deve aparecer no schema."""
    resp = client.get("/openapi.json")
    paths = set(resp.json()["paths"].keys())
    for prefix in _ROUTER_PATH_PREFIXES:
        has_prefix = any(p.startswith(prefix) for p in paths)
        assert has_prefix, f"Nenhuma rota com prefixo '{prefix}' no OpenAPI"


def test_health_simple(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


def test_health_verbose_structure(client):
    """Estrutura do /health?verbose=true inclui database (adicionado no S-0.1)."""
    resp = client.get("/health?verbose=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    details = body["details"]
    assert "agents" in details
    assert "metrics" in details
    assert "a2a" in details
    assert "database" in details
    assert details["database"]["status"] == "not_configured"


def test_health_verbose_agents_structure(client):
    resp = client.get("/health?verbose=true")
    agents = resp.json()["details"]["agents"]
    assert "supervisor_active" in agents
    assert agents["supervisor_active"] is True
    assert "active_delegates" in agents


def test_tasks_route_requires_body(client):
    """POST /api/v1/tasks sem body retorna 422 (validação Pydantic ativa)."""
    resp = client.post("/api/v1/tasks", json={})
    assert resp.status_code == 422


def test_a2a_send_requires_body(client):
    resp = client.post("/api/v1/a2a/send", json={})
    assert resp.status_code == 422


def test_main_py_line_count():
    """DoD S-0.2: main.py deve ter ≲ 150 linhas após a extração.

    Este teste FALHA intencionalmente no estado pré-refactor (1280 LOC) e
    passa quando a extração está completa. É parte da DoD verificável.
    """
    with open("src/api/main.py", encoding="utf-8") as fh:
        lines = fh.readlines()
    assert len(lines) <= 150, (
        f"src/api/main.py tem {len(lines)} linhas — excede o limite de 150. "
        "Continue a extração para routes/ e app_factory.py."
    )
