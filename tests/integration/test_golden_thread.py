"""Fio de Ouro — Bloco C (S-C.2).

Teste de integração ponta-a-ponta do pipeline fiscal:
  upload → processamento inline → registros canônicos → achados de regra
  → apuração calculada → divergência E110

Executa via TestClient (sem Celery/MinIO/Postgres reais).
Quando banco de dados não disponível, testa o pipeline de processamento
diretamente (parse + regras + apuração) e sinaliza com pytest.mark.
"""

from __future__ import annotations

import io
import os
from decimal import Decimal
from pathlib import Path

import pytest

os.environ.setdefault("ENVIRONMENT", "test")

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "fiscal"


@pytest.fixture(scope="module")
def api_client():
    from src.api.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _upload_fixture(client, filename: str, tipo: str = "efd_icms"):
    data = (_FIXTURES / filename).read_bytes()
    resp = client.post(
        "/api/v1/fiscal/upload",
        files={"file": (filename, io.BytesIO(data), "text/plain")},
        data={"tipo": tipo, "ano": 2025, "mes": 1},
    )
    return resp, data


# ─────────────────────────────────────────────────────────────────────────────
# Parte A: pipeline EFD-ICMS de ponta a ponta (parse + regras + apuração)
# ─────────────────────────────────────────────────────────────────────────────


class TestGoldenThreadICMS:
    """Fio-de-ouro EFD-ICMS: upload → parse → regras → apuração devedor."""

    def test_upload_fixture_efd_icms_aceito(self, api_client):
        resp, _ = _upload_fixture(api_client, "efd_icms_devedor.txt", "efd_icms")
        assert resp.status_code == 202
        body = resp.json()
        assert "correlation_id" in body
        assert body["file_type"] == "sped_txt"

    def test_pipeline_parse_registros_canonicos(self):
        """Parse do fixture EFD-ICMS produz registros canônicos contados."""
        from src.fiscal.parser.registry import get_parser

        data = (_FIXTURES / "efd_icms_devedor.txt").read_bytes()
        parser = get_parser("efd_icms")
        result = parser.parse(data, encoding="utf-8")

        assert result.total_registros > 0
        assert "C" in result.registros_por_bloco
        assert "E" in result.registros_por_bloco

        c100_count = result.registros_por_tipo.get("C100", 0)
        assert c100_count == 3  # 2 saída + 1 entrada

    def test_pipeline_achados_regras(self):
        """Motor de regras valida os C100 do fixture (sem violações no devedor)."""
        from src.fiscal.parser.registry import get_parser
        from src.fiscal.rules_engine import get_rules_engine

        data = (_FIXTURES / "efd_icms_devedor.txt").read_bytes()
        parser = get_parser("efd_icms")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_rules_engine("lucro_real")
        result = engine.validate(parse_result.records)

        # O fixture devedor não tem violações de regra
        assert result.aprovado is True
        assert len(result.erros) == 0

    def test_pipeline_apuracao_devedor_saldo_esperado(self):
        """Apuração ICMS: débitos=180, créditos=60, saldo=120 → devedor."""
        # Conta manual:
        # C100 saída #1: vl_icms=120
        # C100 saída #2: vl_icms=60
        # C100 entrada #1: vl_icms=60
        # total_debitos = 120 + 60 = 180
        # total_creditos = 60
        # saldo_apurado = 180 - 60 - 0 = 120 (devedor)
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.registry import get_parser

        data = (_FIXTURES / "efd_icms_devedor.txt").read_bytes()
        parser = get_parser("efd_icms")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_apuracao_engine()
        resultado = engine.calcular(parse_result.records, tipo="efd_icms")

        assert len(resultado.items) == 1
        item = resultado.items[0]
        assert item.tributo == "ICMS"
        assert item.total_debitos == Decimal("180")
        assert item.total_creditos == Decimal("60")
        assert item.saldo_apurado == Decimal("120")
        assert item.situacao == "devedor"
        assert resultado.aprovado is True  # E110 match

    def test_pipeline_apuracao_divergencia_e110(self):
        """Fixture divergência: E110 declara debitos=300 vs computado=120 → ERRO."""
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.registry import get_parser
        from src.fiscal.reconciliation import Severidade

        data = (_FIXTURES / "efd_icms_divergencia.txt").read_bytes()
        parser = get_parser("efd_icms")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_apuracao_engine()
        resultado = engine.calcular(parse_result.records, tipo="efd_icms")

        assert resultado.aprovado is False
        assert len(resultado.items) == 1
        item = resultado.items[0]
        erros = [d for d in item.divergencias if d.severidade == Severidade.ERRO]
        assert len(erros) >= 1
        campos_com_erro = {d.campo for d in erros}
        assert "vl_tot_debitos" in campos_com_erro

    def test_pipeline_apuracao_credor(self):
        """Fixture credor: créditos > débitos → situacao=credor."""
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.registry import get_parser

        data = (_FIXTURES / "efd_icms_credor.txt").read_bytes()
        parser = get_parser("efd_icms")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_apuracao_engine()
        resultado = engine.calcular(parse_result.records, tipo="efd_icms")

        item = resultado.items[0]
        assert item.situacao == "credor"
        assert item.saldo_apurado < 0

    def test_pipeline_apuracao_saldo_anterior(self):
        """Fixture saldo anterior: saldo_credor_ant=50 reduz devedor."""
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.registry import get_parser

        data = (_FIXTURES / "efd_icms_saldo_anterior.txt").read_bytes()
        parser = get_parser("efd_icms")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_apuracao_engine()
        item = engine.calcular_icms(
            parse_result.records, saldo_credor_anterior=Decimal("50")
        )
        assert item.saldo_credor_anterior == Decimal("50")
        assert item.saldo_apurado == Decimal("50")
        assert item.situacao == "devedor"


