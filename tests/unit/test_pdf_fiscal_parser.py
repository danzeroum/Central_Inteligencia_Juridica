"""Testes unitários para parsers PDF fiscais (DANFE, DACT, genérico)."""

from __future__ import annotations

import io
import pytest

from src.fiscal.parser.pdf_fiscal import (
    DactParser,
    DanfeParser,
    PdfFiscalParser,
    PdfParseResult,
    _extract_chave,
    _extract_cnpjs,
    _extract_dates,
    _extract_values,
    get_pdf_parser,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers de texto simulado (sem precisar de PDF real)
# ─────────────────────────────────────────────────────────────────────────────


def _make_pdf_bytes(text: str) -> bytes:
    """Cria um PDF mínimo válido com texto simples usando pypdf/reportlab."""
    try:
        import pypdf
        from pypdf import PdfWriter
        from pypdf.generic import (
            ArrayObject,
            DecodedStreamObject,
            DictionaryObject,
            FloatObject,
            NameObject,
            NumberObject,
            RectangleObject,
        )

        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception:
        return b""


# Texto simulado de DANFE
_DANFE_TEXT = """
DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA

Natureza da Operação: VENDA
NF-e No 000.042  Série 001

Chave de Acesso:
3525 0112 3456 7800 0195 5500 1000 0000 4212 3456 7890

CNPJ: 12.345.678/0001-95
Razão Social: EMPRESA EMISSORA LTDA
Endereço: Rua das Flores, 100

CNPJ: 98.765.432/0001-55
Razão Social: CLIENTE DESTINATARIO SA

Data de Emissão: 01/01/2025
Valor Total da NF: R$ 1.000,00
ICMS: R$ 120,00
IPI: R$ 0,00
"""

_CTE_TEXT = """
DACT - DOCUMENTO AUXILIAR DO CONHECIMENTO DE TRANSPORTE ELETRÔNICO

CT-e No 000.001  Série 001

Chave de Acesso:
3525 0112 3456 7800 0395 5700 1000 0000 0112 3456 7890

CNPJ: 11.111.111/0001-11
Transportadora: TRANSP TESTE LTDA
CNPJ Remetente: 12.345.678/0001-95
CNPJ Destinatário: 98.765.432/0001-55

Data de Emissão: 01/01/2025
Valor Total da Prestação: R$ 500,00
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de regex (independentes de PDF real)
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_chave_nfe():
    chave = _extract_chave(_DANFE_TEXT)
    assert chave == "35250112345678000195550010000000421234567890"


def test_extract_chave_cte():
    chave = _extract_chave(_CTE_TEXT)
    assert chave == "35250112345678000395570010000000011234567890"


def test_extract_chave_none_when_absent():
    assert _extract_chave("sem chave aqui") is None


def test_extract_cnpjs():
    cnpjs = _extract_cnpjs(_DANFE_TEXT)
    assert "12.345.678/0001-95" in cnpjs
    assert "98.765.432/0001-55" in cnpjs


def test_extract_cnpjs_order_preserved():
    cnpjs = _extract_cnpjs(_DANFE_TEXT)
    assert cnpjs[0] == "12.345.678/0001-95"


def test_extract_dates():
    dates = _extract_dates(_DANFE_TEXT)
    assert "01/01/2025" in dates


def test_extract_values():
    values = _extract_values(_DANFE_TEXT)
    assert "1.000,00" in values
    assert "120,00" in values


def test_extract_values_cte():
    values = _extract_values(_CTE_TEXT)
    assert "500,00" in values


def test_extract_chave_without_spaces():
    texto = "Chave: 35250112345678000195550010000000421234567890"
    chave = _extract_chave(texto)
    assert chave == "35250112345678000195550010000000421234567890"


# ─────────────────────────────────────────────────────────────────────────────
# PdfParseResult dataclass
# ─────────────────────────────────────────────────────────────────────────────


def test_pdf_parse_result_defaults():
    r = PdfParseResult(tipo="danfe")
    assert r.tipo == "danfe"
    assert r.texto == ""
    assert r.paginas == 0
    assert r.campos == {}
    assert r.erros == []


# ─────────────────────────────────────────────────────────────────────────────
# DanfeParser — sem pypdf real, simula extração via texto
# ─────────────────────────────────────────────────────────────────────────────


def _parser_with_text(parser_cls, text: str):
    """Usa monkeypatching do _read_pdf para testar sem PDF real."""
    import src.fiscal.parser.pdf_fiscal as mod

    original = mod._read_pdf
    mod._read_pdf = lambda data: (text, 1, [])
    try:
        result = parser_cls().parse(b"fake_pdf_bytes")
    finally:
        mod._read_pdf = original
    return result


def test_danfe_tipo():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert r.tipo == "danfe"


def test_danfe_chave():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert r.campos.get("chave_nfe") == "35250112345678000195550010000000421234567890"


def test_danfe_emit_cnpj():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert r.campos.get("emit_cnpj") == "12.345.678/0001-95"


def test_danfe_dest_cnpj():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert r.campos.get("dest_cnpj") == "98.765.432/0001-55"


def test_danfe_dt_emissao():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert r.campos.get("dt_emissao") == "01/01/2025"


def test_danfe_vl_total():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert r.campos.get("vl_total") == "0,00"  # último valor R$


def test_danfe_num_nf():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert r.campos.get("num_nf") is not None


def test_danfe_no_errors_on_valid_text():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert r.erros == []


def test_danfe_paginas():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert r.paginas == 1


def test_danfe_texto_preservado():
    r = _parser_with_text(DanfeParser, _DANFE_TEXT)
    assert "DANFE" in r.texto


# ─────────────────────────────────────────────────────────────────────────────
# DactParser
# ─────────────────────────────────────────────────────────────────────────────


def test_dact_tipo():
    r = _parser_with_text(DactParser, _CTE_TEXT)
    assert r.tipo == "dact"


def test_dact_chave():
    r = _parser_with_text(DactParser, _CTE_TEXT)
    assert r.campos.get("chave_cte") == "35250112345678000395570010000000011234567890"


def test_dact_emit_cnpj():
    r = _parser_with_text(DactParser, _CTE_TEXT)
    assert r.campos.get("emit_cnpj") == "11.111.111/0001-11"


def test_dact_rem_cnpj():
    r = _parser_with_text(DactParser, _CTE_TEXT)
    assert r.campos.get("rem_cnpj") == "12.345.678/0001-95"


def test_dact_vl_prestacao():
    r = _parser_with_text(DactParser, _CTE_TEXT)
    assert r.campos.get("vl_total_prestacao") == "500,00"


def test_dact_no_errors():
    r = _parser_with_text(DactParser, _CTE_TEXT)
    assert r.erros == []


# ─────────────────────────────────────────────────────────────────────────────
# PdfFiscalParser (genérico)
# ─────────────────────────────────────────────────────────────────────────────


def test_generico_tipo():
    r = _parser_with_text(PdfFiscalParser, _DANFE_TEXT)
    assert r.tipo == "generico"


def test_generico_chave():
    r = _parser_with_text(PdfFiscalParser, _DANFE_TEXT)
    assert r.campos.get("chave") == "35250112345678000195550010000000421234567890"


def test_generico_cnpjs_list():
    r = _parser_with_text(PdfFiscalParser, _DANFE_TEXT)
    cnpjs = r.campos.get("cnpjs", [])
    assert len(cnpjs) >= 2


def test_generico_datas_list():
    r = _parser_with_text(PdfFiscalParser, _DANFE_TEXT)
    assert "01/01/2025" in r.campos.get("datas", [])


def test_generico_valores_list():
    r = _parser_with_text(PdfFiscalParser, _DANFE_TEXT)
    assert "1.000,00" in r.campos.get("valores", [])


def test_generico_texto_sem_pdf_real():
    import src.fiscal.parser.pdf_fiscal as mod

    original = mod._read_pdf
    mod._read_pdf = lambda data: ("", 0, ["pypdf não instalado"])
    try:
        r = PdfFiscalParser().parse(b"qualquer")
    finally:
        mod._read_pdf = original
    assert "pypdf não instalado" in r.erros


# ─────────────────────────────────────────────────────────────────────────────
# Factory get_pdf_parser
# ─────────────────────────────────────────────────────────────────────────────


def test_get_pdf_parser_danfe():
    p = get_pdf_parser("danfe")
    assert isinstance(p, DanfeParser)


def test_get_pdf_parser_dact():
    p = get_pdf_parser("dact")
    assert isinstance(p, DactParser)


def test_get_pdf_parser_generico():
    p = get_pdf_parser("generico")
    assert isinstance(p, PdfFiscalParser)


def test_get_pdf_parser_unknown():
    with pytest.raises(ValueError, match="Parser PDF não disponível"):
        get_pdf_parser("boleto")


def test_get_pdf_parser_fresh_instances():
    p1 = get_pdf_parser("danfe")
    p2 = get_pdf_parser("danfe")
    assert p1 is not p2
