"""Testes unitários apuração extendida — S-C.4.

Cobre: E111/E112/E113 ajustes, M100/M500 regime cumulativo, M400/M405/M800 créditos.
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

os.environ.setdefault("ENVIRONMENT", "test")

from src.fiscal.apuracao import ApuracaoEngine, get_apuracao_engine
from src.fiscal.parser.base import SpedRecord
from src.fiscal.reconciliation import Severidade


def _rec(tipo: str, **campos) -> SpedRecord:
    return SpedRecord(
        bloco=tipo[0],
        tipo_registro=tipo,
        campos=campos,
        numero_linha=1,
    )


def _e110(**kwargs) -> SpedRecord:
    defaults = {
        "vl_tot_debitos": "0,00",
        "vl_aj_debitos": "0,00",
        "vl_tot_aj_debitos": "0,00",
        "vl_estornos_cred": "0,00",
        "vl_tot_creditos": "0,00",
        "vl_aj_creditos": "0,00",
        "vl_tot_aj_creditos": "0,00",
        "vl_estornos_deb": "0,00",
        "vl_sld_credor_ant": "0,00",
        "vl_sld_apurado": "0,00",
        "vl_tot_ded": "0,00",
        "vl_icms_recolher": "0,00",
        "vl_sld_credor_transp": "0,00",
        "deb_esp": "0,00",
    }
    defaults.update(kwargs)
    return _rec("E110", **defaults)


# ─────────────────────────────────────────────────────────────────────────────
# E111 / E112 / E113 ajustes
# ─────────────────────────────────────────────────────────────────────────────


def test_e111_ajuste_debito():
    """E111 com 3º char='1' → débito → soma ao saldo devedor.

    Manual: debitos=100, creditos=0, ajustes_debito=50, ajustes_credito=0
    saldo = 100 - 0 + 50 - 0 - 0 = 150 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
        _e110(vl_tot_debitos="100,00", vl_sld_apurado="150,00"),
        _rec("E111", cod_aj_apur="MG1XXXXX", vl_aj_apur="50,00"),
    ]
    item = engine.calcular_icms(records)
    assert item.ajustes_debito == Decimal("50")
    assert item.ajustes_credito == Decimal("0")
    assert item.saldo_apurado == Decimal("150")
    assert item.situacao == "devedor"


def test_e111_ajuste_credito():
    """E111 com 3º char='2' → crédito → reduz saldo devedor.

    Manual: debitos=200, creditos=0, ajustes_debito=0, ajustes_credito=50
    saldo = 200 - 0 + 0 - 50 - 0 = 150 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="200,00"),
        _e110(vl_tot_debitos="200,00", vl_sld_apurado="150,00"),
        _rec("E111", cod_aj_apur="MG2XXXXX", vl_aj_apur="50,00"),
    ]
    item = engine.calcular_icms(records)
    assert item.ajustes_credito == Decimal("50")
    assert item.ajustes_debito == Decimal("0")
    assert item.saldo_apurado == Decimal("150")
    assert item.situacao == "devedor"


def test_e111_multiplos():
    """Múltiplos E111 (débito e crédito) → efeito líquido correto.

    Manual: debitos=100, creditos=0, ajustes_debito=30+20=50, ajustes_credito=10
    saldo = 100 - 0 + 50 - 10 - 0 = 140 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
        _e110(vl_tot_debitos="100,00", vl_sld_apurado="140,00"),
        _rec("E111", cod_aj_apur="SP1AAAAA", vl_aj_apur="30,00"),
        _rec("E111", cod_aj_apur="SP1BBBBB", vl_aj_apur="20,00"),
        _rec("E111", cod_aj_apur="SP2CCCCC", vl_aj_apur="10,00"),
    ]
    item = engine.calcular_icms(records)
    assert item.ajustes_debito == Decimal("50")
    assert item.ajustes_credito == Decimal("10")
    assert item.saldo_apurado == Decimal("140")


def test_e111_codigo_invalido():
    """E111 com 3º char ≠ '1' ou '2' → AVISO divergência, não soma a ajustes."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
        _e110(vl_tot_debitos="100,00", vl_sld_apurado="100,00"),
        _rec("E111", cod_aj_apur="MG9XXXXX", vl_aj_apur="50,00"),
    ]
    item = engine.calcular_icms(records)
    avisos = [d for d in item.divergencias if d.severidade == Severidade.AVISO]
    cod_avisos = {d.campo for d in avisos}
    assert "E111.cod_aj_apur" in cod_avisos
    assert item.ajustes_debito == Decimal("0")
    assert item.ajustes_credito == Decimal("0")


def test_e111_orfao_sem_e110():
    """E111 sem E110 → ERRO divergência 'E111 sem E110 correspondente'."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
        _rec("E111", cod_aj_apur="MG1XXXXX", vl_aj_apur="50,00"),
    ]
    item = engine.calcular_icms(records)
    erros = [d for d in item.divergencias if d.severidade == Severidade.ERRO]
    assert any(d.campo == "E111" for d in erros)
    assert any("E111 sem E110" in d.valor_computado for d in erros)


