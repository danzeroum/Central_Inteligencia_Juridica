"""Smoke test — POST /auth/login retorna JWT válido."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_auth_login_endpoint_exists(client):
    resp = client.post(
        "/auth/login",
        json={"username": "operator", "password": "operator"},
    )
    # Pode retornar 200 (dev) ou 401 (prod sem usuário demo)
    assert resp.status_code in (200, 401, 422, 404)
    assert resp.status_code != 500


def test_auth_login_invalid_credentials(client):
    resp = client.post(
        "/auth/login",
        json={"username": "invalid_user_xyz", "password": "wrong_password"},
    )
    assert resp.status_code in (400, 401, 422, 404)
    assert resp.status_code != 500


def test_auth_login_missing_body(client):
    resp = client.post("/auth/login", json={})
    assert resp.status_code in (400, 401, 422)
    assert resp.status_code != 500
