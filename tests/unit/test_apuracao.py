"""Testes unitários do motor de apuração ICMS/PIS/COFINS (S-C.2 Parte B).

Cobre os 5 cenários oficiais por tributo exigidos pelo DoD do S-C.2.
Cada cenário tem os valores calculados à mão nos comentários abaixo.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.fiscal.apuracao import (
    ApuracaoEngine,
    DivergenciaApuracao,
    ItemApuracao,
    ResultadoApuracao,
    _to_dec,
    get_apuracao_engine,
)
from src.fiscal.parser.base import SpedRecord
from src.fiscal.parser.registry import get_parser
from src.fiscal.reconciliation import Severidade

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "fiscal"


def _parse_fixture(filename: str, tipo: str) -> list:
    data = (_FIXTURES / filename).read_bytes()
    parser = get_parser(tipo)
    result = parser.parse(data, encoding="utf-8")
    return result.records


def _make_c100(ind_oper: str, vl_icms: str, cod_sit: str = "00") -> SpedRecord:
    return SpedRecord(
        bloco="C",
        tipo_registro="C100",
        campos={"ind_oper": ind_oper, "vl_icms": vl_icms, "cod_sit": cod_sit},
        numero_linha=1,
    )


def _make_e110(**kwargs) -> SpedRecord:
    return SpedRecord(
        bloco="E",
        tipo_registro="E110",
        campos=kwargs,
        numero_linha=100,
    )


def _make_m210(vl_cont_apr: str) -> SpedRecord:
    return SpedRecord(
        bloco="M",
        tipo_registro="M210",
        campos={"vl_cont_apr": vl_cont_apr},
        numero_linha=1,
    )


def _make_m200(**kwargs) -> SpedRecord:
    return SpedRecord(
        bloco="M",
        tipo_registro="M200",
        campos=kwargs,
        numero_linha=100,
    )


def _make_m610(vl_cont_apr: str) -> SpedRecord:
    return SpedRecord(
        bloco="M",
        tipo_registro="M610",
        campos={"vl_cont_apr": vl_cont_apr},
        numero_linha=1,
    )


def _make_m600(**kwargs) -> SpedRecord:
    return SpedRecord(
        bloco="M",
        tipo_registro="M600",
        campos=kwargs,
        numero_linha=100,
    )


# ─────────────────────────────────────────────────────────────────────────────
# _to_dec helper
# ─────────────────────────────────────────────────────────────────────────────


class TestToDecHelper:
    def test_comma_decimal(self):
        assert _to_dec("1.234,56") == Decimal("1234.56")

    def test_dot_decimal(self):
        assert _to_dec("1234.56") == Decimal("1234.56")

    def test_empty(self):
        assert _to_dec("") == Decimal("0")

    def test_none(self):
        assert _to_dec(None) == Decimal("0")

    def test_zero_string(self):
        assert _to_dec("0,00") == Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
# Apuração ICMS — 5 cenários oficiais
# ─────────────────────────────────────────────────────────────────────────────


class TestApuracaoICMS:
    """Cenários ICMS documentados conforme DoD S-C.2."""

    def setup_method(self):
        self.engine = get_apuracao_engine()

    # Cenário 1: saldo devedor
    # Conta: débitos=180 − créditos=60 − saldo_ant=0 = 120 (devedor)
    def test_icms_devedor_from_fixture(self):
        records = _parse_fixture("efd_icms_devedor.txt", "efd_icms")
        item = self.engine.calcular_icms(records)
        assert item.tributo == "ICMS"
        assert item.total_debitos == Decimal("180")
        assert item.total_creditos == Decimal("60")
        assert item.saldo_apurado == Decimal("120")
        assert item.situacao == "devedor"
        assert len(item.divergencias) == 0

    # Cenário 2: saldo credor
    # Conta: débitos=60 − créditos=240 − saldo_ant=0 = −180 (credor)
    def test_icms_credor_from_fixture(self):
        records = _parse_fixture("efd_icms_credor.txt", "efd_icms")
        item = self.engine.calcular_icms(records)
        assert item.situacao == "credor"
        assert item.saldo_apurado == Decimal("-180")
        assert len(item.divergencias) == 0

    # Cenário 3: saldo credor anterior sendo transportado
    # Conta: débitos=100 − créditos=0 − saldo_ant=50 = 50 (devedor)
    # E110 declara sld_credor_ant=50 e sld_apurado=50 → sem divergência
    def test_icms_saldo_anterior_from_fixture(self):
        records = _parse_fixture("efd_icms_saldo_anterior.txt", "efd_icms")
        item = self.engine.calcular_icms(records, saldo_credor_anterior=Decimal("50"))
        assert item.saldo_credor_anterior == Decimal("50")
        assert item.saldo_apurado == Decimal("50")
        assert item.situacao == "devedor"
        assert len(item.divergencias) == 0

    # Cenário 4: divergência E110 × computado
    # C100s computam débitos=120, E110 declara 300 → erro de 180
    def test_icms_divergencia_e110_from_fixture(self):
        records = _parse_fixture("efd_icms_divergencia.txt", "efd_icms")
        item = self.engine.calcular_icms(records)
        assert len(item.divergencias) >= 1
        divs_por_campo = {d.campo: d for d in item.divergencias}
        assert "vl_tot_debitos" in divs_por_campo
        div = divs_por_campo["vl_tot_debitos"]
        assert div.severidade == Severidade.ERRO
        assert Decimal(div.valor_computado) == Decimal("120")
        assert Decimal(div.valor_declarado) == Decimal("300")

    # Cenário 5: saldo equilibrado (débitos = créditos)
    # Conta: débitos=100 − créditos=100 = 0 (equilibrado)
    def test_icms_equilibrado_from_fixture(self):
        records = _parse_fixture("efd_icms_equilibrado.txt", "efd_icms")
        item = self.engine.calcular_icms(records)
        assert item.situacao == "equilibrado"
        assert item.saldo_apurado == Decimal("0")
        assert len(item.divergencias) == 0

    def test_icms_documentos_cancelados_ignorados(self):
        records = [
            _make_c100("1", "100,00", cod_sit="06"),  # cancelado → ignorar
            _make_c100("1", "50,00", cod_sit="00"),  # válido
        ]
        item = self.engine.calcular_icms(records)
        assert item.total_debitos == Decimal("50")

    def test_icms_sem_e110(self):
        records = [_make_c100("1", "200,00"), _make_c100("0", "80,00")]
        item = self.engine.calcular_icms(records)
        assert item.total_debitos == Decimal("200")
        assert item.total_creditos == Decimal("80")
        assert item.saldo_apurado == Decimal("120")
        assert len(item.divergencias) == 0  # sem E110, sem confronto

    def test_icms_saldo_credor_injeto_zerado(self):
        records = [_make_c100("1", "100,00")]
        item = self.engine.calcular_icms(records, Decimal("0"))
        assert item.saldo_credor_anterior == Decimal("0")
        assert item.saldo_apurado == Decimal("100")


# ─────────────────────────────────────────────────────────────────────────────
# Apuração PIS — 5 cenários oficiais
# ─────────────────────────────────────────────────────────────────────────────


class TestApuracaoPIS:
    """Cenários PIS documentados conforme DoD S-C.2."""

    def setup_method(self):
        self.engine = get_apuracao_engine()

    # Cenário 1: devedor simples (PIS 1,65% s/ 6.000 = 99,00)
    def test_pis_devedor_from_fixture(self):
        records = _parse_fixture("efd_contrib_devedor.txt", "efd_contrib")
        item = self.engine.calcular_pis(records)
        assert item.tributo == "PIS"
        assert item.total_debitos == Decimal("99")
        assert item.saldo_apurado == Decimal("99")
        assert item.situacao == "devedor"
        assert len(item.divergencias) == 0

    # Cenário 2: múltiplos M210 somando 99,00 (33+16,50+49,50)
    def test_pis_multiplos_m210_from_fixture(self):
        records = _parse_fixture("efd_contrib_multiplos.txt", "efd_contrib")
        item = self.engine.calcular_pis(records)
        assert item.total_debitos == Decimal("99")
        assert item.detalhes["total_m210_linhas"] == 3
        assert len(item.divergencias) == 0

    # Cenário 3: divergência M200 (M210=99, M200 declara 200)
    def test_pis_divergencia_m200_from_fixture(self):
        records = _parse_fixture("efd_contrib_divergencia_pis.txt", "efd_contrib")
        item = self.engine.calcular_pis(records)
        assert len(item.divergencias) == 1
        div = item.divergencias[0]
        assert div.campo == "vl_tot_cont_nc_per"
        assert div.severidade == Severidade.ERRO
        assert Decimal(div.valor_computado) == Decimal("99")
        assert Decimal(div.valor_declarado) == Decimal("200")

    # Cenário 4: equilibrado (sem M210, M200=0)
    def test_pis_equilibrado_from_fixture(self):
        records = _parse_fixture("efd_contrib_equilibrado.txt", "efd_contrib")
        item = self.engine.calcular_pis(records)
        assert item.situacao == "equilibrado"
        assert item.saldo_apurado == Decimal("0")
        assert len(item.divergencias) == 0

    # Cenário 5: soma de M210 direto (sem fixture)
    # Conta: 50,00 + 30,00 + 20,00 = 100,00 (devedor)
    def test_pis_soma_m210_inline(self):
        records = [
            _make_m210("50,00"),
            _make_m210("30,00"),
            _make_m210("20,00"),
            _make_m200(vl_tot_cont_nc_per="100,00"),
        ]
        item = self.engine.calcular_pis(records)
        assert item.total_debitos == Decimal("100")
        assert item.situacao == "devedor"
        assert len(item.divergencias) == 0

    def test_pis_sem_m200(self):
        records = [_make_m210("100,00")]
        item = self.engine.calcular_pis(records)
        assert item.total_debitos == Decimal("100")
        assert len(item.divergencias) == 0  # sem M200, sem confronto

    def test_pis_m200_dentro_tolerancia(self):
        # Diferença de 0,50 ≤ tolerância 1,00 → sem divergência
        records = [
            _make_m210("100,00"),
            _make_m200(vl_tot_cont_nc_per="100,50"),
        ]
        item = self.engine.calcular_pis(records)
        assert len(item.divergencias) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Apuração COFINS — 5 cenários oficiais
# ─────────────────────────────────────────────────────────────────────────────


class TestApuracaoCOFINS:
    """Cenários COFINS documentados conforme DoD S-C.2."""

    def setup_method(self):
        self.engine = get_apuracao_engine()

    # Cenário 1: devedor (COFINS 7,6% s/ 6.000 = 456,00)
    def test_cofins_devedor_from_fixture(self):
        records = _parse_fixture("efd_contrib_devedor.txt", "efd_contrib")
        item = self.engine.calcular_cofins(records)
        assert item.tributo == "COFINS"
        assert item.total_debitos == Decimal("456")
        assert item.situacao == "devedor"
        assert len(item.divergencias) == 0

    # Cenário 2: múltiplos M610 (152+76+228=456)
    def test_cofins_multiplos_m610_from_fixture(self):
        records = _parse_fixture("efd_contrib_multiplos.txt", "efd_contrib")
        item = self.engine.calcular_cofins(records)
        assert item.total_debitos == Decimal("456")
        assert item.detalhes["total_m610_linhas"] == 3
        assert len(item.divergencias) == 0

    # Cenário 3: divergência M600 (M610=456, M600 declara 900)
    def test_cofins_divergencia_m600_from_fixture(self):
        records = _parse_fixture("efd_contrib_divergencia_cofins.txt", "efd_contrib")
        item = self.engine.calcular_cofins(records)
        assert len(item.divergencias) == 1
        div = item.divergencias[0]
        assert div.campo == "vl_tot_cont_nc_per"
        assert div.severidade == Severidade.ERRO
        assert Decimal(div.valor_computado) == Decimal("456")
        assert Decimal(div.valor_declarado) == Decimal("900")

    # Cenário 4: equilibrado (sem M610, M600=0)
    def test_cofins_equilibrado_from_fixture(self):
        records = _parse_fixture("efd_contrib_equilibrado.txt", "efd_contrib")
        item = self.engine.calcular_cofins(records)
        assert item.situacao == "equilibrado"
        assert len(item.divergencias) == 0

    # Cenário 5: soma M610 direto
    def test_cofins_soma_m610_inline(self):
        records = [
            _make_m610("200,00"),
            _make_m610("256,00"),
            _make_m600(vl_tot_cont_nc_per="456,00"),
        ]
        item = self.engine.calcular_cofins(records)
        assert item.total_debitos == Decimal("456")
        assert len(item.divergencias) == 0

    def test_cofins_sem_m600(self):
        records = [_make_m610("456,00")]
        item = self.engine.calcular_cofins(records)
        assert item.total_debitos == Decimal("456")
        assert len(item.divergencias) == 0

    def test_cofins_m600_dentro_tolerancia(self):
        records = [
            _make_m610("456,00"),
            _make_m600(vl_tot_cont_nc_per="456,80"),
        ]
        item = self.engine.calcular_cofins(records)
        assert len(item.divergencias) == 0


# ─────────────────────────────────────────────────────────────────────────────
# ApuracaoEngine.calcular — orquestração
# ─────────────────────────────────────────────────────────────────────────────


class TestApuracaoEngineCalcular:
    def setup_method(self):
        self.engine = get_apuracao_engine()

    def test_calcular_efd_icms_retorna_item_icms(self):
        records = _parse_fixture("efd_icms_devedor.txt", "efd_icms")
        resultado = self.engine.calcular(records, tipo="efd_icms")
        assert len(resultado.items) == 1
        assert resultado.items[0].tributo == "ICMS"

    def test_calcular_efd_contrib_retorna_pis_e_cofins(self):
        records = _parse_fixture("efd_contrib_devedor.txt", "efd_contrib")
        resultado = self.engine.calcular(records, tipo="efd_contrib")
        assert len(resultado.items) == 2
        tributos = {i.tributo for i in resultado.items}
        assert tributos == {"PIS", "COFINS"}

    def test_calcular_aprovado_sem_divergencias(self):
        records = _parse_fixture("efd_icms_devedor.txt", "efd_icms")
        resultado = self.engine.calcular(records, tipo="efd_icms")
        assert resultado.aprovado is True

    def test_calcular_reprovado_com_divergencias(self):
        records = _parse_fixture("efd_icms_divergencia.txt", "efd_icms")
        resultado = self.engine.calcular(records, tipo="efd_icms")
        assert resultado.aprovado is False

    def test_resultado_to_dict(self):
        records = _parse_fixture("efd_icms_devedor.txt", "efd_icms")
        resultado = self.engine.calcular(records, tipo="efd_icms")
        d = resultado.to_dict()
        assert "aprovado" in d
        assert "items" in d
        assert "resumo" in d
        item = d["items"][0]
        assert "tributo" in item
        assert "saldo_apurado" in item
        assert "divergencias" in item

    def test_get_apuracao_engine_factory(self):
        engine = get_apuracao_engine()
        assert isinstance(engine, ApuracaoEngine)

    def test_divergencia_to_dict(self):
        div = DivergenciaApuracao(
            campo="vl_tot_debitos",
            valor_computado="120",
            valor_declarado="300",
            diferenca="180",
            severidade=Severidade.ERRO,
        )
        d = div.to_dict()
        assert d["severidade"] == "erro"
        assert d["campo"] == "vl_tot_debitos"
