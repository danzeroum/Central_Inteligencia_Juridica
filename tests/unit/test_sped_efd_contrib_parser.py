"""Testes unitários para SpedEfdContribParser (EFD-Contribuições)."""

from __future__ import annotations

import pytest

from src.fiscal.parser import ParseResult, SpedEfdContribParser, get_parser
from src.fiscal.parser.sped_efd_contrib import SpedEfdContribParser as _ContribCls

# ─────────────────────────────────────────────────────────────────────────────
# Fixture: arquivo SPED EFD-Contribuições mínimo
# ─────────────────────────────────────────────────────────────────────────────

_SPED_CONTRIB = (
    "|0000|006|0|01012025|31012025|EMPRESA PIS COFINS LTDA|12345678000195|SP|111111111111|3550308||1|1|\n"
    "|0001|0|\n"
    "|0110|1|1|1|1|\n"
    "|0150|FORN001|FORNECEDOR SA|1058|00000000000200|||3550308|||RUA A|1|AP 1|CENTRO|\n"
    "|0200|PROD001|PRODUTO TESTE|||UN|00|12345678|0|90|||\n"
    "|0990|5|\n"
    "|A001|0|\n"
    "|A100|1|2|PREST001|00|001|01|123|NFSe999|01012025|01012025|5000,00|0,00|5000,00|0,65|32,50|5000,00|3,00|150,00|0,00|0,00|0,00|0,00|\n"
    "|A990|2|\n"
    "|C001|0|\n"
    "|C100|1|1|FORN001|55|00|001|42|35250100000100000000550010000000421234567890|01012025|01012025|1000,00|0|50,00|0,00|950,00|0|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|6,50|30,00|0,00|0,00|\n"
    "|C181|01|5102|1000,00|50,00|950,00|0,65||0,00|6,17|\n"
    "|C185|01|5102|1000,00|50,00|950,00|3,00||0,00|28,50|\n"
    "|C990|4|\n"
    "|D001|0|\n"
    "|D100|1|1|TRANSP01|57|00|001|01|35250100000100000000570010000000011234567890|01012025|01012025|01|0|800,00|0,00|0|800,00|0,00|0,00|0,00||||\n"
    "|D990|2|\n"
    "|F001|0|\n"
    "|F100|1|FORN001|PROD001|15012025|2000,00|01|2000,00|0,65|13,00|01|2000,00|3,00|60,00|01|01|CAIXA BANCO||||\n"
    "|F990|2|\n"
    "|M001|0|\n"
    "|M100|101|0|950,00|0,65||0,00|6,17|0,00|0,00|6,17|0,00|6,17|6,17|0,00|0,00|0,00|0,00|\n"
    "|M200|6,17|6,17|0,00|0,00|0,00|0,00|6,17|0,00|0,00|0,00|6,17|0,00|0,00|0,00|0,00|6,17|0,00|\n"
    "|M210|01|7000,00|6950,00|0,65|0,00|0,00|45,17|0,00|45,17|0,00|\n"
    "|M500|201|0|950,00|3,00||0,00|28,50|0,00|0,00|28,50|0,00|28,50|28,50|0,00|0,00|0,00|0,00|\n"
    "|M600|28,50|28,50|0,00|0,00|0,00|0,00|28,50|0,00|0,00|0,00|28,50|0,00|0,00|0,00|0,00|28,50|0,00|\n"
    "|M610|02|7000,00|6950,00|3,00|0,00|0,00|208,50|0,00|208,50|0,00|\n"
    "|M990|7|\n"
    "|P001|0|\n"
    "|P010|12345678000195|\n"
    "|P100|01012025|31012025|100000,00|62.09-1/00|100000,00|0,00|1,00|1000,00|1000,00|\n"
    "|P200|012025|1000,00|0,00|0,00|1000,00|0,00|\n"
    "|P990|4|\n"
    "|9001|0|\n"
    "|9900|0000|1|\n"
    "|9900|0001|1|\n"
    "|9900|A100|1|\n"
    "|9900|C100|1|\n"
    "|9900|M200|1|\n"
    "|9990|6|\n"
    "|9999|45|\n"
)


