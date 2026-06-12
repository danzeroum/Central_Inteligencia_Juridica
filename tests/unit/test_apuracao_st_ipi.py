"""Testes unitários — ICMS-ST (E200/E210) e IPI (E520/E530) — S-C.6.

Leiaute conferido contra Guia Prático EFD ICMS/IPI v3.1.5 (jan/2025).
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
    return SpedRecord(bloco=tipo[0], tipo_registro=tipo, campos=campos, numero_linha=1)


# ─────────────────────────────────────────────────────────────────────────────
# ICMS-ST (E200 / E210)
# ─────────────────────────────────────────────────────────────────────────────


def test_icms_st_devedor_simples():
    """C100 saída com vl_icmsst → débito ST; saldo devedor.

    Manual: debitos_st=200, creditos_st=0 → saldo=200 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icmsst="200,00", vl_icms="0,00"),
    ]
    item = engine.calcular_icms_st(records)
    assert item.tributo == "ICMS-ST"
    assert item.total_debitos == Decimal("200")
    assert item.total_creditos == Decimal("0")
    assert item.saldo_apurado == Decimal("200")
    assert item.situacao == "devedor"


def test_icms_st_credor():
    """Mais créditos ST do que débitos → credor.

    Manual: debitos_st=100, creditos_st=150 → saldo=-50 (credor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icmsst="100,00"),
        _rec("C100", ind_oper="0", cod_sit="00", vl_icmsst="150,00"),
    ]
    item = engine.calcular_icms_st(records)
    assert item.saldo_apurado == Decimal("-50")
    assert item.situacao == "credor"


def test_icms_st_divergencia_e210():
    """E210 declarado difere do computado → ERRO divergência.

    Manual: debitos_st=200 (C100), E210 vl_retencao_st=300 → diff=100 → ERRO
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icmsst="200,00"),
        _rec("E200", uf="SP", dt_ini="2025-01-01", dt_fin="2025-01-31"),
        _rec(
            "E210",
            ind_mov_st="0",
            vl_sld_cred_ant_st="0,00",
            vl_devol_st="0,00",
            vl_ressarc_st="0,00",
            vl_out_cred_st="0,00",
            vl_aj_creditos_st="0,00",
            vl_retencao_st="300,00",  # diverge: declarado 300, computado 200
            vl_out_deb_st="0,00",
            vl_aj_debitos_st="0,00",
            vl_sld_dev_ant_st="0,00",
            vl_deducoes_st="0,00",
            vl_icms_recol_st="300,00",
            vl_sld_cred_st_transportar="0,00",
            deb_esp_st="0,00",
        ),
    ]
    item = engine.calcular_icms_st(records)
    erros = [d for d in item.divergencias if d.severidade == Severidade.ERRO]
    assert any("E210.debitos_st" in d.campo for d in erros)


def test_icms_st_multiplas_ufs():
    """Dois E200 (SP e RJ) com E210 correspondentes → detalhes.ufs com ambas as UFs.

    Manual: debitos_st=300 (200+100 acumulados) → saldo=300 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icmsst="200,00"),
        _rec("C100", ind_oper="1", cod_sit="00", vl_icmsst="100,00"),
        _rec("E200", uf="SP", dt_ini="2025-01-01", dt_fin="2025-01-31"),
        _rec(
            "E210",
            ind_mov_st="0",
            vl_sld_cred_ant_st="0,00",
            vl_devol_st="0,00",
            vl_ressarc_st="0,00",
            vl_out_cred_st="0,00",
            vl_aj_creditos_st="0,00",
            vl_retencao_st="200,00",
            vl_out_deb_st="0,00",
            vl_aj_debitos_st="0,00",
            vl_sld_dev_ant_st="0,00",
            vl_deducoes_st="0,00",
            vl_icms_recol_st="200,00",
            vl_sld_cred_st_transportar="0,00",
            deb_esp_st="0,00",
        ),
        _rec("E200", uf="RJ", dt_ini="2025-01-01", dt_fin="2025-01-31"),
        _rec(
            "E210",
            ind_mov_st="0",
            vl_sld_cred_ant_st="0,00",
            vl_devol_st="0,00",
            vl_ressarc_st="0,00",
            vl_out_cred_st="0,00",
            vl_aj_creditos_st="0,00",
            vl_retencao_st="100,00",
            vl_out_deb_st="0,00",
            vl_aj_debitos_st="0,00",
            vl_sld_dev_ant_st="0,00",
            vl_deducoes_st="0,00",
            vl_icms_recol_st="100,00",
            vl_sld_cred_st_transportar="0,00",
            deb_esp_st="0,00",
        ),
    ]
    item = engine.calcular_icms_st(records)
    assert item.saldo_apurado == Decimal("300")
    assert "SP" in item.detalhes["ufs"]
    assert "RJ" in item.detalhes["ufs"]


def test_icms_st_sem_e200_ausente():
    """Sem E200 e sem ST em C100 → situacao='ausente'."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
    ]
    item = engine.calcular_icms_st(records)
    assert item.situacao == "ausente"
    assert item.tributo == "ICMS-ST"