# ─────────────────────────────────────────────────────────────────────────────
# Parte B: pipeline EFD-Contribuições (PIS + COFINS)
# ─────────────────────────────────────────────────────────────────────────────


class TestGoldenThreadContrib:
    """Fio-de-ouro EFD-Contrib: upload → apuração PIS/COFINS devedor."""

    def test_upload_fixture_efd_contrib_aceito(self, api_client):
        resp, _ = _upload_fixture(api_client, "efd_contrib_devedor.txt", "efd_contrib")
        assert resp.status_code == 202

    def test_pipeline_apuracao_pis_cofins_devedor(self):
        """Apuração EFD-Contrib: PIS=99, COFINS=456, ambos devedor."""
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.registry import get_parser

        data = (_FIXTURES / "efd_contrib_devedor.txt").read_bytes()
        parser = get_parser("efd_contrib")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_apuracao_engine()
        resultado = engine.calcular(parse_result.records, tipo="efd_contrib")

        assert len(resultado.items) == 2
        by_tributo = {i.tributo: i for i in resultado.items}

        pis = by_tributo["PIS"]
        assert pis.total_debitos == Decimal("99")
        assert pis.situacao == "devedor"
        assert len(pis.divergencias) == 0

        cofins = by_tributo["COFINS"]
        assert cofins.total_debitos == Decimal("456")
        assert cofins.situacao == "devedor"
        assert len(cofins.divergencias) == 0

    def test_pipeline_pis_divergencia_m200(self):
        """Fixture divergência PIS: M210=99 vs M200=200 → ERRO."""
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.registry import get_parser
        from src.fiscal.reconciliation import Severidade

        data = (_FIXTURES / "efd_contrib_divergencia_pis.txt").read_bytes()
        parser = get_parser("efd_contrib")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_apuracao_engine()
        resultado = engine.calcular(parse_result.records, tipo="efd_contrib")

        pis = next(i for i in resultado.items if i.tributo == "PIS")
        assert len(pis.divergencias) == 1
        assert pis.divergencias[0].severidade == Severidade.ERRO
        assert resultado.aprovado is False

    def test_pipeline_cofins_divergencia_m600(self):
        """Fixture divergência COFINS: M610=456 vs M600=900 → ERRO."""
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.registry import get_parser

        data = (_FIXTURES / "efd_contrib_divergencia_cofins.txt").read_bytes()
        parser = get_parser("efd_contrib")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_apuracao_engine()
        resultado = engine.calcular(parse_result.records, tipo="efd_contrib")

        cofins = next(i for i in resultado.items if i.tributo == "COFINS")
        assert len(cofins.divergencias) == 1
        assert resultado.aprovado is False

    def test_pipeline_multiplos_m210_m610(self):
        """Fixture múltiplos: soma 3 M210 = 99 e 3 M610 = 456."""
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.registry import get_parser

        data = (_FIXTURES / "efd_contrib_multiplos.txt").read_bytes()
        parser = get_parser("efd_contrib")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_apuracao_engine()
        resultado = engine.calcular(parse_result.records, tipo="efd_contrib")

        by_tributo = {i.tributo: i for i in resultado.items}
        assert by_tributo["PIS"].detalhes["total_m210_linhas"] == 3
        assert by_tributo["COFINS"].detalhes["total_m610_linhas"] == 3
        assert resultado.aprovado is True

    def test_pipeline_equilibrado(self):
        """Fixture equilibrado: sem M210/M610 → saldo=0, equilibrado."""
        from src.fiscal.apuracao import get_apuracao_engine
        from src.fiscal.parser.registry import get_parser

        data = (_FIXTURES / "efd_contrib_equilibrado.txt").read_bytes()
        parser = get_parser("efd_contrib")
        parse_result = parser.parse(data, encoding="utf-8")

        engine = get_apuracao_engine()
        resultado = engine.calcular(parse_result.records, tipo="efd_contrib")

        for item in resultado.items:
            assert item.situacao == "equilibrado"
            assert item.saldo_apurado == Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
