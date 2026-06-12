"""Unit tests for SpedWriter (S-D.1).

Cálculos manuais:
  - _to_line produz |TIPO|c1|c2|...|cn|
  - gerar() une linhas com CRLF e retorna bytes UTF-8
  - 0000.cod_fin="1" quando ind_ret=True
  - 9999.qdt_lins = total de linhas (contagem real após geração)
"""

from __future__ import annotations

import pytest

from src.fiscal.writer.sped_writer import SpedWriter


@pytest.fixture
def writer() -> SpedWriter:
    return SpedWriter()


# ─── _to_line ────────────────────────────────────────────────────────────────


def test_to_line_named_campos(writer: SpedWriter) -> None:
    """Campos nomeados são emitidos na ordem de inserção do dict."""
    dados = {"cod_ver": "015", "cod_fin": "0", "dt_ini": "2024-01-01"}
    line = writer._to_line("0000", dados)
    assert line == "|0000|015|0|2024-01-01|"


def test_to_line_raw_campos(writer: SpedWriter) -> None:
    """_raw usa lista bruta sem remapeamento de chaves."""
    dados = {"_raw": ["9900", "15"]}
    line = writer._to_line("9900", dados)
    assert line == "|9900|9900|15|"


def test_to_line_none_values(writer: SpedWriter) -> None:
    """Valores None são emitidos como string vazia."""
    dados = {"campo_a": "X", "campo_b": None, "campo_c": "Z"}
    line = writer._to_line("C100", dados)
    assert line == "|C100|X||Z|"


def test_to_line_empty_dados(writer: SpedWriter) -> None:
    """Registro sem campos gera linha com apenas o tipo entre pipes."""
    line = writer._to_line("C001", {})
    assert line == "|C001|"


# ─── gerar() básico ──────────────────────────────────────────────────────────


def _make_records() -> list:
    return [
        {
            "tipo_registro": "0000",
            "dados": {
                "cod_ver": "015",
                "cod_fin": "0",
                "dt_ini": "2024-01-01",
                "dt_fin": "2024-01-31",
                "nome": "EMPRESA TESTE",
                "cnpj": "12345678000195",
                "cpf": "",
                "uf": "SP",
                "ie": "111222333",
                "cod_mun": "3550308",
                "im": "",
                "suframa": "",
                "ind_perfil": "A",
                "ind_ativ": "0",
            },
        },
        {
            "tipo_registro": "0001",
            "dados": {"ind_mov": "0"},
        },
        {
            "tipo_registro": "0990",
            "dados": {"qt_lin": "3"},
        },
        {
            "tipo_registro": "9001",
            "dados": {"ind_mov": "0"},
        },
        {
            "tipo_registro": "9999",
            "dados": {"qdt_lins": "5"},
        },
    ]


def test_gerar_ind_ret_seta_cod_fin(writer: SpedWriter) -> None:
    """gerar(ind_ret=True) muda 0000.cod_fin para '1'."""
    records = _make_records()
    output = writer.gerar(records, ind_ret=True).decode("utf-8")
    lines = output.split("\r\n")
    linha_0000 = lines[0]
    partes = linha_0000.split("|")
    # partes[0]="" partes[1]="0000" partes[2]=cod_ver partes[3]=cod_fin
    assert partes[3] == "1", f"cod_fin deve ser '1', got {partes[3]!r}"


def test_gerar_ind_ret_false_preserva_cod_fin(writer: SpedWriter) -> None:
    """gerar(ind_ret=False) não altera cod_fin."""
    records = _make_records()
    output = writer.gerar(records, ind_ret=False).decode("utf-8")
    lines = output.split("\r\n")
    partes = lines[0].split("|")
    assert partes[3] == "0"


def test_gerar_9999_atualiza_total(writer: SpedWriter) -> None:
    """9999.qdt_lins reflete o total real de linhas geradas (5 neste fixture)."""
    records = _make_records()
    output = writer.gerar(records, ind_ret=True).decode("utf-8")
    lines = output.split("\r\n")
    assert len(lines) == 5  # sanidade: 5 registros
    ultima = lines[-1]
    # |9999|5|
    partes = ultima.split("|")
    assert partes[1] == "9999"
    assert partes[2] == "5"


def test_gerar_crlf_separador(writer: SpedWriter) -> None:
    """Linhas são separadas por CRLF (\\r\\n), não LF."""
    records = _make_records()
    raw = writer.gerar(records, ind_ret=False)
    assert b"\r\n" in raw
    assert raw.count(b"\r\n") == 4  # 5 linhas → 4 separadores


def test_gerar_9999_raw_atualiza_total(writer: SpedWriter) -> None:
    """9999 com _raw também é atualizado com o total de linhas."""
    records = [
        {"tipo_registro": "0000", "dados": {"cod_fin": "0"}},
        {"tipo_registro": "9999", "dados": {"_raw": ["999"]}},  # valor antigo
    ]
    output = writer.gerar(records, ind_ret=True).decode("utf-8")
    lines = output.split("\r\n")
    ultima = lines[-1]
    # |9999|2|  (2 linhas no total)
    partes = ultima.split("|")
    assert partes[2] == "2"


def test_gerar_sem_9999_nao_falha(writer: SpedWriter) -> None:
    """Arquivo sem registro 9999 é gerado sem erro."""
    records = [
        {"tipo_registro": "0000", "dados": {"cod_fin": "0"}},
        {"tipo_registro": "0001", "dados": {"ind_mov": "1"}},
    ]
    output = writer.gerar(records, ind_ret=True).decode("utf-8")
    lines = output.split("\r\n")
    assert len(lines) == 2


def test_gerar_bytes_utf8(writer: SpedWriter) -> None:
    """Saída é UTF-8 com caracteres acentuados preservados."""
    records = [
        {
            "tipo_registro": "0000",
            "dados": {"nome": "AÇÚCAR E CIA LTDA", "cod_fin": "0"},
        },
        {"tipo_registro": "9999", "dados": {"qdt_lins": "1"}},
    ]
    raw = writer.gerar(records, ind_ret=False)
    assert isinstance(raw, bytes)
    decoded = raw.decode("utf-8")
    assert "AÇÚCAR E CIA LTDA" in decoded
