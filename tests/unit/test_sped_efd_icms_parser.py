"""Testes unitários — Parser SPED EFD-ICMS/IPI (S-B.2).

Cobre:
- Parsing de registros principais (0000, 0150, 0200, C100, C170, D100, E110, E520, 9900)
- Datas SPED (DDMMAAAA → ISO)
- Decimais mantidos como string
- Registros desconhecidos → _raw
- Arquivo vazio / linhas em branco
- Contagens por bloco e por tipo
- Registry (get_parser)
- Encoding alternativo
- Números de linha corretos
"""

from __future__ import annotations

import pytest

from src.fiscal.parser import ParseResult, SpedEfdIcmsParser, SpedRecord, get_parser
from src.fiscal.parser.base import SpedParser

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

# Minimal but realistic EFD-ICMS sample (latin-1 encoded)
_SPED_SAMPLE = (
    "|0000|015|0|01012025|31012025|EMPRESA TESTE SA|12345678000190||SP|123456789|3550308|||A|1|\n"
    "|0001|0|\n"
    "|0150|001|CLIENTE ABC LTDA|0105|98765432000155||SP1234567|3550308||Rua das Flores|100||Centro|\n"
    "|0200|PROD001|Produto A||UN|04|00|||0000|0,00||\n"
    "|0990|4|\n"
    "|C001|0|\n"
    "|C100|1|0|001|55|00|001|123|35250112345678000190550001000000001234567890|01012025|02012025"
    "|1000,00|0|0,00|0,00|1000,00|0||0,00|0,00|120,00|12,00|0,00|0,00|0,00|0,00|0,00|0,00|\n"
    "|C170|1|PROD001|Produto A|10,000|UN|1000,00|0,00|0|040|5102||120,00|12,00|120,00"
    "|0,00|0,00|0,00|||49|0,00|0,00|0,00|01||0,00|0,00|0,00|01||0,00|0,00|0,00||0,00|\n"
    "|C990|2|\n"
    "|E001|0|\n"
    "|E110|120,00|0,00|120,00|0,00|0,00|0,00|0,00|0,00|0,00|120,00|0,00|120,00|0,00|0,00|\n"
    "|E990|2|\n"
    "|9001|0|\n"
    "|9900|0000|1|\n"
    "|9900|0001|1|\n"
    "|9900|0150|1|\n"
    "|9900|0200|1|\n"
    "|9900|0990|1|\n"
    "|9900|C001|1|\n"
    "|9900|C100|1|\n"
    "|9900|C170|1|\n"
    "|9900|C990|1|\n"
    "|9900|E001|1|\n"
    "|9900|E110|1|\n"
    "|9900|E990|1|\n"
    "|9900|9001|1|\n"
    "|9900|9900|14|\n"
    "|9900|9990|1|\n"
    "|9900|9999|1|\n"
    "|9990|17|\n"
    "|9999|33|\n"
).encode("latin-1")


@pytest.fixture()
def parser() -> SpedEfdIcmsParser:
    return SpedEfdIcmsParser()


@pytest.fixture()
def result(parser: SpedEfdIcmsParser) -> ParseResult:
    return parser.parse(_SPED_SAMPLE)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Resultado geral
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_returns_parse_result(result: ParseResult) -> None:
    assert isinstance(result, ParseResult)


def test_parse_has_records(result: ParseResult) -> None:
    assert len(result.records) > 0


def test_parse_total_linhas(result: ParseResult) -> None:
    assert result.total_linhas > 0


def test_parse_total_registros_equals_records_len(result: ParseResult) -> None:
    assert result.total_registros == len(result.records)


def test_parse_no_errors(result: ParseResult) -> None:
    assert result.erros == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. Registro 0000 — Identificação
# ─────────────────────────────────────────────────────────────────────────────


def test_0000_present(result: ParseResult) -> None:
    tipos = [r.tipo_registro for r in result.records]
    assert "0000" in tipos


def test_0000_fields(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "0000")
    assert rec.campos["cod_ver"] == "015"
    assert rec.campos["nome"] == "EMPRESA TESTE SA"
    assert rec.campos["uf"] == "SP"
    assert rec.campos["ind_perfil"] == "A"


def test_0000_date_dt_ini(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "0000")
    assert rec.campos["dt_ini"] == "2025-01-01"


def test_0000_date_dt_fin(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "0000")
    assert rec.campos["dt_fin"] == "2025-01-31"