def test_icms_st_e210_sem_e200_erro():
    """E210 sem E200 → ERRO estrutural."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icmsst="100,00"),
        _rec(
            "E210",
            ind_mov_st="0",
            vl_sld_cred_ant_st="0,00",
            vl_devol_st="0,00",
            vl_ressarc_st="0,00",
            vl_out_cred_st="0,00",
            vl_aj_creditos_st="0,00",
            vl_retencao_st="100,00",
            vl_out_deb_st="0,00",
            vl_aj_debitos_st="0,00",
            vl_sld_dev_ant_st="0,00",
            vl_deducoes_st="0,00",
            vl_icms_recol_st="100,00",
            vl_sld_cred_st_transportar="0,00",
            deb_esp_st="0,00",
        ),
    ]
    item = engine.calcular_icms_st(records)
    erros = [d for d in item.divergencias if d.severidade == Severidade.ERRO]
    assert any(d.campo == "E210" for d in erros)
    assert any("sem E200" in d.valor_computado for d in erros)


def test_icms_st_nao_incluido_em_calcular_sem_dados():
    """calcular() para efd_icms sem ST não inclui item ICMS-ST."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
    ]
    resultado = engine.calcular(records, tipo="efd_icms")
    tributos = {i.tributo for i in resultado.items}
    assert "ICMS" in tributos
    assert "ICMS-ST" not in tributos


def test_icms_st_incluido_em_calcular_com_dados():
    """calcular() para efd_icms com vl_icmsst inclui item ICMS-ST."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00", vl_icmsst="50,00"),
    ]
    resultado = engine.calcular(records, tipo="efd_icms")
    tributos = {i.tributo for i in resultado.items}
    assert "ICMS-ST" in tributos


# ─────────────────────────────────────────────────────────────────────────────
# IPI (E520 / E530)
# ─────────────────────────────────────────────────────────────────────────────


def test_ipi_devedor_simples():
    """C100 saída com vl_ipi → débito IPI; saldo devedor.

    Manual: debitos=120, creditos=0 → saldo=120 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_ipi="120,00"),
    ]
    item = engine.calcular_ipi(records)
    assert item.tributo == "IPI"
    assert item.total_debitos == Decimal("120")
    assert item.saldo_apurado == Decimal("120")
    assert item.situacao == "devedor"


def test_ipi_credito_entrada():
    """C100 entrada com vl_ipi → crédito IPI; compensa débito.

    Manual: debitos=120, creditos=50 → saldo=70 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_ipi="120,00"),
        _rec("C100", ind_oper="0", cod_sit="00", vl_ipi="50,00"),
    ]
    item = engine.calcular_ipi(records)
    assert item.saldo_apurado == Decimal("70")
    assert item.situacao == "devedor"


def test_ipi_confronto_e520():
    """E520 real declarado compatível → zero divergências.

    Manual: debitos=80, creditos=30 → saldo=50 (devedor); E520 confirma.
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_ipi="80,00"),
        _rec("C100", ind_oper="0", cod_sit="00", vl_ipi="30,00"),
        _rec(
            "E520",
            vl_sd_ant_ipi="0,00",
            vl_deb_ipi="80,00",
            vl_cred_ipi="30,00",
            vl_od_ipi="0,00",
            vl_oc_ipi="0,00",
            vl_sc_ipi="0,00",
            vl_sd_ipi="50,00",
        ),
    ]
    item = engine.calcular_ipi(records)
    assert item.saldo_apurado == Decimal("50")
    erros = [d for d in item.divergencias if d.severidade == Severidade.ERRO]
    assert len(erros) == 0


