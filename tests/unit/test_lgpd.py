"""Testes dos endpoints de direitos do titular (LGPD-001).

Cobrem acesso, portabilidade e exclusão/anonimização, além da autorização RBAC
(leitura exige ``lgpd:read``; exclusão exige ``lgpd:write``).
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.auth import AuthManager  # noqa: E402
from src.api.main import app  # noqa: E402
from src.utils import ledger as ledger_module  # noqa: E402

client = TestClient(app)

SUBJECT = "titular-teste-001"


@pytest.fixture
def temp_ledger(monkeypatch):
    """Aponta o ledger global para um arquivo temporário, semeado com 2 entradas."""

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", prefix="lgpd_")
    tmp.close()
    led = ledger_module.DecisionLedger(log_file=tmp.name)
    monkeypatch.setattr(ledger_module, "_ledger", led)

    led.log_decision("Agent", "QUERY", {"subject_id": SUBJECT, "cpf": "12345678901"})
    led.log_decision("Agent", "QUERY", {"subject_id": SUBJECT, "nome": "Fulano"})
    led.log_decision("Agent", "QUERY", {"subject_id": "outro-titular"})
    yield led
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def enforce_auth():
    AuthManager.configure(secret_key="x" * 40, required=True)
    yield
    AuthManager.configure(required=False)


def _token(user_id: str, roles) -> str:
    return AuthManager.create_token(user_id, roles=roles)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestAccessAndPortability:
    def test_access_returns_subject_records(self, temp_ledger, enforce_auth) -> None:
        resp = client.get(
            f"/api/v1/lgpd/data/{SUBJECT}",
            headers=_auth(_token("dpo", roles=["auditor"])),
        )
        assert resp.status_code == 200
        assert resp.json()["record_count"] == 2

    def test_export_is_portable_json(self, temp_ledger, enforce_auth) -> None:
        resp = client.get(
            f"/api/v1/lgpd/data/{SUBJECT}/export",
            headers=_auth(_token("dpo", roles=["admin"])),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["format"] == "json"
        assert body["record_count"] == 2


class TestAuthorization:
    def test_read_requires_permission(self, temp_ledger, enforce_auth) -> None:
        # readonly não possui lgpd:read.
        resp = client.get(
            f"/api/v1/lgpd/data/{SUBJECT}",
            headers=_auth(_token("u", roles=["readonly"])),
        )
        assert resp.status_code == 403

    def test_delete_requires_write_permission(self, temp_ledger, enforce_auth) -> None:
        # auditor pode ler, mas não excluir.
        resp = client.request(
            "DELETE",
            f"/api/v1/lgpd/data/{SUBJECT}",
            params={"justification": "pedido do titular"},
            headers=_auth(_token("u", roles=["auditor"])),
        )
        assert resp.status_code == 403


class TestErasure:
    def test_delete_anonymizes_and_audits(self, temp_ledger, enforce_auth) -> None:
        resp = client.request(
            "DELETE",
            f"/api/v1/lgpd/data/{SUBJECT}",
            params={"justification": "direito de exclusão (Art. 18, VI)"},
            headers=_auth(_token("dpo", roles=["admin"])),
        )
        assert resp.status_code == 200
        assert resp.json()["ledger_entries_anonymized"] == 2

        # Após a exclusão, os registros de dados (QUERY) do titular foram
        # anonimizados — não restam dados pessoais referenciando-o...
        access = client.get(
            f"/api/v1/lgpd/data/{SUBJECT}",
            headers=_auth(_token("dpo", roles=["admin"])),
        )
        remaining = access.json()["records"]
        assert all(r["decision_type"] != "QUERY" for r in remaining)

        # ...mas a operação de exclusão fica registrada (accountability).
        deletions = temp_ledger.get_entries(decision_type="LGPD_DELETION")
        assert any(e["metadata"]["subject_id"] == SUBJECT for e in deletions)

    def test_delete_requires_justification(self, temp_ledger, enforce_auth) -> None:
        resp = client.request(
            "DELETE",
            f"/api/v1/lgpd/data/{SUBJECT}",
            headers=_auth(_token("dpo", roles=["admin"])),
        )
        assert resp.status_code == 422  # justification ausente
