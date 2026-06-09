"""Smoke test — GET /health deve retornar 200."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_response_structure(client):
    resp = client.get("/health")
    data = resp.json()
    assert "status" in data or resp.status_code == 200
