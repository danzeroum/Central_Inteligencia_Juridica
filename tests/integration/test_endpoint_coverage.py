"""Cobertura dos endpoints HTTP ainda não exercitados (Frente C).

Mocka os colaboradores pesados (supervisor, orquestrador, clientes externos)
para cobrir caminhos felizes e de erro de ``src/api/main.py`` de forma
determinística e rápida.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

from unittest.mock import AsyncMock  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402
from src.api.state import (
    a2a_channel,
    supervisor_agent,
    unified_orchestrator,
)  # noqa: E402

client = TestClient(app)


# ── A2A broadcast (caminho de sucesso) ───────────────────────────────────────
def test_broadcast_success(monkeypatch):
    monkeypatch.setattr(a2a_channel, "send_message", AsyncMock(return_value="msg_1"))
    resp = client.post(
        "/api/v1/a2a/broadcast",
        json={
            "sender_id": "agent_a",
            "receiver_ids": ["agent_b", "agent_c"],
            "message_type": "ping",
            "payload": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "broadcasted"
    assert body["total_sent"] == 2
    assert body["receivers"] == ["agent_b", "agent_c"]


# ── Invocação direta de agente (MCP) ─────────────────────────────────────────
def test_invoke_supervisor_agent(monkeypatch):
    monkeypatch.setattr(
        supervisor_agent,
        "process_task",
        AsyncMock(return_value={"status": "success", "n": 1}),
    )
    resp = client.post(
        "/api/v1/agents/supervisor_agent/invoke",
        json={"task_description": "consulta"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_invoked"] == "supervisor_agent"
    assert body["result"]["status"] == "success"


def test_invoke_tribunal_by_suffix(monkeypatch):
    # agent_id que termina em _agent e não está no registry → ramo de delegação.
    monkeypatch.setattr(
        supervisor_agent,
        "identify_all_tribunals",
        lambda code: ["TJSP"],
    )
    monkeypatch.setattr(
        supervisor_agent,
        "delegate_to_tribunal_agent",
        AsyncMock(return_value={"status": "success"}),
    )
    resp = client.post(
        "/api/v1/agents/tjsp_agent/invoke",
        json={"task_description": "consulta"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_invoked"] == "tjsp_agent"


def test_invoke_unknown_agent_is_404():
    resp = client.post(
        "/api/v1/agents/inexistente/invoke",
        json={"task_description": "consulta"},
    )
    assert resp.status_code == 404


# ── /tasks (deprecated) e /api/v1/tasks/advanced ─────────────────────────────
_VALID_TASK_RESULT = {
    "status": "success",
    "supervisor_result": {"ok": True},
    "tribunals_used": ["TJSP"],
    "task_id": "task_0001",
    "execution_time": 0.1,
    "parallel": False,
    "timestamp": "2026-06-04T12:00:00+00:00",
}


def test_deprecated_tasks_endpoint_success(monkeypatch):
    monkeypatch.setattr(
        supervisor_agent,
        "process_task",
        AsyncMock(return_value=_VALID_TASK_RESULT),
    )
    resp = client.post("/tasks", json={"task_description": "consulta"})
    assert resp.status_code == 200
    assert resp.json()["task_id"] == "task_0001"


def test_advanced_task_success(monkeypatch):
    monkeypatch.setattr(
        unified_orchestrator,
        "execute_complex_task",
        AsyncMock(return_value={"success": True}),
    )
    resp = client.post(
        "/api/v1/tasks/advanced", json={"task_description": "tarefa complexa"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_mode"] == "advanced"
    assert body["api_version"] == "1.1.0"


# ── Proposições legislativas (legado + canônico) ─────────────────────────────
def test_consultar_projetos_empty_q_is_400():
    resp = client.get("/consultar-projetos-lei/", params={"q": "   "})
    assert resp.status_code == 400


def test_consultar_projetos_success(monkeypatch):
    import src.api.routes.legislative as leg_mod

    monkeypatch.setattr(
        leg_mod, "buscar_projetos_de_lei", lambda termo, **_: {"data": ["proj"]}
    )
    resp = client.get("/consultar-projetos-lei/", params={"q": "reforma"})
    assert resp.status_code == 200
    assert resp.json() == {"data": ["proj"]}


def test_consultar_projetos_upstream_error_is_502(monkeypatch):
    import src.api.routes.legislative as leg_mod

    monkeypatch.setattr(
        leg_mod,
        "buscar_projetos_de_lei",
        lambda termo, **_: {"error": "indisponível"},
    )
    resp = client.get("/consultar-projetos-lei/", params={"q": "reforma"})
    assert resp.status_code == 502


def test_canonical_proposicoes_success(monkeypatch):
    import src.api.routes.legislative as leg_mod

    monkeypatch.setattr(
        leg_mod, "buscar_projetos_de_lei", lambda termo, **_: {"data": []}
    )
    resp = client.get("/api/v1/proposicoes-legislativas", params={"q": "reforma"})
    assert resp.status_code == 200


# ── Análise legislativa (legado + canônico) ──────────────────────────────────
def test_analise_legislativa_empty_is_400():
    resp = client.post("/analise-legislativa/", json={"tema": "   "})
    assert resp.status_code == 400


def test_analise_legislativa_success(monkeypatch):
    import src.api.routes.legislative as leg_mod

    monkeypatch.setattr(
        leg_mod, "analisar_cenario_legislativo", lambda tema: {"resumo": "ok"}
    )
    resp = client.post("/analise-legislativa/", json={"tema": "reforma tributária"})
    assert resp.status_code == 200
    assert resp.json()["analise_ia"] == {"resumo": "ok"}


def test_canonical_analises_success(monkeypatch):
    import src.api.routes.legislative as leg_mod

    monkeypatch.setattr(
        leg_mod, "analisar_cenario_legislativo", lambda tema: {"resumo": "ok"}
    )
    resp = client.post(
        "/api/v1/analises-legislativas", json={"tema": "reforma tributária"}
    )
    assert resp.status_code == 201
    assert resp.json()["tema_analisado"] == "reforma tributária"


# ── /health verbose ──────────────────────────────────────────────────────────
def test_health_verbose(monkeypatch):
    monkeypatch.setattr(
        a2a_channel,
        "health_check",
        AsyncMock(return_value={"status": "ok"}),
    )
    resp = client.get("/health", params={"verbose": True})
    assert resp.status_code == 200
    body = resp.json()
    assert "details" in body
    assert "agents" in body["details"]