# Parte C: endpoints HTTP (status, achados, apuração)
# ─────────────────────────────────────────────────────────────────────────────


class TestGoldenThreadHTTPEndpoints:
    """Testa endpoints HTTP com respostas esperadas (sem DB → 503)."""

    def test_escrituracao_status_404_desconhecido(self, api_client):
        import uuid

        resp = api_client.get(f"/api/v1/fiscal/escrituracoes/{uuid.uuid4()}")
        # Sem DB: 503; com DB mas ID inexistente: 404
        assert resp.status_code in (404, 503)

    def test_escrituracao_achados_404_desconhecido(self, api_client):
        import uuid

        resp = api_client.get(f"/api/v1/fiscal/escrituracoes/{uuid.uuid4()}/achados")
        assert resp.status_code in (404, 503)

    def test_escrituracao_apuracao_404_desconhecido(self, api_client):
        import uuid

        resp = api_client.post(f"/api/v1/fiscal/escrituracoes/{uuid.uuid4()}/apuracao")
        assert resp.status_code in (404, 503)

    def test_listar_apuracoes_db_indisponivel(self, api_client):
        resp = api_client.get("/api/v1/fiscal/apuracoes")
        # Sem DB retorna 503; com DB retorna 200 com lista vazia
        assert resp.status_code in (200, 503)

    def test_escrituracao_status_uuid_invalido(self, api_client):
        resp = api_client.get("/api/v1/fiscal/escrituracoes/nao-e-uuid")
        assert resp.status_code == 422

    def test_escrituracao_achados_uuid_invalido(self, api_client):
        resp = api_client.get("/api/v1/fiscal/escrituracoes/nao-e-uuid/achados")
        assert resp.status_code == 422

    def test_apuracao_post_uuid_invalido(self, api_client):
        resp = api_client.post("/api/v1/fiscal/escrituracoes/nao-e-uuid/apuracao")
        assert resp.status_code == 422

    def test_listar_apuracoes_filtro_periodo_invalido(self, api_client):
        resp = api_client.get("/api/v1/fiscal/apuracoes?periodo=invalido")
        assert resp.status_code == 422
