"""Fio de Ouro — Bloco C (S-C.2).

Teste de integração ponta-a-ponta do pipeline fiscal:
  upload → processamento inline → registros canônicos → achados de regra
  → apuração calculada → divergência E110

Executa via TestClient (sem Celery/MinIO/Postgres reais).
Quando banco de dados não disponível, testa o pipeline de processamento
diretamente (parse + regras + apuração) e sinaliza com pytest.mark.
"""

from __future__ import annotations

import asyncio
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


# ─────────────────────────────────────────────────────────────────────────────
# Guard helper — usado apenas por TestGoldenThreadE2E
# ─────────────────────────────────────────────────────────────────────────────


def _assert_postgres_available() -> None:
    """Skip-guard: salta se DATABASE_URL ausente ou Postgres inacessível."""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL não configurado — testes E2E requerem Postgres")

    try:
        from sqlalchemy import text

        from src.db.session import get_async_session

        async def _probe() -> None:
            async with get_async_session() as s:
                await s.execute(text("SELECT 1"))

        try:
            asyncio.run(_probe())
        except RuntimeError as exc:
            if "running" in str(exc).lower():
                return  # loop já ativo — assume DB disponível
            pytest.skip(f"Postgres inacessível (RuntimeError): {exc}")
    except Exception as exc:
        pytest.skip(f"Postgres inacessível: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Parte D: E2E real via HTTP + Postgres (S-C.2.1)
# ─────────────────────────────────────────────────────────────────────────────


class TestGoldenThreadE2E:
    """E2E real com Postgres: upload → inline → status → achados → apuração → listagem.

    Guard: sem DATABASE_URL ou Postgres inacessível → pytest.skip() explícito.
    Força processamento inline removendo CELERY_BROKER_URL do ambiente para
    garantir que o pipeline completa antes da resposta 202.
    """

    @pytest.fixture(autouse=True)
    def _db_and_inline(self):
        _assert_postgres_available()
        saved_broker = os.environ.pop("CELERY_BROKER_URL", None)
        yield
        if saved_broker is not None:
            os.environ["CELERY_BROKER_URL"] = saved_broker

    def _upload(self, client, filename: str, tipo: str = "efd_icms"):
        data = (_FIXTURES / filename).read_bytes()
        return client.post(
            "/api/v1/fiscal/upload",
            files={"file": (filename, io.BytesIO(data), "text/plain")},
            data={"tipo": tipo, "ano": 2025, "mes": 1},
        )

    def test_e2e_icms_upload_status_achados_apuracao_listagem(self, api_client):
        """Upload EFD-ICMS → processado → sem erros → apuração 120 devedor → lista."""
        # Upload
        resp = self._upload(api_client, "efd_icms_devedor.txt", "efd_icms")
        assert resp.status_code == 202
        body = resp.json()
        db_id = body.get("db_id")
        assert db_id is not None, "db_id ausente — escrituração não foi persistida"

        # Status processado com registros
        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}")
        assert r.status_code == 200
        st = r.json()
        assert st["status"] == "processado"
        assert (st["total_registros"] or 0) > 0

        # Achados: nenhum erro no fixture devedor limpo
        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}/achados")
        assert r.status_code == 200
        ac = r.json()
        erros = [a for a in ac["achados"] if a["severidade"] == "erro"]
        assert len(erros) == 0

        # Apuração ICMS: débitos=180, créditos=60, saldo=120, devedor
        r = api_client.post(f"/api/v1/fiscal/escrituracoes/{db_id}/apuracao")
        assert r.status_code == 200
        ap = r.json()
        assert ap["aprovado"] is True
        by_t = {i["tributo"]: i for i in ap["items"]}
        assert "ICMS" in by_t
        icms = by_t["ICMS"]
        assert Decimal(icms["saldo_apurado"]) == Decimal("120")
        assert icms["situacao"] == "devedor"

        # Aparece na listagem
        r = api_client.get("/api/v1/fiscal/apuracoes?tributo=ICMS&periodo=2025-01")
        assert r.status_code == 200
        escr_ids = [a["escrituracao_id"] for a in r.json()]
        assert db_id in escr_ids

    def test_e2e_icms_divergencia_e110_vl_tot_debitos(self, api_client):
        """Upload fixture divergência → apuração gera ERRO em vl_tot_debitos."""
        resp = self._upload(api_client, "efd_icms_divergencia.txt", "efd_icms")
        assert resp.status_code == 202
        db_id = resp.json().get("db_id")
        assert db_id is not None

        r = api_client.post(f"/api/v1/fiscal/escrituracoes/{db_id}/apuracao")
        assert r.status_code == 200
        ap = r.json()
        assert ap["aprovado"] is False
        icms = next((i for i in ap["items"] if i["tributo"] == "ICMS"), None)
        assert icms is not None
        campos_erro = {
            d["campo"] for d in icms["divergencias"] if d["severidade"] == "erro"
        }
        assert "vl_tot_debitos" in campos_erro

    def test_e2e_contrib_pis_cofins_devedor(self, api_client):
        """Upload EFD-Contrib → PIS=99 devedor, COFINS=456 devedor."""
        resp = self._upload(api_client, "efd_contrib_devedor.txt", "efd_contrib")
        assert resp.status_code == 202
        db_id = resp.json().get("db_id")
        assert db_id is not None

        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "processado"

        r = api_client.post(f"/api/v1/fiscal/escrituracoes/{db_id}/apuracao")
        assert r.status_code == 200
        ap = r.json()
        by_t = {i["tributo"]: i for i in ap["items"]}
        assert Decimal(by_t["PIS"]["saldo_apurado"]) == Decimal("99")
        assert by_t["PIS"]["situacao"] == "devedor"
        assert Decimal(by_t["COFINS"]["saldo_apurado"]) == Decimal("456")
        assert by_t["COFINS"]["situacao"] == "devedor"

    def test_e2e_apuracao_idempotente(self, api_client):
        """POST apuracao duas vezes → 200 ambas, sem duplicar registros."""
        resp = self._upload(api_client, "efd_icms_devedor.txt", "efd_icms")
        assert resp.status_code == 202
        db_id = resp.json().get("db_id")
        assert db_id is not None

        r1 = api_client.post(f"/api/v1/fiscal/escrituracoes/{db_id}/apuracao")
        assert r1.status_code == 200
        r2 = api_client.post(f"/api/v1/fiscal/escrituracoes/{db_id}/apuracao")
        assert r2.status_code == 200

        # Exatamente 1 ApuracaoFiscal ICMS para esta escrituração — sem duplicatas
        r = api_client.get(f"/api/v1/fiscal/apuracoes?tributo=ICMS&periodo=2025-01")
        assert r.status_code == 200
        icms_desta = [a for a in r.json() if a["escrituracao_id"] == db_id]
        assert len(icms_desta) == 1

    def test_e2e_apuracao_com_ajuste_e111_e_regime(self, api_client):
        """S-C.4/DT-14: Upload com regime/uf + E111 código real → apuração soma ajuste no saldo.

        Fixture efd_icms_ajuste_e111.txt tem:
          C100 saída vl_icms=100 + E111 SP000207 (natureza 0, outros débitos) vl_aj_apur=50
          E110 declarado saldo=150
        Upload com regime=lucro_real&uf=SP → apuração deve retornar saldo=150 devedor.
        Manual: debitos=100, ajustes_debito=50 (4º char '0' → outros débitos) → saldo=150.
        """
        fixture_path = _FIXTURES / "efd_icms_ajuste_e111.txt"
        with fixture_path.open("rb") as f:
            resp = api_client.post(
                "/api/v1/fiscal/upload",
                files={"file": ("efd_icms_ajuste_e111.txt", f, "text/plain")},
                data={
                    "tipo": "efd_icms",
                    "ano": 2025,
                    "mes": 1,
                    "regime": "lucro_real",
                    "uf": "SP",
                },
            )
        assert resp.status_code == 202
        db_id = resp.json().get("db_id")
        assert db_id is not None

        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "processado"

        r = api_client.post(f"/api/v1/fiscal/escrituracoes/{db_id}/apuracao")
        assert r.status_code == 200
        ap = r.json()
        icms = next((i for i in ap["items"] if i["tributo"] == "ICMS"), None)
        assert icms is not None
        assert Decimal(icms["saldo_apurado"]) == Decimal(
            "150"
        ), f"Saldo esperado 150, got: {icms}"
        assert icms["situacao"] == "devedor"

    def test_e2e_ciclo_detectar_corrigir_reapurar(self, api_client):
        """Ciclo completo S-C.3: upload com ERRO → corrigir via lote → revalidação 0 erros → apuração ok.

        Fixture efd_icms_erro_detectavel.txt tem C100 com vl_icms=-120 (ICMS-002 ERRO).
        Corrige via POST /registros/lote → vl_icms=120,00.
        Resultado final: achados 0 erros, apuracao devedor=120 aprovado.
        """
        # 1. Upload fixture com erro detectável
        resp = self._upload(api_client, "efd_icms_erro_detectavel.txt", "efd_icms")
        assert resp.status_code == 202
        body = resp.json()
        db_id = body.get("db_id")
        assert db_id is not None, "db_id ausente — escrituração não foi persistida"

        # 2. Status processado
        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "processado"

        # 3. Achados: ICMS-002 ERRO presente
        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}/achados")
        assert r.status_code == 200
        achados = r.json()["achados"]
        erros = [a for a in achados if a["severidade"] == "erro"]
        assert len(erros) >= 1, f"Esperado ao menos 1 ERRO, achados: {achados}"
        regra_ids = {a["regra_id"] for a in erros}
        assert (
            "ICMS-002" in regra_ids
        ), f"ICMS-002 deveria ter disparado, ids: {regra_ids}"

        # 4. GET /registros → localizar C100 registro_id
        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}/registros")
        assert r.status_code == 200
        registros = r.json()["registros"]
        c100 = next((reg for reg in registros if reg["tipo_registro"] == "C100"), None)
        assert c100 is not None, "Nenhum registro C100 encontrado"
        c100_id = c100["id"]

        # 5. POST /registros/lote dry_run=True → diff + achados_depois sem erros
        fix_payload = {
            "operacoes": [{"registro_id": c100_id, "campos": {"vl_icms": "120,00"}}],
            "dry_run": True,
        }
        r = api_client.post(
            f"/api/v1/fiscal/escrituracoes/{db_id}/registros/lote",
            json=fix_payload,
        )
        assert r.status_code == 200
        lote = r.json()
        assert lote["dry_run"] is True
        erros_depois = [a for a in lote["achados_depois"] if a["severidade"] == "erro"]
        assert (
            len(erros_depois) == 0
        ), f"dry_run: esperado 0 erros depois, achados: {lote['achados_depois']}"

        # 6. POST /registros/lote dry_run=False → persiste correção
        fix_payload["dry_run"] = False
        r = api_client.post(
            f"/api/v1/fiscal/escrituracoes/{db_id}/registros/lote",
            json=fix_payload,
        )
        assert r.status_code == 200
        assert r.json()["dry_run"] is False

        # 7. GET /achados → 0 erros após correção
        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}/achados")
        assert r.status_code == 200
        achados_pos = r.json()["achados"]
        erros_pos = [a for a in achados_pos if a["severidade"] == "erro"]
        assert (
            len(erros_pos) == 0
        ), f"Esperado 0 erros após correção, achados: {achados_pos}"

        # 8. POST /apuracao → aprovado (E110=120 = vl_icms fixado=120)
        r = api_client.post(f"/api/v1/fiscal/escrituracoes/{db_id}/apuracao")
        assert r.status_code == 200
        ap = r.json()
        assert ap["aprovado"] is True, f"Apuração deveria ser aprovada: {ap}"
        icms = next((i for i in ap["items"] if i["tributo"] == "ICMS"), None)
        assert icms is not None
        assert Decimal(icms["saldo_apurado"]) == Decimal("120")
        assert icms["situacao"] == "devedor"

    def test_e2e_apuracao_icms_st(self, api_client):
        """S-C.6: Upload EFD com ICMS-ST (E200/E210) → apuração retorna item ICMS-ST.

        Fixture efd_icms_st.txt tem:
          C100 saída  vl_icmsst=200 (ind_oper=1)
          C100 entrada vl_icmsst=100 (ind_oper=0)
          E200 SP 2025-01-01..2025-01-31
          E210 vl_retencao_st=200, vl_devol_st=100, vl_icms_recol_st=100
        Manual: debitos_st=200, creditos_st=100, saldo_st=100 (devedor).
        """
        fixture_path = _FIXTURES / "efd_icms_st.txt"
        with fixture_path.open("rb") as f:
            resp = api_client.post(
                "/api/v1/fiscal/upload",
                files={"file": ("efd_icms_st.txt", f, "text/plain")},
                data={
                    "tipo": "efd_icms",
                    "ano": 2025,
                    "mes": 1,
                    "regime": "lucro_real",
                    "uf": "SP",
                },
            )
        assert resp.status_code == 202
        db_id = resp.json().get("db_id")
        assert db_id is not None

        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "processado"

        r = api_client.post(f"/api/v1/fiscal/escrituracoes/{db_id}/apuracao")
        assert r.status_code == 200
        ap = r.json()

        icms_st = next((i for i in ap["items"] if i["tributo"] == "ICMS-ST"), None)
        assert (
            icms_st is not None
        ), f"Item ICMS-ST ausente. Tributos: {[i['tributo'] for i in ap['items']]}"
        assert Decimal(icms_st["saldo_apurado"]) == Decimal(
            "100"
        ), f"Saldo ST esperado 100, got: {icms_st}"
        assert icms_st["situacao"] == "devedor"

    def test_e2e_retificacao(self, api_client):
        """S-D.1: Upload EFD-ICMS → download retificado → 0000.cod_fin='1' + HITL gate.

        Passos:
          1. Upload efd_icms_devedor.txt → db_id
          2. GET /retificado → bytes com 0000.cod_fin='1'
          3. POST /registros/lote com require_approval=True → 200 status=aguardando_aprovacao
          4. Aprovar via HITLQueue → POST /lote/confirmar → status=aplicado
        """
        import uuid as _uuid
        from src.hitl.hitl_queue import get_hitl_queue

        # 1. Upload
        resp = self._upload(api_client, "efd_icms_devedor.txt", "efd_icms")
        assert resp.status_code == 202
        db_id = resp.json().get("db_id")
        assert db_id is not None

        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "processado"

        # 2. GET /retificado → arquivo SPED bytes com cod_fin='1'
        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}/retificado")
        assert r.status_code == 200
        assert "attachment" in r.headers.get("content-disposition", "")
        txt = r.content.decode("utf-8")
        # Linha 0000: |0000|cod_ver|cod_fin|...  → campo [3] = cod_fin
        linha_0000 = txt.split("\r\n")[0]
        partes = linha_0000.split("|")
        assert partes[1] == "0000", f"Primeiro registro deveria ser 0000: {partes}"
        assert partes[3] == "1", f"cod_fin deveria ser '1' (retificação): {partes[3]!r}"

        # 3. POST /registros/lote com require_approval=True
        # Localiza um C100 para editar
        r = api_client.get(f"/api/v1/fiscal/escrituracoes/{db_id}/registros")
        assert r.status_code == 200
        registros = r.json()["registros"]
        c100 = next((reg for reg in registros if reg["tipo_registro"] == "C100"), None)
        assert c100 is not None
        c100_id = c100["id"]

        lote_payload = {
            "operacoes": [{"registro_id": c100_id, "campos": {"vl_frt": "10,00"}}],
            "dry_run": False,
            "require_approval": True,
        }
        r = api_client.post(
            f"/api/v1/fiscal/escrituracoes/{db_id}/registros/lote",
            json=lote_payload,
        )
        assert r.status_code == 200
        lote_resp = r.json()
        assert lote_resp["status"] == "aguardando_aprovacao"
        hitl_id = lote_resp.get("hitl_request_id")
        assert hitl_id is not None

        # 4. Aprovar HITL e confirmar
        hitl_queue = get_hitl_queue()
        ok = hitl_queue.record_decision(
            hitl_id,
            approved=True,
            feedback="aprovado pelo teste E2E",
            operator_id="test_operator",
        )
        assert ok is True

        r = api_client.post(
            f"/api/v1/fiscal/escrituracoes/{db_id}/lote/confirmar",
            json={"hitl_request_id": hitl_id},
        )
        assert r.status_code == 200
        confirmar = r.json()
        assert confirmar["status"] == "aplicado"
        assert confirmar["operacoes_aplicadas"] == 1
