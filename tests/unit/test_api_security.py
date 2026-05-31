"""Regressão das correções de segurança P0 na camada de API (``main.py``).

Cobre os pontos que a auditoria apontou como NÃO comprovados:
* SEC-001 — autenticação JWT efetivamente exigida (sem o stub "anonymous").
* SEC-004 / CWE-209 — respostas 500 não vazam ``str(exc)`` ao cliente.
* P0-5 / CWE-20 — identificadores A2A passam por allowlist estrito.

Estes testes vivem em ``tests/unit`` de propósito: o autouse ``relax_auth`` dos
testes de integração não se aplica aqui, permitindo exercitar a enforcement real.
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
def require_auth():
    """Ativa a exigência de JWT durante o teste e restaura ao final."""

    AuthManager.configure(secret_key="x" * 40, required=True)
    yield
    AuthManager.configure(required=False)


class TestAuthEnforcement:
    """SEC-001: o endpoint protegido não pode mais aceitar acesso anônimo."""

    def test_rejects_request_without_token(self, require_auth) -> None:
        resp = client.post("/api/v1/tasks", json={"task_description": "Status TJSP"})
        assert resp.status_code == 401

    def test_rejects_invalid_token(self, require_auth) -> None:
        resp = client.post(
            "/api/v1/tasks",
            json={"task_description": "Status TJSP"},
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
        assert resp.status_code == 401

    def test_accepts_valid_token(self, require_auth) -> None:
        token = AuthManager.create_token("user-1")
        resp = client.post(
            "/api/v1/tasks",
            json={"task_description": "Status TJSP"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # O importante é que a AUTENTICAÇÃO passou (não 401); o processamento
        # a jusante pode variar conforme o ambiente.
        assert resp.status_code != 401


class TestA2AIdValidation:
    """P0-5: identificadores malformados são rejeitados com 400."""

    def test_send_rejects_malformed_sender_id(self) -> None:
        resp = client.post(
            "/api/v1/a2a/send",
            params={"sender_id": "bad id;DROP"},
            json={"receiver_id": "agent_b", "message_type": "ping", "payload": {}},
        )
        assert resp.status_code == 400

    def test_broadcast_rejects_malformed_receiver_id(self) -> None:
        resp = client.post(
            "/api/v1/a2a/broadcast",
            json={
                "sender_id": "agent_a",
                "receiver_ids": ["ok_agent", "bad receiver!"],
                "message_type": "ping",
                "payload": {},
            },
        )
        assert resp.status_code == 400

    def test_send_accepts_valid_ids(self) -> None:
        resp = client.post(
            "/api/v1/a2a/send",
            params={"sender_id": "agent_a"},
            json={"receiver_id": "agent_b", "message_type": "ping", "payload": {}},
        )
        assert resp.status_code == 200


class TestErrorDisclosure:
    """SEC-004 / CWE-209: detalhes internos não vazam na resposta 500."""

    def test_advanced_endpoint_does_not_leak_exception(self, monkeypatch) -> None:
        from src.api import main as main_module

        async def boom(_payload):
            raise RuntimeError("segredo-interno /etc/passwd host=db pass=1234")

        monkeypatch.setattr(
            main_module.unified_orchestrator, "execute_complex_task", boom
        )

        resp = client.post("/api/v1/tasks/advanced", json={"task_description": "x"})
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "segredo-interno" not in detail
        assert "/etc/passwd" not in detail
        assert "Referência para suporte" in detail