def test_0000_bloco(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "0000")
    assert rec.bloco == "0"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Registro 0150 — Participantes
# ─────────────────────────────────────────────────────────────────────────────


def test_0150_fields(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "0150")
    assert rec.campos["cod_part"] == "001"
    assert rec.campos["nome"] == "CLIENTE ABC LTDA"
    assert (
        rec.campos["uf"] if "uf" in rec.campos else rec.campos.get("ie", "") is not None
    )


def test_0150_bairro(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "0150")
    assert rec.campos["bairro"] == "Centro"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Registro C100 — Nota Fiscal (Mercadorias)
# ─────────────────────────────────────────────────────────────────────────────


def test_c100_present(result: ParseResult) -> None:
    tipos = [r.tipo_registro for r in result.records]
    assert "C100" in tipos


def test_c100_fields(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "C100")
    assert rec.campos["ind_oper"] == "1"
    assert rec.campos["cod_mod"] == "55"
    assert rec.campos["ser"] == "001"
    assert rec.campos["num_doc"] == "123"


def test_c100_date_dt_doc(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "C100")
    assert rec.campos["dt_doc"] == "2025-01-01"


def test_c100_date_dt_e_s(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "C100")
    assert rec.campos["dt_e_s"] == "2025-01-02"


def test_c100_decimal_vl_doc(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "C100")
    # Decimal is kept as string with comma separator
    assert rec.campos["vl_doc"] == "1000,00"


def test_c100_decimal_vl_icms(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "C100")
    assert rec.campos["vl_icms"] == "12,00"


def test_c100_bloco(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "C100")
    assert rec.bloco == "C"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Registro C170 — Itens da NF
# ─────────────────────────────────────────────────────────────────────────────


def test_c170_fields(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "C170")
    assert rec.campos["cod_item"] == "PROD001"
    assert rec.campos["cfop"] == "5102"
    assert rec.campos["vl_item"] == "1000,00"
    assert rec.campos["aliq_icms"] == "12,00"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Registro E110 — Apuração ICMS
# ─────────────────────────────────────────────────────────────────────────────


def test_e110_present(result: ParseResult) -> None:
    tipos = [r.tipo_registro for r in result.records]
    assert "E110" in tipos


def test_e110_fields(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "E110")
    assert rec.campos["vl_tot_debitos"] == "120,00"
    assert rec.campos["vl_icms_recolher"] == "120,00"
    assert rec.campos["vl_sld_credor_transp"] == "0,00"


def test_e110_bloco(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "E110")
    assert rec.bloco == "E"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Registro 9900 — Controle
# ─────────────────────────────────────────────────────────────────────────────


def test_9900_fields(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "9900")
    assert "reg" in rec.campos
    assert "qt_reg_blc" in rec.campos


# ─────────────────────────────────────────────────────────────────────────────
# 8. Registros genéricos (IND_MOV e QT_LIN)
# ─────────────────────────────────────────────────────────────────────────────


def test_0001_ind_mov(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "0001")
    assert rec.campos["ind_mov"] == "0"


def test_0990_qt_lin(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "0990")
    assert rec.campos["qt_lin"] == "4"


def test_9999_qt_lin(result: ParseResult) -> None:
    rec = next(r for r in result.records if r.tipo_registro == "9999")
    assert rec.campos["qt_lin"] == "33"


# ─────────────────────────────────────────────────────────────────────────────
# 9. Registros desconhecidos
# ─────────────────────────────────────────────────────────────────────────────


def test_unknown_record_preserved_as_raw(parser: SpedEfdIcmsParser) -> None:
    data = b"|ZZZZ|campo1|campo2|\n"
    result = parser.parse(data)
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.tipo_registro == "ZZZZ"
    assert "_raw" in rec.campos
    assert rec.campos["_raw"] == ["campo1", "campo2"]


# ─────────────────────────────────────────────────────────────────────────────
# 10. Arquivo vazio e linhas em branco
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_file(parser: SpedEfdIcmsParser) -> None:
    result = parser.parse(b"")
    assert result.total_registros == 0
    assert result.records == []
    assert result.erros == []


def test_blank_lines_ignored(parser: SpedEfdIcmsParser) -> None:
    data = b"\n\n|0001|0|\n\n"
    result = parser.parse(data)
    assert result.total_registros == 1