def test_ipi_divergencia_e520():
    """E520 diverge dos C100 → ERRO divergência.

    Manual: debitos=80 (C100), E520 declarado vl_deb_ipi=100 → diff=20 → ERRO
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_ipi="80,00"),
        _rec(
            "E520",
            vl_sd_ant_ipi="0,00",
            vl_deb_ipi="100,00",
            vl_cred_ipi="0,00",
            vl_od_ipi="0,00",
            vl_oc_ipi="0,00",
            vl_sc_ipi="0,00",
            vl_sd_ipi="100,00",
        ),
    ]
    item = engine.calcular_ipi(records)
    erros = [d for d in item.divergencias if d.severidade == Severidade.ERRO]
    assert any("E520.vl_deb_ipi" in d.campo for d in erros)


def test_ipi_ajuste_e530_debito():
    """E530 com ind_aj='0' (débito) → ajustes_debito.

    Manual: debitos=100, ajustes_debito=20 → saldo=120 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_ipi="100,00"),
        _rec(
            "E530",
            cod_aj="SP000101",
            ind_aj="0",
            vl_aj_ipi="20,00",
            cod_item="",
            num_da="",
            num_proc="",
            ind_proc="",
            descr_compl_aj="ajuste débito",
            cod_cta="",
        ),
    ]
    item = engine.calcular_ipi(records)
    assert item.ajustes_debito == Decimal("20")
    assert item.saldo_apurado == Decimal("120")


def test_ipi_ajuste_e530_credito():
    """E530 com ind_aj='1' (crédito) → ajustes_credito.

    Manual: debitos=100, ajustes_credito=15 → saldo=85 (devedor)
    """
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_ipi="100,00"),
        _rec(
            "E530",
            cod_aj="SP020101",
            ind_aj="1",
            vl_aj_ipi="15,00",
            cod_item="",
            num_da="",
            num_proc="",
            ind_proc="",
            descr_compl_aj="ajuste crédito",
            cod_cta="",
        ),
    ]
    item = engine.calcular_ipi(records)
    assert item.ajustes_credito == Decimal("15")
    assert item.saldo_apurado == Decimal("85")


def test_ipi_sem_dados_ausente():
    """Sem C100 com vl_ipi e sem E520 → situacao='ausente'."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
    ]
    item = engine.calcular_ipi(records)
    assert item.situacao == "ausente"
    assert item.tributo == "IPI"


def test_ipi_nao_incluido_em_calcular_sem_dados():
    """calcular() para efd_icms sem IPI não inclui item IPI."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00"),
    ]
    resultado = engine.calcular(records, tipo="efd_icms")
    tributos = {i.tributo for i in resultado.items}
    assert "IPI" not in tributos


def test_ipi_incluido_em_calcular_com_e520():
    """calcular() para efd_icms com E520 inclui item IPI."""
    engine = get_apuracao_engine()
    records = [
        _rec("C100", ind_oper="1", cod_sit="00", vl_icms="100,00", vl_ipi="20,00"),
        _rec(
            "E520",
            vl_sd_ant_ipi="0,00",
            vl_deb_ipi="20,00",
            vl_cred_ipi="0,00",
            vl_od_ipi="0,00",
            vl_oc_ipi="0,00",
            vl_sc_ipi="0,00",
            vl_sd_ipi="20,00",
        ),
    ]
    resultado = engine.calcular(records, tipo="efd_icms")
    tributos = {i.tributo for i in resultado.items}
    assert "IPI" in tributos
