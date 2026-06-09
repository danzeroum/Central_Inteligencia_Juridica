"""Smoke test — endpoints de perfil respondem sem erro de servidor."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_profile_endpoint_exists(client):
    resp = client.get("/api/v1/profile")
    # 401/403 em produção; 200 em test (sem auth)
    assert resp.status_code in (200, 401, 403, 422)
    assert resp.status_code != 500


def test_profile_area_endpoint_exists(client):
    resp = client.get("/api/v1/profile/area")
    assert resp.status_code in (200, 401, 403, 422)
    assert resp.status_code != 500


def test_profile_clientes_endpoint_exists(client):
    resp = client.get("/api/v1/profile/clientes")
    assert resp.status_code in (200, 401, 403, 422)
    assert resp.status_code != 500