def test_e111_zero_sem_e111():
    """Sem E111 → ajustes_debito=0, ajustes_credito=0."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
        _e110(vl_tot_debitos="100,00", vl_sld_apurado="100,00"),
    ]
    item = engine.calcular_icms(records)
    assert item.ajustes_debito == Decimal("0")
    assert item.ajustes_credito == Decimal("0")
    assert item.detalhes["e111_count"] == 0
    assert item.detalhes["e112_count"] == 0
    assert item.detalhes["e113_count"] == 0


def test_e112_e113_contagem():
    """E112 e E113 são contados nos detalhes sem afetar o saldo."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
        _e110(vl_tot_debitos="100,00", vl_sld_apurado="150,00"),
        _rec("E111", cod_aj_apur="MG1XXXXX", vl_aj_apur="50,00"),
        _rec("E112", cod_aj_apur="MG1XXXXX", num_da="12345"),
        _rec("E113", cod_aj_apur="MG1XXXXX", num_doc="99999"),
    ]
    item = engine.calcular_icms(records)
    assert item.detalhes["e111_count"] == 1
    assert item.detalhes["e112_count"] == 1
    assert item.detalhes["e113_count"] == 1
    assert item.saldo_apurado == Decimal("150")


# ─────────────────────────────────────────────────────────────────────────────
# M100 / M500 regime cumulativo PIS
# ─────────────────────────────────────────────────────────────────────────────


def test_pis_cumulativo_com_m100():
    """M100 presente → usa caminho cumulativo, detalhes.regime='cumulativo'."""
    engine = get_apuracao_engine()
    records = [
        _rec("M100", vl_cont="65,00"),
    ]
    item = engine.calcular_pis(records)
    assert item.tributo == "PIS"
    assert item.detalhes.get("regime") == "cumulativo"
    assert item.total_debitos == Decimal("65")


def test_pis_cumulativo_base_e_aliq():
    """M100 sem vl_cont → base × alíquota.

    Manual: vl_bc=10000, aliq=0,65% → PIS=65,00
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M100", vl_bc="10000,00", aliq_pis_ou_pasep="0,65"),
    ]
    item = engine.calcular_pis(records)
    assert item.total_debitos == Decimal("65")
    assert item.situacao == "devedor"


def test_pis_cumulativo_vl_cont_direto():
    """M100 com vl_cont preenchido → usa diretamente sem recalcular."""
    engine = get_apuracao_engine()
    records = [
        _rec("M100", vl_cont="99,50", vl_bc="50000,00"),
    ]
    item = engine.calcular_pis(records)
    assert item.total_debitos == Decimal("99.50")


def test_pis_cumulativo_sem_m100_usa_nao_cumulativo():
    """Sem M100 → usa caminho não-cumulativo (M210)."""
    engine = get_apuracao_engine()
    records = [
        _rec("M210", vl_cont_apr="99,00"),
    ]
    item = engine.calcular_pis(records)
    assert item.detalhes.get("regime") is None
    assert item.total_debitos == Decimal("99")


# ─────────────────────────────────────────────────────────────────────────────
# M500 regime cumulativo COFINS
# ─────────────────────────────────────────────────────────────────────────────


def test_cofins_cumulativo_com_m500():
    """M500 presente → usa caminho cumulativo."""
    engine = get_apuracao_engine()
    records = [
        _rec("M500", vl_cont="300,00"),
    ]
    item = engine.calcular_cofins(records)
    assert item.tributo == "COFINS"
    assert item.detalhes.get("regime") == "cumulativo"
    assert item.total_debitos == Decimal("300")


def test_cofins_cumulativo_base_e_aliq():
    """M500 sem vl_cont → base × alíquota.

    Manual: vl_bc=10000, aliq=3% → COFINS=300,00
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M500", vl_bc="10000,00", aliq_cofins="3,00"),
    ]
    item = engine.calcular_cofins(records)
    assert item.total_debitos == Decimal("300")
    assert item.situacao == "devedor"


def test_cofins_cumulativo_vl_cont_direto():
    """M500 com vl_cont → usa diretamente."""
    engine = get_apuracao_engine()
    records = [
        _rec("M500", vl_cont="456,00", vl_bc="20000,00"),
    ]
    item = engine.calcular_cofins(records)
    assert item.total_debitos == Decimal("456")


def test_cofins_cumulativo_sem_m500_usa_nao_cumulativo():
    """Sem M500 → usa caminho não-cumulativo (M610)."""
    engine = get_apuracao_engine()
    records = [
        _rec("M610", vl_cont_apr="456,00"),
    ]
    item = engine.calcular_cofins(records)
    assert item.detalhes.get("regime") is None
    assert item.total_debitos == Decimal("456")


# ─────────────────────────────────────────────────────────────────────────────
# M400 / M405 créditos PIS
# ─────────────────────────────────────────────────────────────────────────────


