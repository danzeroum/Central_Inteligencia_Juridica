"""Higiene/observabilidade (Onda 5) + regressão dos itens já resolvidos (Onda 0).

Onda 5 (V&V): C-14 (SafetyProtocol real), H01 (segredo JWT nunca vazio), M06
(datetime tz-aware), H06 (API pública do supervisor), /metrics Prometheus.

Onda 0 — comprova o estado correto de itens que o PDF reportava como abertos
mas já estavam resolvidos: H05 (validação de agent_id), D11 (CI/CD existe),
export_openapi disponível, geração de OpenAPI íntegra.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402

client = TestClient(app)


# --- C-14: SafetyProtocol aplica controles reais ----------------------------
class TestSafetyProtocol:
    def test_redacts_pii_in_output(self):
        from src.protocols.safety_protocol import SafetyProtocol

        out = SafetyProtocol().validate_output({"texto": "meu CPF é 123.456.789-09"})
        assert "123.456.789-09" not in out["texto"]

    def test_truncates_oversized_field(self):
        from src.protocols.safety_protocol import SafetyProtocol

        proto = SafetyProtocol()
        out = proto.validate_output({"big": "x" * (proto.MAX_FIELD_LENGTH + 500)})
        assert len(out["big"]) == proto.MAX_FIELD_LENGTH

    def test_recurses_into_nested_structures(self):
        from src.protocols.safety_protocol import SafetyProtocol

        out = SafetyProtocol().validate_output(
            {"nested": {"items": ["CPF 123.456.789-09"]}}
        )
        assert "123.456.789-09" not in out["nested"]["items"][0]


# --- H01: segredo JWT nunca vazio -------------------------------------------
def test_jwt_secret_is_never_empty():
    from src.api.auth import AuthManager

    assert AuthManager.SECRET_KEY  # não vazio
    assert len(AuthManager.SECRET_KEY) >= 32


# --- M06: datetime tz-aware -------------------------------------------------
def test_span_record_timestamps_are_tz_aware():
    from src.utils.observability import SpanRecord

    span = SpanRecord(operation="op", metadata={})
    span.close()
    assert span.start_time.tzinfo is not None
    assert span.end_time.tzinfo is not None


# --- /metrics: endpoint Prometheus ------------------------------------------
def test_metrics_endpoint_exposes_prometheus():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")


# --- H10: VectorMemory é lazy (não bloqueia o startup) ----------------------
def test_supervisor_vector_memory_is_lazy():
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    # Logo após a construção, o cliente de memória ainda NÃO foi instanciado.
    assert agent._memory is None
    # O primeiro acesso instancia sob demanda.
    _ = agent.memory
    assert agent._memory is not None


# --- H06: API pública do supervisor (sem chamar métodos privados na HTTP) ---
def test_supervisor_exposes_public_methods():
    from src.api.main import supervisor_agent

    assert hasattr(supervisor_agent, "identify_all_tribunals")
    assert hasattr(supervisor_agent, "delegate_to_tribunal_agent")
    assert callable(supervisor_agent.identify_all_tribunals)


# --- Onda 0: H05 — validação de agent_id ------------------------------------
class TestAgentIdValidationRegression:
    @pytest.mark.parametrize("bad", ["../etc", "a b", "x" * 65, "drop;table", ""])
    def test_invalid_agent_ids_rejected(self, bad):
        from fastapi import HTTPException

        from src.api.main import _validate_agent_id

        with pytest.raises(HTTPException):
            _validate_agent_id(bad, "agent_id")

    def test_valid_agent_id_accepted(self):
        from src.api.main import _validate_agent_id

        assert _validate_agent_id("tjsp_agent.v1-2", "agent_id") == "tjsp_agent.v1-2"


# --- Onda 0: D11 — CI/CD existe (PDF afirmava que não) ----------------------
def test_ci_workflow_exists():
    ci = Path(".github/workflows/ci.yml")
    assert ci.exists()
    content = ci.read_text(encoding="utf-8")
    assert "bandit" in content and "pytest" in content


# --- Onda 0: export_openapi disponível e OpenAPI íntegro --------------------
def test_export_openapi_script_present():
    assert Path("scripts/dev/export_openapi.py").exists()


def test_openapi_schema_is_generated():
    schema = app.openapi()
    assert schema["info"]["title"] == "Central Inteligência Jurídica"
    assert "/tasks" in schema["paths"]