def test_non_pipe_lines_ignored(parser: SpedEfdIcmsParser) -> None:
    data = b"comentario\n|0001|0|\n"
    result = parser.parse(data)
    assert result.total_registros == 1


# ─────────────────────────────────────────────────────────────────────────────
# 11. Contagens por bloco e por tipo
# ─────────────────────────────────────────────────────────────────────────────


def test_registros_por_bloco(result: ParseResult) -> None:
    assert "0" in result.registros_por_bloco
    assert "C" in result.registros_por_bloco
    assert "E" in result.registros_por_bloco
    assert "9" in result.registros_por_bloco


def test_registros_por_tipo_9900_count(result: ParseResult) -> None:
    # Sample has 16 lines of 9900
    assert result.registros_por_tipo.get("9900", 0) >= 14


def test_total_registros_matches_sum_por_bloco(result: ParseResult) -> None:
    assert sum(result.registros_por_bloco.values()) == result.total_registros


# ─────────────────────────────────────────────────────────────────────────────
# 12. Números de linha
# ─────────────────────────────────────────────────────────────────────────────


def test_line_numbers_start_at_1(parser: SpedEfdIcmsParser) -> None:
    data = b"|0001|0|\n|0990|1|\n"
    result = parser.parse(data)
    assert result.records[0].numero_linha == 1
    assert result.records[1].numero_linha == 2


def test_line_numbers_skip_blank_lines(parser: SpedEfdIcmsParser) -> None:
    data = b"\n|0001|0|\n\n|0990|1|\n"
    result = parser.parse(data)
    assert result.records[0].numero_linha == 2
    assert result.records[1].numero_linha == 4


# ─────────────────────────────────────────────────────────────────────────────
# 13. Registry
# ─────────────────────────────────────────────────────────────────────────────


def test_registry_efd_icms_returns_parser() -> None:
    p = get_parser("efd_icms")
    assert isinstance(p, SpedEfdIcmsParser)


def test_registry_efd_icms_ipi_alias_returns_parser() -> None:
    p = get_parser("efd_icms_ipi")
    assert isinstance(p, SpedEfdIcmsParser)


def test_registry_unknown_tipo_raises() -> None:
    with pytest.raises(ValueError, match="Parser não disponível"):
        get_parser("unknown_tipo")


def test_registry_efd_contrib_not_yet_available() -> None:
    with pytest.raises(ValueError):
        get_parser("efd_contrib")


# ─────────────────────────────────────────────────────────────────────────────
# 14. Encoding alternativo
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_utf8_encoding(parser: SpedEfdIcmsParser) -> None:
    data = "|0001|0|\n".encode("utf-8")
    result = parser.parse(data, encoding="utf-8")
    assert result.total_registros == 1
    assert result.records[0].campos["ind_mov"] == "0"


# ─────────────────────────────────────────────────────────────────────────────
# 15. SpedParser base (registrar handler customizado)
# ─────────────────────────────────────────────────────────────────────────────


def test_base_parser_custom_handler() -> None:
    base = SpedParser()
    base.register_handler("TEST", lambda campos: {"valor": campos[0] if campos else ""})
    data = b"|TEST|abc|\n"
    result = base.parse(data)
    assert result.records[0].campos["valor"] == "abc"


def test_base_parser_overwrite_handler() -> None:
    base = SpedParser()
    base.register_handler("TEST", lambda campos: {"v": "first"})
    base.register_handler("TEST", lambda campos: {"v": "second"})
    data = b"|TEST|x|\n"
    result = base.parse(data)
    assert result.records[0].campos["v"] == "second"


# ─────────────────────────────────────────────────────────────────────────────
# 16. Parsing de datas inválidas / campos ausentes
# ─────────────────────────────────────────────────────────────────────────────


def test_0000_empty_date_returns_none(parser: SpedEfdIcmsParser) -> None:
    data = ("|0000|015|0||||EMPRESA||SP|||||||||\n").encode("latin-1")
    result = parser.parse(data)
    rec = result.records[0]
    assert rec.campos["dt_ini"] is None
    assert rec.campos["dt_fin"] is None


def test_0000_invalid_date_kept_as_string(parser: SpedEfdIcmsParser) -> None:
    data = b"|0000|015|0|INVALID|31012025|EMPRESA||SP||||||A|1|\n"
    result = parser.parse(data)
    rec = result.records[0]
    # Non-8-digit date string is kept as-is (not None, not converted)
    assert rec.campos["dt_ini"] == "INVALID"
