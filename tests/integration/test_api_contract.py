"""Testes de contrato da API — garantem que as correções de API Design (Frente A,
API-01…07) não regridem.

Cada teste mapeia para um item do diagnóstico consolidado em
``docs/PLANO_MESTRE_MELHORIAS.md``. A abordagem das correções é *aditiva*: as
rotas legadas (exceções conscientes do ADR-003/D12) permanecem, porém marcadas
``deprecated``, e as formas canônicas passam a existir ao lado delas.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.auth import AuthManager  # noqa: E402
from src.api.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture
def enforce_auth():
    """Liga a exigência de JWT (com secret de teste) e restaura ao final."""

    AuthManager.configure(secret_key="x" * 40, required=True)
    yield
    AuthManager.configure(required=False)


def _token(user_id: str, roles=None) -> str:
    return AuthManager.create_token(user_id, roles=roles)


# Endpoints GET que passaram a declarar ``response_model`` (API-05). Excluem
# rotas propositadamente dinâmicas (``/health``, ``/api/v1/agents/capabilities``).
_MODELED_GET_PATHS = [
    "/api/v1/agents",
    "/api/v1/a2a/messages/{agent_id}",
    "/api/v1/a2a/history/{agent_id}",
    "/api/v1/agents/by-capability/{capability}",
    "/api/v1/history",
]


# ── API-01: versionamento — rota canônica existe, legada fica deprecated ──────
def test_api01_canonical_tasks_route_exists():
    schema = app.openapi()
    assert "/api/v1/tasks" in schema["paths"]


def test_api01_legacy_tasks_route_is_deprecated():
    schema = app.openapi()
    # Mantida (exceção ADR-003/D12), mas sinalizada como deprecated no contrato.
    assert "/tasks" in schema["paths"]
    assert schema["paths"]["/tasks"]["post"].get("deprecated") is True


# ── API-02: substantivos plurais sem verbo; legados deprecated ───────────────
def test_api02_canonical_legislative_routes_exist():
    schema = app.openapi()
    assert "/api/v1/proposicoes-legislativas" in schema["paths"]
    assert "/api/v1/analises-legislativas" in schema["paths"]


def test_api02_legacy_verb_routes_are_deprecated():
    schema = app.openapi()
    assert schema["paths"]["/consultar-projetos-lei/"]["get"].get("deprecated") is True
    assert schema["paths"]["/analise-legislativa/"]["post"].get("deprecated") is True


# ── API-03: sender_id no corpo (canônico); query param deprecated ────────────
def test_api03_send_accepts_sender_in_body():
    resp = client.post(
        "/api/v1/a2a/send",
        json={
            "sender_id": "agent_a",
            "receiver_id": "agent_b",
            "message_type": "ping",
            "payload": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sender"] == "agent_a"
    assert body["receiver"] == "agent_b"


def test_api03_send_without_any_sender_is_400():
    resp = client.post(
        "/api/v1/a2a/send",
        json={"receiver_id": "agent_b", "message_type": "ping", "payload": {}},
    )
    assert resp.status_code == 400


def test_api03_query_param_sender_still_works_deprecated():
    # Retrocompatibilidade: o query param continua aceito (marcado deprecated).
    resp = client.post(
        "/api/v1/a2a/send",
        params={"sender_id": "agent_a"},
        json={"receiver_id": "agent_b", "message_type": "ping", "payload": {}},
    )
    assert resp.status_code == 200


def test_api03_send_query_param_marked_deprecated_in_schema():
    schema = app.openapi()
    params = schema["paths"]["/api/v1/a2a/send"]["post"].get("parameters", [])
    sender_param = next((p for p in params if p["name"] == "sender_id"), None)
    assert sender_param is not None
    assert sender_param.get("deprecated") is True


# ── API-04: filtragem por capability via query param (forma canônica) ────────
def test_api04_agents_filter_by_capability_query():
    resp = client.get("/api/v1/agents", params={"capability": "task_routing"})
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body and "agents" in body
    assert body["total"] == len(body["agents"])


def test_api04_legacy_by_capability_path_still_present():
    schema = app.openapi()
    assert "/api/v1/agents/by-capability/{capability}" in schema["paths"]


# ── API-05: GETs modelados expõem schema de resposta (não Dict opaco) ────────
@pytest.mark.parametrize("path", _MODELED_GET_PATHS)
def test_api05_get_endpoints_have_response_schema(path):
    schema = app.openapi()
    content = schema["paths"][path]["get"]["responses"]["200"]["content"]
    json_schema = content["application/json"]["schema"]
    # Um response_model declarado gera referência a um componente nomeado.
    assert (
        "$ref" in json_schema or json_schema.get("type") == "array"
    ), f"GET {path} não declara response_model (schema opaco): {json_schema}"


# ── API-06: /tasks/compare exige a permissão tasks:compare (admin) ───────────
def test_api06_compare_forbidden_for_operator(enforce_auth):
    token = _token("user-op", roles=["operator"])
    resp = client.post(
        "/api/v1/tasks/compare",
        json={"task_description": "comparar modos"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_api06_compare_allowed_for_admin(enforce_auth):
    token = _token("user-admin", roles=["admin"])
    resp = client.post(
        "/api/v1/tasks/compare",
        json={"task_description": "comparar modos"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # A autorização passou: não pode ser 403 (o resultado a jusante pode variar).
    assert resp.status_code != 403


# ── API-07: histórico expõe contrato de paginação (total + cursor) ───────────
def test_api07_history_exposes_pagination_contract():
    resp = client.get("/api/v1/history", params={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert "count" in body
    assert "total" in body
    assert "cursor" in body
    assert "history" in body
