"""Testes unitários — S-E.2: Relatórios premium + SQL Workbench seguro."""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# QuerySafetyValidator — núcleo de segurança do workbench
# ─────────────────────────────────────────────────────────────────────────────


from src.api.routes.workbench import QuerySafetyViolation, validate_query_safety


class TestQuerySafetyValidator:
    def test_select_simples_aprovado(self):
        validate_query_safety("SELECT id, tipo FROM escrituracao_fiscal LIMIT 10")

    def test_select_com_where_aprovado(self):
        validate_query_safety("SELECT * FROM apuracao_fiscal WHERE tributo = 'ICMS'")

    def test_select_com_join_aprovado(self):
        validate_query_safety(
            "SELECT e.id, a.tributo FROM escrituracao_fiscal e "
            "JOIN apuracao_fiscal a ON e.id = a.escrituracao_id"
        )

    def test_insert_bloqueado(self):
        with pytest.raises(QuerySafetyViolation, match="INSERT"):
            validate_query_safety("INSERT INTO tabela VALUES (1, 'x')")

    def test_update_bloqueado(self):
        with pytest.raises(QuerySafetyViolation, match="UPDATE"):
            validate_query_safety("UPDATE escrituracao_fiscal SET status='erro'")

    def test_delete_bloqueado(self):
        with pytest.raises(QuerySafetyViolation, match="DELETE"):
            validate_query_safety("DELETE FROM apuracao_fiscal WHERE id = 1")

    def test_drop_bloqueado(self):
        with pytest.raises(QuerySafetyViolation, match="DROP"):
            validate_query_safety("DROP TABLE escrituracao_fiscal")

    def test_create_bloqueado(self):
        with pytest.raises(QuerySafetyViolation, match="CREATE"):
            validate_query_safety("CREATE TABLE nova_tabela (id INT)")

    def test_alter_bloqueado(self):
        with pytest.raises(QuerySafetyViolation, match="ALTER"):
            validate_query_safety("ALTER TABLE escrituracao_fiscal ADD COLUMN x TEXT")

    def test_truncate_bloqueado(self):
        with pytest.raises(QuerySafetyViolation, match="TRUNCATE"):
            validate_query_safety("TRUNCATE TABLE apuracao_fiscal")

    def test_union_injection_bloqueado(self):
        with pytest.raises(QuerySafetyViolation):
            validate_query_safety("SELECT 1 UNION SELECT password FROM users")

    def test_comment_injection_bloqueado(self):
        with pytest.raises(QuerySafetyViolation):
            validate_query_safety("SELECT 1 -- DROP TABLE users")

    def test_case_insensitive_bloqueado(self):
        with pytest.raises(QuerySafetyViolation):
            validate_query_safety("select 1; DrOp tAbLe users")

    def test_grant_bloqueado(self):
        with pytest.raises(QuerySafetyViolation):
            validate_query_safety("GRANT ALL ON tabela TO usuario")

    def test_exec_bloqueado(self):
        with pytest.raises(QuerySafetyViolation):
            validate_query_safety("EXEC xp_cmdshell 'ls'")


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────


from src.api.routes.reports import ReportResponse, ReportTipo, REPORT_TYPES
from src.api.routes.workbench import (
    QueryResult,
    QueryTemplateInfo,
    ValidacaoRequest,
    ValidacaoResponse,
    QUERY_TEMPLATES,
)


class TestReportModels:
    def test_report_tipo_model(self):
        rt = ReportTipo(
            tipo="apuracoes_tributo",
            nome="Apurações",
            descricao="Desc",
            colunas=["id", "tributo"],
        )
        assert rt.tipo == "apuracoes_tributo"
        assert len(rt.colunas) == 2

    def test_report_response_model(self):
        rr = ReportResponse(
            report_id="abc123",
            tipo="escrituracoes_status",
            total_linhas=3,
            dados=[{"id": "1"}, {"id": "2"}, {"id": "3"}],
        )
        assert rr.total_linhas == 3

    def test_query_result_model(self):
        qr = QueryResult(
            execution_id="xyz",
            query_id="escrituracoes_recentes",
            total_linhas=0,
            duration_ms=5,
            dados=[],
        )
        assert qr.duration_ms == 5

    def test_validacao_request_rejeita_vazio(self):
        with pytest.raises(Exception):
            ValidacaoRequest(sql="")

    def test_validacao_request_aceita_select(self):
        v = ValidacaoRequest(sql="SELECT 1")
        assert v.sql == "SELECT 1"


# ─────────────────────────────────────────────────────────────────────────────
# Catálogos
# ─────────────────────────────────────────────────────────────────────────────


