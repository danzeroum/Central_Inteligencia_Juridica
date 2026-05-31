"""Testes da camada de RBAC e do binding de identidade (IAM-001/002/003).

Cobrem:
* Mapa de permissões por papel e a dependência ``require_permissions``.
* Papéis carregados no JWT (claim ``roles``) e papel padrão de tokens legados.
* Bypass em dev/testes (``AuthManager.REQUIRED == False``).
* A2A: ``sender_id`` amarrado à identidade autenticada (IAM-002).
* HITL: ``operator_id`` derivado do token, não do corpo (IAM-003).
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.auth import AuthManager  # noqa: E402
from src.api.main import app  # noqa: E402
from src.api.rbac import (  # noqa: E402
    DEFAULT_ROLES,
    Principal,
    Role,
    is_privileged,
    issue_token,
    permissions_for,
    roles_from_payload,
)

client = TestClient(app)


@pytest.fixture
def enforce_auth():
    """Liga a exigência de JWT (com secret de teste) e restaura ao final."""

    AuthManager.configure(secret_key="x" * 40, required=True)
    yield
    AuthManager.configure(required=False)


def _token(user_id: str, roles=None) -> str:
    return AuthManager.create_token(user_id, roles=roles)


class TestPermissionMap:
    def test_admin_has_lgpd_write(self) -> None:
        assert "lgpd:write" in permissions_for([Role.ADMIN])

    def test_operator_lacks_lgpd_write(self) -> None:
        assert "lgpd:write" not in permissions_for([Role.OPERATOR])

    def test_auditor_can_read_not_write(self) -> None:
        perms = permissions_for([Role.AUDITOR])
        assert "lgpd:read" in perms and "lgpd:write" not in perms

    def test_unknown_role_in_payload_ignored(self) -> None:
        assert roles_from_payload({"roles": ["sysadmin"]}) == list(DEFAULT_ROLES)

    def test_missing_roles_falls_back_to_default(self) -> None:
        assert roles_from_payload({"sub": "x"}) == list(DEFAULT_ROLES)

    def test_roles_parsed_from_payload(self) -> None:
        assert roles_from_payload({"roles": ["admin", "auditor"]}) == [
            Role.ADMIN,
            Role.AUDITOR,
        ]


class TestPrincipal:
    def test_anonymous_detection(self) -> None:
        assert Principal(user_id="anonymous").is_anonymous

    def test_permissions_union(self) -> None:
        p = Principal(user_id="u", roles=[Role.AUDITOR, Role.READONLY])
        assert "ledger:read" in p.permissions
        assert p.has_permission("monitoring:read")


class TestTokenRoles:
    def test_create_token_embeds_roles(self) -> None:
        AuthManager.configure(secret_key="x" * 40)
        token = AuthManager.create_token("u1", roles=["admin"])
        payload = AuthManager.verify_token_payload(_creds(token))
        assert payload["roles"] == ["admin"]
        assert payload["sub"] == "u1"

    def test_token_without_roles_has_no_claim(self) -> None:
        AuthManager.configure(secret_key="x" * 40)
        token = AuthManager.create_token("u1")
        payload = AuthManager.verify_token_payload(_creds(token))
        assert "roles" not in payload


class TestSessionTimeout:
    """BACEN 4.658: timeout de sessão reduzido, mais curto para privilegiados."""

    def _exp_minutes(self, token: str) -> float:
        payload = AuthManager.verify_token_payload(_creds(token))
        return (payload["exp"] - payload["iat"]) / 60

    def test_default_token_expiry_is_30_min(self) -> None:
        AuthManager.configure(secret_key="x" * 40, expiry_minutes=30)
        assert round(self._exp_minutes(AuthManager.create_token("u"))) == 30

    def test_explicit_minutes_override(self) -> None:
        AuthManager.configure(secret_key="x" * 40)
        token = AuthManager.create_token("u", expires_in_minutes=5)
        assert round(self._exp_minutes(token)) == 5

    def test_privileged_roles_get_shorter_session(self) -> None:
        AuthManager.configure(secret_key="x" * 40, expiry_minutes=30)
        assert round(self._exp_minutes(issue_token("a", ["admin"]))) == 15
        assert round(self._exp_minutes(issue_token("o", ["operator"]))) == 15

    def test_readonly_uses_standard_session(self) -> None:
        AuthManager.configure(secret_key="x" * 40, expiry_minutes=30)
        assert round(self._exp_minutes(issue_token("r", ["readonly"]))) == 30

    def test_is_privileged_classification(self) -> None:
        assert is_privileged([Role.ADMIN])
        assert is_privileged([Role.AUDITOR])
        assert not is_privileged([Role.READONLY])


class TestA2AIdentityBinding:
    """IAM-002: sender_id deve corresponder à identidade autenticada."""

    def test_sender_mismatch_is_forbidden(self, enforce_auth) -> None:
        token = _token("agent_a", roles=["operator"])
        resp = client.post(
            "/api/v1/a2a/send",
            params={"sender_id": "agent_b"},
            json={"receiver_id": "agent_c", "message_type": "ping", "payload": {}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_sender_match_is_allowed(self, enforce_auth) -> None:
        token = _token("agent_a", roles=["operator"])
        resp = client.post(
            "/api/v1/a2a/send",
            params={"sender_id": "agent_a"},
            json={"receiver_id": "agent_c", "message_type": "ping", "payload": {}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code != 403

    def test_admin_can_impersonate(self, enforce_auth) -> None:
        token = _token("ops-bot", roles=["admin"])
        resp = client.post(
            "/api/v1/a2a/send",
            params={"sender_id": "agent_b"},
            json={"receiver_id": "agent_c", "message_type": "ping", "payload": {}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code != 403


class TestHITLOperatorBinding:
    """IAM-003: operator_id vem do token, não do corpo da requisição."""

    def test_operator_id_comes_from_token(self, enforce_auth) -> None:
        from src.hitl.hitl_queue import get_hitl_queue
        from src.utils.ledger import get_ledger

        queue = get_hitl_queue()
        queue.clear()
        req = queue.add_request(agent="a", action={"x": 1}, context={})

        token = _token("real.operator", roles=["operator"])
        resp = client.post(
            "/api/v1/hitl/decisions",
            json={
                "request_id": req.request_id,
                "approved": True,
                "operator_id": "forjado",  # deve ser ignorado
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        stored = queue.get_request(req.request_id)
        assert stored.decided_by == "real.operator"

        # A trilha de auditoria também registra o operador autenticado.
        entries = get_ledger().get_entries(decision_type="HITL_DECISION")
        assert any(
            e["metadata"].get("operator_id") == "real.operator"
            and e["metadata"].get("request_id") == req.request_id
            for e in entries
        )
        queue.clear()


# --- helpers -----------------------------------------------------------------
def _creds(token: str):
    from fastapi.security import HTTPAuthorizationCredentials

    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
