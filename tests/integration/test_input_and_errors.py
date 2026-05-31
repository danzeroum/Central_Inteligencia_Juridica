"""Validação de entrada, anti-DoS, vazamento de erro, CORS e rate limit (Onda 3).

Cobre (V&V): H07/M07 (limite de task_description), M05/M10 (payload/receivers
A2A), M09 (subject_id LGPD), H08/H17 + handler global (sem vazar exceções),
H15/M01 (CORS explícito), H14 (rate limit em rotas adicionais), H09 (sanitização
de texto na borda).
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api import main as main_module  # noqa: E402
from src.api.main import app  # noqa: E402

client = TestClient(app)
# Cliente que NÃO re-levanta exceções do servidor: necessário para observar a
# resposta 500 produzida pelo handler global de exceções.
client_500 = TestClient(app, raise_server_exceptions=False)


# --- H07/M07: limite de tamanho de task_description -------------------------
def test_task_description_too_long_is_422():
    resp = client.post("/tasks", json={"task_description": "a" * 6000})
    assert resp.status_code == 422


def test_task_description_empty_is_422():
    resp = client.post("/tasks", json={"task_description": ""})
    assert resp.status_code == 422


# --- H09: sanitização de texto na borda -------------------------------------
def test_task_description_is_sanitized():
    from src.api.main import TaskRequest

    model = TaskRequest(task_description="<script>alert(1)</script> consulta TJSP")
    assert "<script>" not in model.task_description


# --- M05/M10: limites de payload e destinatários A2A ------------------------
def test_a2a_broadcast_too_many_receivers_is_422():
    resp = client.post(
        "/api/v1/a2a/broadcast",
        json={
            "sender_id": "agent_a",
            "receiver_ids": [f"agent_{i}" for i in range(200)],
            "message_type": "ping",
            "payload": {},
        },
    )
    assert resp.status_code == 422


def test_a2a_payload_too_large_is_422():
    resp = client.post(
        "/api/v1/a2a/send",
        params={"sender_id": "agent_a"},
        json={
            "receiver_id": "agent_b",
            "message_type": "ping",
            "payload": {"blob": "x" * (70 * 1024)},
        },
    )
    assert resp.status_code == 422


# --- M09: formato de subject_id (LGPD) --------------------------------------
def test_lgpd_invalid_subject_id_is_400():
    # Caractere inválido que ainda roteia até o handler (não quebra o path).
    resp = client.get("/api/v1/lgpd/data/bad!id")
    assert resp.status_code == 400


# --- H08: monitoring não vaza str(exc) --------------------------------------
def test_monitoring_health_does_not_leak_exception(monkeypatch):
    from src.api import monitoring_endpoints as mon

    async def _boom():
        raise RuntimeError("segredo-interno-12345")

    channel = mon.get_a2a_channel()
    monkeypatch.setattr(channel, "health_check", _boom)
    resp = client.get("/api/v1/monitoring/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["a2a"]["status"] == "unknown"
    assert "segredo-interno-12345" not in resp.text


# --- H17 + handler global: 500 opaco ----------------------------------------
def test_global_handler_returns_opaque_500(monkeypatch):
    async def _boom(*_a, **_k):
        raise RuntimeError("stacktrace-secreto-98765")

    monkeypatch.setattr(main_module.supervisor_agent, "process_task", _boom)
    resp = client_500.post("/tasks", json={"task_description": "consulta"})
    assert resp.status_code == 500
    assert "stacktrace-secreto-98765" not in resp.text
    assert "Referência" in resp.text  # referência opaca para suporte


# --- H15/M01: CORS explícito (sem '*') --------------------------------------
def test_cors_methods_are_explicit_not_wildcard():
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    allow_methods = resp.headers.get("access-control-allow-methods", "")
    assert "*" not in allow_methods
    assert "POST" in allow_methods


# --- H14: rate limiting aplicado a rotas adicionais (main + routers) ---------
def test_rate_limit_applies_to_a2a_send(monkeypatch):
    """Com o limite reduzido a 1/min, a 2ª chamada deve receber 429."""

    from src.api import rate_limit
    from src.api.rate_limiter import RateLimiter

    monkeypatch.setattr(rate_limit, "limiter", RateLimiter(requests_per_minute=1))
    body = {"receiver_id": "agent_b", "message_type": "ping", "payload": {}}
    first = client.post("/api/v1/a2a/send", params={"sender_id": "agent_a"}, json=body)
    second = client.post("/api/v1/a2a/send", params={"sender_id": "agent_a"}, json=body)
    assert first.status_code != 429
    assert second.status_code == 429


def test_rate_limit_applies_to_ledger_router(monkeypatch):
    """H14: routers (ledger) agora também têm rate limit via módulo compartilhado."""

    from src.api import rate_limit
    from src.api.rate_limiter import RateLimiter

    monkeypatch.setattr(rate_limit, "limiter", RateLimiter(requests_per_minute=1))
    first = client.get("/api/v1/ledger")
    second = client.get("/api/v1/ledger")
    assert first.status_code != 429
    assert second.status_code == 429