class TestCatalogues:
    def test_report_types_nao_vazio(self):
        assert len(REPORT_TYPES) >= 4

    def test_report_types_tem_colunas(self):
        for k, v in REPORT_TYPES.items():
            assert "colunas" in v, f"{k} sem colunas"
            assert len(v["colunas"]) > 0

    def test_query_templates_nao_vazio(self):
        assert len(QUERY_TEMPLATES) >= 4

    def test_query_templates_tem_parametros(self):
        for k, v in QUERY_TEMPLATES.items():
            assert "nome" in v, f"{k} sem nome"
            assert "parametros" in v, f"{k} sem parametros"


# ─────────────────────────────────────────────────────────────────────────────
# CSV helper
# ─────────────────────────────────────────────────────────────────────────────


from src.api.routes.reports import _to_csv


class TestCsvHelper:
    def test_to_csv_basico(self):
        rows = [{"id": "1", "tipo": "EFD"}, {"id": "2", "tipo": "XML"}]
        csv = _to_csv(rows, ["id", "tipo"])
        assert "id,tipo" in csv
        assert "EFD" in csv
        assert "XML" in csv

    def test_to_csv_vazio(self):
        csv = _to_csv([], ["id", "tipo"])
        assert "id,tipo" in csv

    def test_to_csv_ignora_colunas_extras(self):
        rows = [{"id": "1", "tipo": "EFD", "extra": "ignorado"}]
        csv = _to_csv(rows, ["id", "tipo"])
        assert "ignorado" not in csv


# ─────────────────────────────────────────────────────────────────────────────
# HTTP endpoints — sem DB (503 esperado ou 422 para params inválidos)
# ─────────────────────────────────────────────────────────────────────────────


def _make_client():
    from src.api.main import (
        app,
    )  # side-effect: AuthManager.configure(required=False) via config

    return TestClient(app, raise_server_exceptions=False)


class TestReportsEndpoints:
    def setup_method(self):
        self.client = _make_client()

    def test_list_tipos_200(self):
        resp = self.client.get(
            "/api/v1/fiscal/reports/tipos",
            headers={},
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 4

    def test_gerar_tipo_invalido_422(self):
        resp = self.client.get(
            "/api/v1/fiscal/reports/gerar?tipo=inexistente",
            headers={},
        )
        assert resp.status_code == 422

    def test_gerar_formato_invalido_422(self):
        resp = self.client.get(
            "/api/v1/fiscal/reports/gerar?tipo=escrituracoes_status&formato=pdf",
            headers={},
        )
        assert resp.status_code == 422

    def test_gerar_sem_db_200_ou_503(self):
        resp = self.client.get(
            "/api/v1/fiscal/reports/gerar?tipo=escrituracoes_status",
            headers={},
        )
        assert resp.status_code in (200, 503)

    def test_gerar_csv_content_type(self):
        resp = self.client.get(
            "/api/v1/fiscal/reports/gerar?tipo=escrituracoes_status&formato=csv",
            headers={},
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert "text/csv" in resp.headers.get("content-type", "")


class TestWorkbenchEndpoints:
    def setup_method(self):
        self.client = _make_client()

    def test_list_queries_200(self):
        resp = self.client.get(
            "/api/v1/fiscal/workbench/queries",
            headers={},
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) >= 4

    def test_executar_query_invalida_422(self):
        resp = self.client.post(
            "/api/v1/fiscal/workbench/executar?query_id=nao_existe",
            headers={},
        )
        assert resp.status_code == 422

    def test_executar_sem_db_200_ou_503(self):
        resp = self.client.post(
            "/api/v1/fiscal/workbench/executar?query_id=escrituracoes_recentes",
            headers={},
        )
        assert resp.status_code in (200, 503)

    def test_validar_select_seguro(self):
        resp = self.client.post(
            "/api/v1/fiscal/workbench/validar",
            json={"sql": "SELECT id FROM escrituracao_fiscal"},
            headers={},
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert data["seguro"] is True

    def test_validar_drop_inseguro(self):
        resp = self.client.post(
            "/api/v1/fiscal/workbench/validar",
            json={"sql": "DROP TABLE escrituracao_fiscal"},
            headers={},
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert data["seguro"] is False

    def test_registrar_com_sql_invalido_422(self):
        resp = self.client.post(
            "/api/v1/fiscal/workbench/registrar",
            json={
                "query_id": "teste_drop",
                "nome": "Drop Test",
                "descricao": "Teste",
                "sql_preview": "DROP TABLE users",
            },
            headers={},
        )
        assert resp.status_code == 422