def test_pis_credito_m400():
    """M400 crédito abate PIS não-cumulativo.

    Manual: M210=100, M400 crédito=30 → saldo=70 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M210", vl_cont_apr="100,00"),
        _rec("M400", vl_cred="30,00"),
    ]
    item = engine.calcular_pis(records)
    assert item.total_creditos == Decimal("30")
    assert item.saldo_apurado == Decimal("70")
    assert item.situacao == "devedor"


def test_pis_credito_excede_vira_credor():
    """Crédito PIS > débito → saldo negativo → situacao=credor.

    Manual: M210=50, M400=80 → saldo=-30 (credor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M210", vl_cont_apr="50,00"),
        _rec("M400", vl_cred="80,00"),
    ]
    item = engine.calcular_pis(records)
    assert item.saldo_apurado == Decimal("-30")
    assert item.situacao == "credor"


def test_pis_credito_m405():
    """M405 também conta como crédito PIS.

    Manual: M210=100, M405=25 → saldo=75 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M210", vl_cont_apr="100,00"),
        _rec("M405", vl_cred="25,00"),
    ]
    item = engine.calcular_pis(records)
    assert item.total_creditos == Decimal("25")
    assert item.saldo_apurado == Decimal("75")


def test_pis_credito_zero_sem_m400():
    """Sem M400/M405 → credito=0, saldo=total M210.

    Manual: M210=99 → saldo=99 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M210", vl_cont_apr="99,00"),
    ]
    item = engine.calcular_pis(records)
    assert item.total_creditos == Decimal("0")
    assert item.saldo_apurado == Decimal("99")


# ─────────────────────────────────────────────────────────────────────────────
# M800 créditos COFINS
# ─────────────────────────────────────────────────────────────────────────────


def test_cofins_credito_m800():
    """M800 crédito abate COFINS não-cumulativo.

    Manual: M610=456, M800=100 → saldo=356 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M610", vl_cont_apr="456,00"),
        _rec("M800", vl_cred="100,00"),
    ]
    item = engine.calcular_cofins(records)
    assert item.total_creditos == Decimal("100")
    assert item.saldo_apurado == Decimal("356")
    assert item.situacao == "devedor"


def test_cofins_credito_excede_vira_credor():
    """Crédito COFINS > débito → situacao=credor.

    Manual: M610=100, M800=150 → saldo=-50 (credor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M610", vl_cont_apr="100,00"),
        _rec("M800", vl_cred="150,00"),
    ]
    item = engine.calcular_cofins(records)
    assert item.saldo_apurado == Decimal("-50")
    assert item.situacao == "credor"


def test_cofins_cumulativo_com_m800_credito():
    """M500 cumulativo com M800 crédito.

    Manual: M500 vl_cont=300, M800=50 → saldo=250 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M500", vl_cont="300,00"),
        _rec("M800", vl_cred="50,00"),
    ]
    item = engine.calcular_cofins(records)
    assert item.total_creditos == Decimal("50")
    assert item.saldo_apurado == Decimal("250")


def test_pis_m400_e_m405_somados():
    """M400 + M405 ambos contam como crédito PIS.

    Manual: M210=200, M400=30, M405=20 → saldo=150 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("M210", vl_cont_apr="200,00"),
        _rec("M400", vl_cred="30,00"),
        _rec("M405", vl_cred="20,00"),
    ]
    item = engine.calcular_pis(records)
    assert item.total_creditos == Decimal("50")
    assert item.saldo_apurado == Decimal("150")


def test_item_apuracao_to_dict_inclui_ajustes():
    """to_dict inclui ajustes_debito e ajustes_credito."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
        _e110(vl_tot_debitos="100,00", vl_sld_apurado="150,00"),
        _rec("E111", cod_aj_apur="MG1XXXXX", vl_aj_apur="50,00"),
    ]
    item = engine.calcular_icms(records)
    d = item.to_dict()
    assert "ajustes_debito" in d
    assert "ajustes_credito" in d
    assert Decimal(d["ajustes_debito"]) == Decimal("50")
    assert Decimal(d["ajustes_credito"]) == Decimal("0")


def test_e111_cod_curto_aviso():
    """E111 com cod_aj_apur < 3 chars → aviso com '(vazio)' ou o código curto."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
        _e110(vl_tot_debitos="100,00", vl_sld_apurado="100,00"),
        _rec("E111", cod_aj_apur="AB", vl_aj_apur="10,00"),
    ]
    item = engine.calcular_icms(records)
    avisos = [d for d in item.divergencias if d.severidade == Severidade.AVISO]
    assert len(avisos) >= 1


def test_e111_ajuste_reduz_para_credor():
    """Ajuste crédito grande → saldo vira credor.

    Manual: debitos=50, creditos=0, ajustes_credito=80 → saldo=50-80=-30 (credor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="50,00"),
        _e110(vl_tot_debitos="50,00", vl_sld_apurado="-30,00"),
        _rec("E111", cod_aj_apur="MG2YYYYY", vl_aj_apur="80,00"),
    ]
    item = engine.calcular_icms(records)
    assert item.saldo_apurado == Decimal("-30")
    assert item.situacao == "credor"
