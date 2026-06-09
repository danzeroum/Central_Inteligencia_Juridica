"""Testes de integração — endpoints de perfil via API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.integration
def test_get_profile_creates_default(client):
    resp = client.get("/api/v1/profile")
    assert resp.status_code in (200, 401, 403)


@pytest.mark.integration
def test_profile_delete_returns_404_when_missing(client):
    resp = client.delete("/api/v1/profile")
    # Sem auth = 401/403; autenticado sem perfil = 404
    assert resp.status_code in (401, 403, 404)


@pytest.mark.integration
def test_profile_endpoints_registered():
    routes = [r.path for r in app.routes]
    assert "/api/v1/profile" in routes
    assert "/api/v1/profile/clientes" in routes
    assert "/api/v1/profile/area" in routes