@pytest.fixture(scope="module")
def result():
    parser = SpedEfdContribParser()
    return parser.parse(_SPED_CONTRIB.encode("latin-1"))


# ─────────────────────────────────────────────────────────────────────────────
# Estrutura geral
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_result_type(result):
    assert isinstance(result, ParseResult)


def test_records_not_empty(result):
    assert result.total_registros > 0


def test_total_linhas_counted(result):
    assert result.total_linhas == len(_SPED_CONTRIB.splitlines())


def test_blocos_present(result):
    assert "0" in result.registros_por_bloco
    assert "A" in result.registros_por_bloco
    assert "C" in result.registros_por_bloco
    assert "M" in result.registros_por_bloco
    assert "P" in result.registros_por_bloco
    assert "9" in result.registros_por_bloco


# ─────────────────────────────────────────────────────────────────────────────
# Bloco 0
# ─────────────────────────────────────────────────────────────────────────────


def test_0000_date_conversion(result):
    r = next(r for r in result.records if r.tipo_registro == "0000")
    assert r.campos["dt_ini"] == "2025-01-01"
    assert r.campos["dt_fin"] == "2025-01-31"


def test_0000_nome(result):
    r = next(r for r in result.records if r.tipo_registro == "0000")
    assert r.campos["nome"] == "EMPRESA PIS COFINS LTDA"


def test_0000_ind_natur_pj(result):
    r = next(r for r in result.records if r.tipo_registro == "0000")
    assert "ind_natur_pj" in r.campos
    assert r.campos["ind_natur_pj"] == "1"


def test_0110_parsing(result):
    r = next(r for r in result.records if r.tipo_registro == "0110")
    assert r.campos["cod_inc_trib"] == "1"
    assert r.campos["ind_apro_cred"] == "1"
    assert r.campos["ind_reg_cum"] == "1"


# ─────────────────────────────────────────────────────────────────────────────
# Bloco A
# ─────────────────────────────────────────────────────────────────────────────


def test_a100_dates(result):
    r = next(r for r in result.records if r.tipo_registro == "A100")
    assert r.campos["dt_doc"] == "2025-01-01"
    assert r.campos["dt_exc"] == "2025-01-01"


def test_a100_valores(result):
    r = next(r for r in result.records if r.tipo_registro == "A100")
    assert r.campos["vl_doc"] == "5000,00"
    assert r.campos["vl_pis"] == "32,50"
    assert r.campos["vl_cofins"] == "150,00"
    assert r.campos["aliq_pis"] == "0,65"
    assert r.campos["aliq_cofins"] == "3,00"


def test_a100_chv_nfse(result):
    r = next(r for r in result.records if r.tipo_registro == "A100")
    assert r.campos["chv_nfse"] == "NFSe999"


# ─────────────────────────────────────────────────────────────────────────────
# Bloco C
# ─────────────────────────────────────────────────────────────────────────────


def test_c100_dates(result):
    r = next(r for r in result.records if r.tipo_registro == "C100")
    assert r.campos["dt_doc"] == "2025-01-01"
    assert r.campos["dt_e_s"] == "2025-01-01"


def test_c100_chave_nfe(result):
    r = next(r for r in result.records if r.tipo_registro == "C100")
    assert "chv_nfe" in r.campos


def test_c181_pis_detail(result):
    r = next(r for r in result.records if r.tipo_registro == "C181")
    assert r.campos["cst_pis"] == "01"
    assert r.campos["cfop"] == "5102"
    assert r.campos["vl_pis"] == "6,17"


def test_c185_cofins_detail(result):
    r = next(r for r in result.records if r.tipo_registro == "C185")
    assert r.campos["cst_cofins"] == "01"
    assert r.campos["vl_cofins"] == "28,50"


# ─────────────────────────────────────────────────────────────────────────────
# Bloco M — Apuração PIS/COFINS
# ─────────────────────────────────────────────────────────────────────────────


def test_m100_pis_credito(result):
    r = next(r for r in result.records if r.tipo_registro == "M100")
    assert r.campos["cod_cred"] == "101"
    assert r.campos["vl_bc_pis"] == "950,00"
    assert r.campos["aliq_pis"] == "0,65"
    assert r.campos["vl_cred"] == "6,17"


