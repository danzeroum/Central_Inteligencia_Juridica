"""Testes unitários — S-F.2: Gerador PER/DCOMP (Factory + Validator)."""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

import base64  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Modelos
# ─────────────────────────────────────────────────────────────────────────────


class TestModelos:
    def test_tipo_ficha_valores(self):
        from src.fiscal.per_dcomp.models import TipoFicha

        assert TipoFicha.PER_RESTITUICAO.value == "per_restituicao"
        assert TipoFicha.DCOMP_CREDITO_APURACAO.value == "dcomp_credito_apuracao"

    def test_codigo_receita_pis(self):
        from src.fiscal.per_dcomp.models import CODIGO_RECEITA, TipoTributo

        assert CODIGO_RECEITA[TipoTributo.PIS] == "8109"
        assert CODIGO_RECEITA[TipoTributo.COFINS] == "7987"

    def test_ficha_to_dict_decimal_como_str(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory

        ficha = PERDCOMPFactory.create_per_restituicao(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="Empresa Teste",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("1500.00"),
        )
        d = ficha.to_dict()
        assert d["credito"]["valor_credito"] == "1500.00"
        assert d["tipo"] == "per_restituicao"
        assert d["status"] == "gerada"

    def test_credito_codigo_receita_auto_preenchido(self):
        from src.fiscal.per_dcomp.models import CreditoTributario, TipoTributo

        c = CreditoTributario(
            tributo=TipoTributo.PIS,
            periodo_apuracao="2026-01",
            valor_credito=Decimal("100"),
        )
        assert c.codigo_receita == "8109"

    def test_debito_codigo_receita_auto_preenchido(self):
        from src.fiscal.per_dcomp.models import DebitoCompensacao, TipoTributo

        d = DebitoCompensacao(
            tributo=TipoTributo.COFINS,
            periodo_apuracao="2026-02",
            valor_debito=Decimal("200"),
        )
        assert d.codigo_receita == "7987"


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


class TestPERDCOMPFactory:
    def _factory(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory

        return PERDCOMPFactory

    def test_create_per_restituicao(self):
        F = self._factory()
        ficha = F.create_per_restituicao(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="Empresa SA",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("2000.00"),
        )
        from src.fiscal.per_dcomp.models import StatusFicha, TipoFicha

        assert ficha.tipo == TipoFicha.PER_RESTITUICAO
        assert ficha.credito.valor_credito == Decimal("2000.00")
        assert ficha.status == StatusFicha.GERADA
        assert ficha.debitos == []
        assert ficha.ficha_id

    def test_create_dcomp(self):
        from src.fiscal.per_dcomp.models import (
            DebitoCompensacao,
            TipoFicha,
            TipoTributo,
        )

        F = self._factory()
        debitos = [
            DebitoCompensacao(
                tributo=TipoTributo.PIS,
                periodo_apuracao="2026-02",
                valor_debito=Decimal("300"),
            )
        ]
        ficha = F.create_dcomp(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="Empresa SA",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("1500"),
            debitos=debitos,
        )
        assert ficha.tipo == TipoFicha.DCOMP_CREDITO_APURACAO
        assert len(ficha.debitos) == 1
        assert ficha.debitos[0].valor_debito == Decimal("300")

    def test_create_per_ressarcimento(self):
        from src.fiscal.per_dcomp.models import TipoFicha

        F = self._factory()
        ficha = F.create_per_ressarcimento(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="Exportadora Ltda",
            tributo_str="COFINS",
            periodo_apuracao="2025-12",
            valor_credito=Decimal("50000"),
        )
        assert ficha.tipo == TipoFicha.PER_RESSARCIMENTO
        assert ficha.credito.valor_credito == Decimal("50000")

    def test_create_from_apuracao_credor_sem_debitos_gera_per(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.models import TipoFicha

        apuracao = {
            "tributo": "PIS",
            "periodo_competencia": "2026-01",
            "saldo_apurado": "1200.00",
            "situacao": "credor",
        }
        ficha = PERDCOMPFactory.create_from_apuracao(
            apuracao=apuracao,
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="Empresa X",
        )
        assert ficha.tipo == TipoFicha.PER_RESTITUICAO
        assert ficha.credito.valor_credito == Decimal("1200.00")

    def test_create_from_apuracao_com_debitos_gera_dcomp(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.models import (
            DebitoCompensacao,
            TipoFicha,
            TipoTributo,
        )

        apuracao = {
            "tributo": "COFINS",
            "periodo_competencia": "2026-01",
            "saldo_apurado": "800.00",
            "situacao": "credor",
        }
        debitos = [
            DebitoCompensacao(
                tributo=TipoTributo.COFINS,
                periodo_apuracao="2026-02",
                valor_debito=Decimal("400"),
            )
        ]
        ficha = PERDCOMPFactory.create_from_apuracao(
            apuracao=apuracao,
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="Empresa Y",
            debitos=debitos,
        )
        assert ficha.tipo == TipoFicha.DCOMP_CREDITO_APURACAO

    def test_ficha_tem_correlation_id(self):
        F = self._factory()
        ficha = F.create_per_restituicao(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="X",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("100"),
        )
        assert ficha.correlation_id is not None

    def test_ficha_ids_unicos(self):
        F = self._factory()

        def make():
            return F.create_per_restituicao(
                cnpj_masked="**.***.***/****-**",
                nome_empresarial="X",
                tributo_str="PIS",
                periodo_apuracao="2026-01",
                valor_credito=Decimal("100"),
            )

        ids = {make().ficha_id for _ in range(20)}
        assert len(ids) == 20


# ─────────────────────────────────────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────────────────────────────────────


class TestPERDCOMPValidator:
    def _make_per(self, valor="1500.00", periodo="2026-01", tributo_str="PIS"):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory

        return PERDCOMPFactory.create_per_restituicao(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="Empresa Teste",
            tributo_str=tributo_str,
            periodo_apuracao=periodo,
            valor_credito=Decimal(valor),
        )

    def test_per_valido(self):
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        ficha = self._make_per()
        ficha = PERDCOMPValidator.validate(ficha)
        from src.fiscal.per_dcomp.models import StatusFicha

        assert ficha.status == StatusFicha.VALIDADA
        assert ficha.erros_validacao == []

    def test_valor_zero_invalido(self):
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        ficha = self._make_per(valor="0")
        erros = PERDCOMPValidator.validate_semantica(ficha)
        assert any("maior que zero" in e for e in erros)

    def test_periodo_futuro_invalido(self):
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        ficha = self._make_per(periodo="2099-12")
        erros = PERDCOMPValidator.validate_semantica(ficha)
        assert any("futuro" in e for e in erros)

    def test_periodo_formato_invalido(self):
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        ficha = self._make_per(periodo="01/2026")
        erros = PERDCOMPValidator.validate_sintatica(ficha)
        assert any("AAAA-MM" in e for e in erros)

    def test_tributo_inelegivel_para_tipo_efd(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.models import TipoTributo
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        ficha = PERDCOMPFactory.create_per_restituicao(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="X",
            tributo_str="IRPJ",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("5000"),
        )
        erros = PERDCOMPValidator.validate_semantica(ficha)
        assert any("PIS ou COFINS" in e for e in erros)

    def test_dcomp_sem_debitos_invalido(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.models import TipoFicha
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        ficha = PERDCOMPFactory.create_per_restituicao(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="X",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("1000"),
        )
        ficha.tipo = TipoFicha.DCOMP_CREDITO_APURACAO  # forçar DCOMP sem débitos
        erros = PERDCOMPValidator.validate_semantica(ficha)
        assert any("débito" in e.lower() for e in erros)

    def test_dcomp_debitos_superam_credito(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.models import DebitoCompensacao, TipoTributo
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        debitos = [
            DebitoCompensacao(
                tributo=TipoTributo.PIS,
                periodo_apuracao="2026-02",
                valor_debito=Decimal("2000"),
            )
        ]
        ficha = PERDCOMPFactory.create_dcomp(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="X",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("500"),  # crédito < débito
            debitos=debitos,
        )
        erros = PERDCOMPValidator.validate_semantica(ficha)
        assert any("supera" in e for e in erros)

    def test_dcomp_saldo_remanescente_gera_aviso(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.models import DebitoCompensacao, TipoTributo
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        debitos = [
            DebitoCompensacao(
                tributo=TipoTributo.PIS,
                periodo_apuracao="2026-02",
                valor_debito=Decimal("300"),
            )
        ]
        ficha = PERDCOMPFactory.create_dcomp(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="X",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("1000"),  # 700 remanescente
            debitos=debitos,
        )
        _, avisos = PERDCOMPValidator._validate_semantica_com_avisos(ficha)
        assert any("remanescente" in a for a in avisos)

    def test_periodo_prescrito_mais_5_anos(self):
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        ficha = self._make_per(periodo="2019-01")
        erros = PERDCOMPValidator.validate_semantica(ficha)
        assert any("prescrito" in e for e in erros)

    def test_cnpj_vazio_sintax_erro(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        ficha = PERDCOMPFactory.create_per_restituicao(
            cnpj_masked="",
            nome_empresarial="X",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("100"),
        )
        erros = PERDCOMPValidator.validate_sintatica(ficha)
        assert any("cnpj_masked" in e for e in erros)

    def test_validate_marca_status_invalido(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.models import StatusFicha
        from src.fiscal.per_dcomp.validator import PERDCOMPValidator

        ficha = PERDCOMPFactory.create_per_restituicao(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="X",
            tributo_str="PIS",
            periodo_apuracao="2099-01",  # futuro
            valor_credito=Decimal("100"),
        )
        ficha = PERDCOMPValidator.validate(ficha)
        assert ficha.status == StatusFicha.INVALIDA
        assert len(ficha.erros_validacao) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Serializer XML
# ─────────────────────────────────────────────────────────────────────────────


class TestSerializer:
    def test_xml_contem_ficha_id(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.serializer import to_xml

        ficha = PERDCOMPFactory.create_per_restituicao(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="Empresa SA",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("1500"),
        )
        xml = to_xml(ficha)
        assert ficha.ficha_id in xml
        assert "PIS" in xml
        assert "1500.00" in xml

    def test_xml_dcomp_contem_debitos(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.models import DebitoCompensacao, TipoTributo
        from src.fiscal.per_dcomp.serializer import to_xml

        debitos = [
            DebitoCompensacao(
                tributo=TipoTributo.PIS,
                periodo_apuracao="2026-02",
                valor_debito=Decimal("300"),
            )
        ]
        ficha = PERDCOMPFactory.create_dcomp(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="X",
            tributo_str="PIS",
            periodo_apuracao="2026-01",
            valor_credito=Decimal("1000"),
            debitos=debitos,
        )
        xml = to_xml(ficha)
        assert "debitoCompensacao" in xml
        assert "300.00" in xml

    def test_xml_b64_decodificavel(self):
        from src.fiscal.per_dcomp.factory import PERDCOMPFactory
        from src.fiscal.per_dcomp.serializer import to_xml, to_xml_b64

        ficha = PERDCOMPFactory.create_per_restituicao(
            cnpj_masked="**.***.***/****-**",
            nome_empresarial="X",
            tributo_str="COFINS",
            periodo_apuracao="2026-03",
            valor_credito=Decimal("999.99"),
        )
        b64 = to_xml_b64(ficha)
        decoded = base64.b64decode(b64).decode("utf-8")
        assert decoded == to_xml(ficha)

    def test_periodo_convertido_mmaaaa(self):
        from src.fiscal.per_dcomp.serializer import _periodo_para_xml

        assert _periodo_para_xml("2026-01") == "012026"
        assert _periodo_para_xml("2025-12") == "122025"


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Endpoints
# ─────────────────────────────────────────────────────────────────────────────


def _make_client():
    from src.api.main import app

    return TestClient(app, raise_server_exceptions=False)


class TestPERDCOMPEndpoints:
    def setup_method(self):
        from src.api.auth import AuthManager

        AuthManager.configure(required=False)
        self.client = _make_client()

    def test_tipos_200(self):
        resp = self.client.get("/api/v1/fiscal/per-dcomp/tipos")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        tipos = [t["tipo"] for t in data]
        assert "per_restituicao" in tipos
        assert "dcomp_credito_apuracao" in tipos

    def test_gerar_per_restituicao_201(self):
        resp = self.client.post(
            "/api/v1/fiscal/per-dcomp/gerar",
            json={
                "cnpj_masked": "**.***.***/****-**",
                "nome_empresarial": "Empresa SA",
                "tributo": "PIS",
                "periodo_apuracao": "2026-01",
                "valor_credito": "1500.00",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tipo"] == "per_restituicao"
        assert data["status"] == "validada"
        assert data["xml_b64"]
        assert data["erros_validacao"] == []

    def test_gerar_dcomp_201(self):
        resp = self.client.post(
            "/api/v1/fiscal/per-dcomp/gerar",
            json={
                "cnpj_masked": "**.***.***/****-**",
                "nome_empresarial": "Empresa SA",
                "tributo": "COFINS",
                "periodo_apuracao": "2026-02",
                "valor_credito": "2000.00",
                "tipo_ficha": "dcomp_credito_apuracao",
                "debitos": [
                    {
                        "tributo": "COFINS",
                        "periodo_apuracao": "2026-03",
                        "valor_debito": "500.00",
                    }
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tipo"] == "dcomp_credito_apuracao"
        assert len(data["debitos"]) == 1

    def test_gerar_tributo_invalido_422(self):
        resp = self.client.post(
            "/api/v1/fiscal/per-dcomp/gerar",
            json={
                "cnpj_masked": "**.***.***/****-**",
                "nome_empresarial": "X",
                "tributo": "INVALIDO",
                "periodo_apuracao": "2026-01",
                "valor_credito": "100.00",
            },
        )
        assert resp.status_code == 422

    def test_gerar_de_apuracao_201(self):
        resp = self.client.post(
            "/api/v1/fiscal/per-dcomp/gerar-de-apuracao",
            json={
                "apuracao": {
                    "tributo": "PIS",
                    "periodo_competencia": "2026-01",
                    "saldo_apurado": "3000.00",
                    "situacao": "credor",
                },
                "cnpj_masked": "**.***.***/****-**",
                "nome_empresarial": "Exportadora SA",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tipo"] == "per_restituicao"
        assert data["credito"]["valor_credito"] == "3000.00"

    def test_validar_valido_200(self):
        resp = self.client.post(
            "/api/v1/fiscal/per-dcomp/validar",
            json={
                "cnpj_masked": "**.***.***/****-**",
                "nome_empresarial": "Empresa",
                "tributo": "PIS",
                "periodo_apuracao": "2026-01",
                "valor_credito": "1000.00",
                "tipo_ficha": "per_restituicao",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valido"] is True
        assert data["erros_sintaticos"] == []
        assert data["erros_semanticos"] == []

    def test_validar_invalido_periodo_futuro(self):
        resp = self.client.post(
            "/api/v1/fiscal/per-dcomp/validar",
            json={
                "cnpj_masked": "**.***.***/****-**",
                "nome_empresarial": "Empresa",
                "tributo": "PIS",
                "periodo_apuracao": "2099-01",
                "valor_credito": "100.00",
                "tipo_ficha": "per_restituicao",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valido"] is False
        assert len(data["erros_semanticos"]) > 0

    def test_gerar_per_invalido_retorna_status_invalida(self):
        """Ficha gerada com período futuro ainda retorna 201 mas com status=invalida."""
        resp = self.client.post(
            "/api/v1/fiscal/per-dcomp/gerar",
            json={
                "cnpj_masked": "**.***.***/****-**",
                "nome_empresarial": "X",
                "tributo": "PIS",
                "periodo_apuracao": "2099-06",
                "valor_credito": "500.00",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "invalida"
        assert len(data["erros_validacao"]) > 0
