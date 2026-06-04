"""Endpoint HTTP de jurisprudência (Frente F.1 — fecha a dívida do ADR-013).

Sem DATAJUD_API_KEY, o serviço degrada para mock — os testes são determinísticos
e não dependem de rede. Um teste com serviço fake valida o roteamento por ``q``.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

from fastapi.testclient import TestClient  # noqa: E402

from src.api import jurisprudencia_endpoints as je  # noqa: E402
from src.api.main import app  # noqa: E402
from src.services.datajud_schemas import (
    DataJudProcesso,
    DataJudSearchResult,
)  # noqa: E402

client = TestClient(app)


# ── Fallback gracioso (sem chave) ────────────────────────────────────────────
def test_busca_por_processo_sem_chave_retorna_simulado():
    resp = client.get("/api/v1/jurisprudencia", params={"tribunal": "tjsp", "q": "123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["alias"] == "tjsp"
    assert body["source"] == "simulated"  # sem DATAJUD_API_KEY → mock
    assert body["fallback"] is True


def test_busca_por_assunto_sem_chave_retorna_simulado():
    resp = client.get(
        "/api/v1/jurisprudencia", params={"tribunal": "trf1", "assunto": [2086]}
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "simulated"


# ── Validações ───────────────────────────────────────────────────────────────
def test_tribunal_invalido_e_400():
    resp = client.get("/api/v1/jurisprudencia", params={"tribunal": "tj/sp", "q": "1"})
    assert resp.status_code == 400


def test_sem_q_e_sem_assunto_e_400():
    resp = client.get("/api/v1/jurisprudencia", params={"tribunal": "tjsp"})
    assert resp.status_code == 400


# ── Roteamento por ``q`` (serviço fake) ──────────────────────────────────────
def test_q_roteia_para_buscar_processo(monkeypatch):
    capturado = {}

    class _FakeService:
        async def buscar_processo(self, alias, numero):
            capturado["alias"] = alias
            capturado["numero"] = numero
            return DataJudSearchResult(
                total=1,
                processos=[DataJudProcesso(numeroProcesso=numero, tribunal="TJSP")],
                source="real_api",
                alias=alias,
            )

        async def buscar_por_assunto(self, *a, **k):  # pragma: no cover
            raise AssertionError("não deveria ser chamado quando q está presente")

    monkeypatch.setattr(je, "datajud_service", _FakeService())
    resp = client.get(
        "/api/v1/jurisprudencia", params={"tribunal": "TJSP", "q": " 00008323 "}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "real_api"
    assert capturado["alias"] == "tjsp"  # normalizado para minúsculas
    assert capturado["numero"] == "00008323"  # trim aplicado


# ── Contrato OpenAPI (response_model declarado) ──────────────────────────────
def test_endpoint_tem_response_model_no_openapi():
    schema = app.openapi()
    content = schema["paths"]["/api/v1/jurisprudencia"]["get"]["responses"]["200"][
        "content"
    ]
    assert "$ref" in content["application/json"]["schema"]
