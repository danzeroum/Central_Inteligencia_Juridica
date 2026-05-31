"""Endpoint /auth/login (CRÍTICO-09: base para o login real da SPA).

V&V: credenciais válidas emitem JWT utilizável; inválidas => 401; o token
emitido de fato autoriza um endpoint protegido por RBAC.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.auth import AuthManager  # noqa: E402
from src.api.main import app  # noqa: E402

client = TestClient(app)


def test_login_with_valid_dev_credentials_returns_token():
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user_id"] == "admin"
    assert "admin" in body["roles"]


def test_login_with_invalid_credentials_is_401():
    resp = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user_is_401():
    resp = client.post("/auth/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


def test_issued_token_authorizes_protected_endpoint():
    """Given um token emitido pelo /login, When chama rota RBAC, Then é aceito."""

    AuthManager.configure(secret_key="x" * 40, required=True)
    try:
        token = client.post(
            "/auth/login", json={"username": "admin", "password": "admin"}
        ).json()["access_token"]
        resp = client.get(
            "/api/v1/ledger", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code not in (401, 403)
    finally:
        AuthManager.configure(required=False)
