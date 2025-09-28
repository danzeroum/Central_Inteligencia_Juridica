"""Testes de integração para a API pública da Central de Inteligência Jurídica."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

# Garante que o diretório raiz esteja no sys.path para importar `src`
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.api.main import app  # noqa: E402  pylint: disable=wrong-import-position

client = TestClient(app)


@pytest.fixture(name="client")
def client_fixture() -> TestClient:
    """Fornece um TestClient configurado para a aplicação FastAPI."""

    return client


def test_health_check_deve_retornar_ok(client: TestClient) -> None:
    """O endpoint GET /health deve retornar 200 OK com o payload esperado."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_process_task_com_sucesso(client: TestClient) -> None:
    """O endpoint POST /api/v1/tasks deve retornar sucesso com payload válido."""

    task_payload = {"task_description": "verificar status tjsp"}

    response = client.post("/api/v1/tasks", json=task_payload)
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "success"
    assert data["tribunal_used"] == "TJSP"
    assert "supervisor_result" in data
    assert "operation" in data["supervisor_result"]


def test_process_task_com_descricao_vazia_retorna_400(client: TestClient) -> None:
    """Uma descrição vazia deve produzir erro 400 no formato RFC 7807."""

    task_payload = {"task_description": " "}

    response = client.post("/api/v1/tasks", json=task_payload)
    problem = response.json()

    assert response.status_code == 400
    assert problem["status"] == 400
    assert problem["title"] == "Invalid Input"
    assert "vazio" in problem["detail"].lower()
    assert problem["type"].endswith("invalid-input")
    assert problem["instance"].endswith("/api/v1/tasks")


def test_process_task_com_corpo_malformado_retorna_400(client: TestClient) -> None:
    """Um corpo malformado deve retornar 400 com ProblemDetail padronizado."""

    invalid_payload = {"descricao_da_tarefa": "status tjsp"}

    response = client.post("/api/v1/tasks", json=invalid_payload)
    problem = response.json()

    assert response.status_code == 400
    assert problem["status"] == 400
    assert problem["title"] == "Invalid Input"
    assert problem["detail"].startswith("task_description: Field required")
    assert problem["type"].endswith("invalid-input")
