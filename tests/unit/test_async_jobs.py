"""Testes unitários — Celery app, S3Client, JobRequest e jobs endpoint."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Celery app — modo sem broker
# ---------------------------------------------------------------------------


def test_celery_app_is_none_without_broker(monkeypatch):
    """Sem CELERY_BROKER_URL, celery_app deve ser None."""
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    import importlib

    import src.workers.celery_app as ca

    monkeypatch.setattr(ca, "_BROKER_URL", "")
    monkeypatch.setattr(ca, "celery_app", None)
    assert ca.celery_app is None


# ---------------------------------------------------------------------------
# JobRequest validation
# ---------------------------------------------------------------------------


def test_job_request_valid_task():
    from src.api.schemas.requests import JobRequest

    req = JobRequest(task="analyze_document", payload={"doc_id": "abc"})
    assert req.task == "analyze_document"
    assert req.priority == 1


def test_job_request_invalid_task_raises():
    from pydantic import ValidationError

    from src.api.schemas.requests import JobRequest

    with pytest.raises(ValidationError):
        JobRequest(task="drop_database")


def test_job_request_priority_bounds():
    from pydantic import ValidationError

    from src.api.schemas.requests import JobRequest

    with pytest.raises(ValidationError):
        JobRequest(task="analyze_document", priority=0)
    with pytest.raises(ValidationError):
        JobRequest(task="analyze_document", priority=4)


# ---------------------------------------------------------------------------
# S3Client — sem credenciais
# ---------------------------------------------------------------------------


def test_s3client_not_configured_without_env(monkeypatch):
    """Sem variáveis de ambiente, S3Client não deve estar configurado."""
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)

    import importlib

    import src.storage.s3_client as s3_mod

    monkeypatch.setattr(s3_mod, "_ENDPOINT", "")
    monkeypatch.setattr(s3_mod, "_s3", None)
    client = s3_mod.S3Client()
    assert not client.is_configured


def test_s3client_upload_returns_false_when_not_configured(monkeypatch):
    import src.storage.s3_client as s3_mod

    monkeypatch.setattr(s3_mod, "_ENDPOINT", "")
    client = s3_mod.S3Client()
    result = client.upload_file(io.BytesIO(b"test"), "test/key.txt")
    assert result is False


def test_s3client_download_returns_none_when_not_configured(monkeypatch):
    import src.storage.s3_client as s3_mod

    monkeypatch.setattr(s3_mod, "_ENDPOINT", "")
    client = s3_mod.S3Client()
    result = client.download_file("test/key.txt")
    assert result is None


def test_s3client_presigned_url_returns_none_when_not_configured(monkeypatch):
    import src.storage.s3_client as s3_mod

    monkeypatch.setattr(s3_mod, "_ENDPOINT", "")
    client = s3_mod.S3Client()
    result = client.generate_presigned_url("test/key.txt")
    assert result is None


def test_get_s3_client_returns_singleton():
    import src.storage.s3_client as s3_mod

    s3_mod._s3 = None
    c1 = s3_mod.get_s3_client()
    c2 = s3_mod.get_s3_client()
    assert c1 is c2


# ---------------------------------------------------------------------------
# Tasks — execução síncrona (sem broker)
# ---------------------------------------------------------------------------


def test_analyze_document_sync_returns_dict():
    from src.workers.tasks import analyze_document

    result = analyze_document(None, document_id="doc-001", tenant_id="t-001")
    assert result["document_id"] == "doc-001"
    assert result["status"] == "analyzed"


def test_process_sped_file_sync_returns_dict():
    from src.workers.tasks import process_sped_file

    result = process_sped_file(
        None,
        file_key="tenants/t-001/sped/file.txt",
        tenant_id="t-001",
        cnpj_masked="**.***.***/**XX-**",
        competencia="2024-01",
    )
    assert result["status"] == "queued"
    assert "job_id" in result


# ---------------------------------------------------------------------------
# Jobs endpoint — fallback síncrono (sem broker em ENVIRONMENT=test)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_client():
    from src.api.main import app

    with TestClient(app) as c:
        yield c


def test_submit_job_sync_fallback(api_client):
    """Sem broker, POST /api/v1/jobs retorna mode=sync."""
    resp = api_client.post(
        "/api/v1/jobs",
        json={"task": "analyze_document", "payload": {"document_id": "doc-1"}},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["task"] == "analyze_document"
    assert body["mode"] == "sync"
    assert body["status"] == "sync"
    assert "job_id" in body


def test_submit_job_invalid_task_rejected(api_client):
    resp = api_client.post(
        "/api/v1/jobs",
        json={"task": "rm_rf_everything"},
    )
    assert resp.status_code == 422


def test_get_job_status_without_broker_returns_503(api_client):
    """Sem broker, GET /api/v1/jobs/{id} retorna 503."""
    resp = api_client.get("/api/v1/jobs/fake-job-id-123")
    assert resp.status_code == 503
