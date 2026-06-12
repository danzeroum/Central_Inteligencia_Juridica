"""Testes de integração — Bloco B: endpoint POST /api/v1/fiscal/upload."""

from __future__ import annotations

import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(scope="module")
def api_client():
    from src.api.main import app

    with TestClient(app) as c:
        yield c


def _make_sped_payload(filename="efd.txt", content=b"|0000|...|"):
    return {"file": (filename, io.BytesIO(content), "text/plain")}


def _make_zip_payload(inner_content=b"|0000|...|", zip_name="efd.zip"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("efd.txt", inner_content)
    buf.seek(0)
    return {"file": (zip_name, buf, "application/zip")}


# ── Upload de arquivo válido ──────────────────────────────────────────────────


def test_upload_sped_txt_success(api_client):
    data = _make_sped_payload(content=b"|0000|SPED TEST|\n" * 10)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 1},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["file_type"] == "sped_txt"
    assert body["size_bytes"] > 0
    assert len(body["sha256"]) == 64
    assert "correlation_id" in body


def test_upload_xml_success(api_client):
    xml = b"<?xml version='1.0'?><nfeProc xmlns='http://www.portalfiscal.inf.br/nfe'><NFe/></nfeProc>"
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files={"file": ("nfe.xml", io.BytesIO(xml), "application/xml")},
        data={"tipo": "xml", "ano": 2025, "mes": 3},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["file_type"] == "xml"


def test_upload_zip_single_file_success(api_client):
    data = _make_zip_payload(inner_content=b"|0000|ZIP SPED|\n" * 20)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 6},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["file_type"] == "sped_txt"


# ── Rejeições de segurança ────────────────────────────────────────────────────


def test_upload_unsupported_content_type_rejected(api_client):
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
        data={"tipo": "outro", "ano": 2025, "mes": 1},
    )
    assert resp.status_code == 415


def test_upload_zip_multiple_files_rejected(api_client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", b"A")
        zf.writestr("b.txt", b"B")
    buf.seek(0)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files={"file": ("multi.zip", buf, "application/zip")},
        data={"tipo": "efd_icms", "ano": 2025, "mes": 1},
    )
    assert resp.status_code == 400


def test_upload_invalid_zip_rejected(api_client):
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files={"file": ("fake.zip", io.BytesIO(b"not a zip"), "application/zip")},
        data={"tipo": "outro", "ano": 2025, "mes": 1},
    )
    assert resp.status_code == 400


# ── Validação de parâmetros de form ──────────────────────────────────────────


def test_upload_invalid_tipo_rejected(api_client):
    data = _make_sped_payload()
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "sped_malicioso", "ano": 2025, "mes": 1},
    )
    assert resp.status_code == 422


def test_upload_invalid_mes_rejected(api_client):
    data = _make_sped_payload()
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 13},
    )
    assert resp.status_code == 422


def test_upload_invalid_ano_rejected(api_client):
    data = _make_sped_payload()
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 1999, "mes": 1},
    )
    assert resp.status_code == 422


def test_upload_anual_sem_mes_success(api_client):
    data = _make_sped_payload(content=b"|0000|ANUAL|\n")
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "outro", "ano": 2024},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["correlation_id"]


# ── Resposta inclui campos obrigatórios ───────────────────────────────────────


def test_upload_response_schema(api_client):
    data = _make_sped_payload()
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 2},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "correlation_id" in body
    assert "filename" in body
    assert "file_type" in body
    assert "size_bytes" in body
    assert "sha256" in body
    assert "message" in body


# ── Regime e UF no upload ─────────────────────────────────────────────────────


def test_upload_com_regime_lucro_presumido(api_client):
    data = _make_sped_payload(content=b"|0000|REGIME TEST|\n" * 5)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 1, "regime": "lucro_presumido"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "correlation_id" in body


def test_upload_com_uf_sp(api_client):
    data = _make_sped_payload(content=b"|0000|UF TEST|\n" * 5)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 1, "uf": "SP"},
    )
    assert resp.status_code == 202
    assert "correlation_id" in resp.json()


def test_upload_sem_regime_usa_lucro_real(api_client):
    data = _make_sped_payload(content=b"|0000|DEFAULT REGIME|\n" * 5)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 2},
    )
    assert resp.status_code == 202


def test_upload_regime_invalido_retorna_422(api_client):
    data = _make_sped_payload(content=b"|0000|BAD REGIME|\n" * 5)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 1, "regime": "regime_malicioso"},
    )
    assert resp.status_code == 422


def test_upload_uf_invalida_retorna_422(api_client):
    data = _make_sped_payload(content=b"|0000|BAD UF|\n" * 5)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 1, "uf": "SPX"},
    )
    assert resp.status_code == 422


def test_upload_uf_numerica_retorna_422(api_client):
    data = _make_sped_payload(content=b"|0000|NUMERIC UF|\n" * 5)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 1, "uf": "12"},
    )
    assert resp.status_code == 422


def test_upload_regime_simples_aceito(api_client):
    data = _make_sped_payload(content=b"|0000|SIMPLES|\n" * 5)
    resp = api_client.post(
        "/api/v1/fiscal/upload",
        files=data,
        data={"tipo": "efd_icms", "ano": 2025, "mes": 3, "regime": "simples"},
    )
    assert resp.status_code == 202
