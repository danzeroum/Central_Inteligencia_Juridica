"""Testes de integração — rotas do módulo Fiscal (Bloco A: S-A.1 e S-A.2)."""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

_VALID_CNPJ = "11222333000181"
_VALID_CNPJ_FORMATTED = "11.222.333/0001-81"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _due_diligence_svc_mock():
    svc = MagicMock()
    svc.generate_report = AsyncMock(
        return_value={
            "cnpj_masked": "11.***.***/****-81",
            "overall_risk_score": 0.25,
            "fiscal": {"risk_score": 0.3, "summary": "Sem pendências fiscais."},
            "legal": {"risk_score": 0.2, "summary": "Sem processos relevantes."},
            "module": "cadastro_risco",
            "version": "1.0.0",
        }
    )
    return svc


def _consultoria_svc_mock():
    svc = MagicMock()
    svc.gerar_parecer = AsyncMock(
        return_value={
            "regime": "Simples Nacional (LC 123/2006)",
            "cnae": "6201-5/01",
            "porte": "ME (até R$ 360 mil/ano)",
            "pergunta": "Qual a alíquota do ISS?",
            "recomendacao": "[LC 116/2003] ISS 2%-5%",
            "citacoes": [{"texto": "LC 116/2003", "metadata": {}, "score": 0.9}],
            "guardrail": "CJ-001: sem invenção de normas.",
            "status": "preliminar",
            "module": "consultoria_tributaria",
        }
    )
    return svc


# ── Due Diligência 360° ──────────────────────────────────────────────────────


def test_due_diligence_success(monkeypatch):
    import src.api.routes.fiscal as fiscal_mod

    mock_svc = _due_diligence_svc_mock()
    monkeypatch.setattr(
        fiscal_mod, "DueDiligenceService", lambda: mock_svc, raising=False
    )

    with monkeypatch.context() as m:
        # Patch inside the route function's local import
        import src.fiscal.due_diligence as dd_mod

        m.setattr(dd_mod, "DueDiligenceService", lambda: mock_svc)

        resp = client.get(f"/api/v1/fiscal/due-diligence/{_VALID_CNPJ}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["module"] == "cadastro_risco"
    assert "cnpj_masked" in body
    assert "overall_risk_score" in body


def test_due_diligence_invalid_format_is_400():
    resp = client.get("/api/v1/fiscal/due-diligence/123")
    assert resp.status_code == 400


def test_due_diligence_dots_dashes_format_accepted(monkeypatch):
    """CNPJ com pontos e traço (sem barra) é aceito no path param."""
    import src.fiscal.due_diligence as dd_mod

    mock_svc = _due_diligence_svc_mock()
    monkeypatch.setattr(dd_mod, "DueDiligenceService", lambda: mock_svc)

    # Formato sem barra: pontos e traço apenas (barra causaria 404 no roteador)
    resp = client.get("/api/v1/fiscal/due-diligence/11.222.333.0001-81")
    assert resp.status_code == 200


def test_due_diligence_service_value_error_is_400(monkeypatch):
    import src.fiscal.due_diligence as dd_mod

    svc = MagicMock()
    svc.generate_report = AsyncMock(
        side_effect=ValueError("CNPJ inválido: digito verificador")
    )
    monkeypatch.setattr(dd_mod, "DueDiligenceService", lambda: svc)

    resp = client.get(f"/api/v1/fiscal/due-diligence/{_VALID_CNPJ}")
    assert resp.status_code == 400


# ── Consultoria Tributária ───────────────────────────────────────────────────

_VALID_CONSULTORIA_BODY = {
    "regime": "simples_nacional",
    "cnae": "6201-5/01",
    "porte": "me",
    "pergunta": "Qual a alíquota do ISS para desenvolvimento de software?",
}


def test_consultoria_success(monkeypatch):
    import src.fiscal.consultoria as cons_mod

    mock_svc = _consultoria_svc_mock()
    monkeypatch.setattr(cons_mod, "ConsultoriaService", lambda: mock_svc)

    resp = client.post("/api/v1/fiscal/consultoria", json=_VALID_CONSULTORIA_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "preliminar"
    assert "guardrail" in body
    assert body["module"] == "consultoria_tributaria"


def test_consultoria_invalid_regime_is_422():
    body = {**_VALID_CONSULTORIA_BODY, "regime": "super_simples"}
    resp = client.post("/api/v1/fiscal/consultoria", json=body)
    assert resp.status_code == 422


def test_consultoria_invalid_porte_is_422():
    body = {**_VALID_CONSULTORIA_BODY, "porte": "gigante"}
    resp = client.post("/api/v1/fiscal/consultoria", json=body)
    assert resp.status_code == 422


def test_consultoria_missing_field_is_422():
    resp = client.post(
        "/api/v1/fiscal/consultoria",
        json={"regime": "simples_nacional", "porte": "me"},
    )
    assert resp.status_code == 422


def test_consultoria_pergunta_too_short_is_422():
    body = {**_VALID_CONSULTORIA_BODY, "pergunta": "oi"}
    resp = client.post("/api/v1/fiscal/consultoria", json=body)
    assert resp.status_code == 422


# ── Módulos registrados incluem novos módulos do Bloco A ────────────────────


def test_modules_list_includes_fiscal_modules():
    """Verifica que os módulos do Bloco A aparecem no registry."""
    from src.modules.registry import get_module_registry

    registry = get_module_registry()
    module_ids = {m.module_id for m in registry.list_all()}
    assert "cadastro_risco" in module_ids
    assert "consultoria_tributaria" in module_ids