def test_m200_pis_apuracao(result):
    r = next(r for r in result.records if r.tipo_registro == "M200")
    assert r.campos["vl_tot_cont_nc_per"] == "6,17"
    assert r.campos["vl_cont_nc_rec"] == "6,17"


def test_m210_pis_detalhe(result):
    r = next(r for r in result.records if r.tipo_registro == "M210")
    assert r.campos["cod_cont"] == "01"
    assert r.campos["vl_rec_brt"] == "7000,00"
    assert r.campos["vl_cont_per_apur"] == "45,17"


def test_m500_cofins_credito(result):
    r = next(r for r in result.records if r.tipo_registro == "M500")
    assert r.campos["cod_cred"] == "201"
    assert r.campos["vl_bc_cofins"] == "950,00"
    assert r.campos["aliq_cofins"] == "3,00"


def test_m600_cofins_apuracao(result):
    r = next(r for r in result.records if r.tipo_registro == "M600")
    assert r.campos["vl_tot_cont_nc_per"] == "28,50"


def test_m610_cofins_detalhe(result):
    r = next(r for r in result.records if r.tipo_registro == "M610")
    assert r.campos["cod_cont"] == "02"
    assert r.campos["vl_rec_brt"] == "7000,00"
    assert r.campos["vl_cont_per_apur"] == "208,50"


# ─────────────────────────────────────────────────────────────────────────────
# Bloco P
# ─────────────────────────────────────────────────────────────────────────────


def test_p010_cnpj(result):
    r = next(r for r in result.records if r.tipo_registro == "P010")
    assert r.campos["cnpj"] == "12345678000195"


def test_p100_dates(result):
    r = next(r for r in result.records if r.tipo_registro == "P100")
    assert r.campos["dt_ini"] == "2025-01-01"
    assert r.campos["dt_fin"] == "2025-01-31"


def test_p100_valores(result):
    r = next(r for r in result.records if r.tipo_registro == "P100")
    assert r.campos["vl_rec_tot_est"] == "100000,00"
    assert r.campos["aliq_princ"] == "1,00"
    assert r.campos["vl_contrib_previdenc"] == "1000,00"


def test_p200_apuracao(result):
    r = next(r for r in result.records if r.tipo_registro == "P200")
    assert r.campos["vl_cont_apurada"] == "1000,00"
    assert r.campos["vl_cont_dev"] == "1000,00"


# ─────────────────────────────────────────────────────────────────────────────
# Bloco F
# ─────────────────────────────────────────────────────────────────────────────


def test_f100_parsing(result):
    r = next(r for r in result.records if r.tipo_registro == "F100")
    assert r.campos["vl_oper"] == "2000,00"
    assert r.campos["vl_pis"] == "13,00"
    assert r.campos["vl_cofins"] == "60,00"
    assert r.campos["dt_oper"] == "2025-01-15"


# ─────────────────────────────────────────────────────────────────────────────
# Bloco 9
# ─────────────────────────────────────────────────────────────────────────────


def test_9900_records(result):
    noves = [r for r in result.records if r.tipo_registro == "9900"]
    assert len(noves) == 5


def test_9900_first_reg(result):
    r = next(r for r in result.records if r.tipo_registro == "9900")
    assert r.campos["reg"] == "0000"
    assert r.campos["qt_reg_blc"] == "1"


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────


def test_registry_efd_contrib():
    parser = get_parser("efd_contrib")
    assert isinstance(parser, SpedEfdContribParser)


def test_registry_efd_contribuicoes():
    parser = get_parser("efd_contribuicoes")
    assert isinstance(parser, SpedEfdContribParser)


def test_registry_icms_unchanged():
    from src.fiscal.parser import SpedEfdIcmsParser

    parser = get_parser("efd_icms")
    assert isinstance(parser, SpedEfdIcmsParser)


def test_registry_unknown_raises():
    with pytest.raises(ValueError, match="Parser não disponível"):
        get_parser("efd_pis_standalone")
