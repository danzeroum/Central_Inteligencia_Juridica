"""Testes unitários para S-D.2 — Retificação SPED ponta-a-ponta.

Cobre:
  - comparador.py: lógica de diff de registros canônicos
  - layout_validator.py: validação de contagem de campos EFD ICMS/IPI v3.1.5
  - routes/retificacao.py: endpoints via TestClient (sem banco)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.fiscal.retificacao.comparador import (
    ComparacaoRetificacao,
    comparar_registros,
)
from src.fiscal.writer.layout_validator import ErroLayout, validar_layout

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _reg(tipo: str, linha: int, **dados) -> dict:
    return {"tipo_registro": tipo, "numero_linha": linha, "dados": dados or None}


ORIGINAIS = [
    _reg("C100", 10, VL_DOC="1000.00", NUM_DOC="001"),
    _reg("C190", 11, CST_ICMS="00", VL_BC_ICMS="1000.00"),
    _reg("E110", 20, VL_TOT_DEBITOS="500.00"),
]

RETIFICADOS_SEM_DIFF = [
    _reg("C100", 10, VL_DOC="1000.00", NUM_DOC="001"),
    _reg("C190", 11, CST_ICMS="00", VL_BC_ICMS="1000.00"),
    _reg("E110", 20, VL_TOT_DEBITOS="500.00"),
]

RETIFICADOS_COM_DIFF = [
    _reg("C100", 10, VL_DOC="1500.00", NUM_DOC="001"),  # modificado
    _reg("C190", 11, CST_ICMS="00", VL_BC_ICMS="1000.00"),  # igual
    # E110 linha 20 removido
    _reg("E110", 21, VL_TOT_DEBITOS="600.00"),  # adicionado
]


# ─────────────────────────────────────────────────────────────────────────────
# Testes do comparador
# ─────────────────────────────────────────────────────────────────────────────


def test_comparar_sem_diferencas():
    resultado = comparar_registros(ORIGINAIS, RETIFICADOS_SEM_DIFF)
    assert isinstance(resultado, ComparacaoRetificacao)
    assert not resultado.tem_diferencas
    assert resultado.total_alteracoes == 0
    assert resultado.adicionados == []
    assert resultado.removidos == []
    assert resultado.modificados == []


def test_comparar_com_diferencas():
    resultado = comparar_registros(ORIGINAIS, RETIFICADOS_COM_DIFF)
    assert resultado.tem_diferencas
    assert len(resultado.adicionados) == 1
    assert len(resultado.removidos) == 1
    assert len(resultado.modificados) == 1


def test_comparar_modificacao_campos():
    resultado = comparar_registros(ORIGINAIS, RETIFICADOS_COM_DIFF)
    mod = resultado.modificados[0]
    assert mod.tipo_registro == "C100"
    assert mod.numero_linha == 10
    assert "VL_DOC" in mod.campos_alterados
    orig_val, ret_val = mod.campos_alterados["VL_DOC"]
    assert orig_val == "1000.00"
    assert ret_val == "1500.00"


def test_comparar_adicionado_e_removido():
    resultado = comparar_registros(ORIGINAIS, RETIFICADOS_COM_DIFF)
    tipos_add = [r.get("tipo_registro") for r in resultado.adicionados]
    tipos_rem = [r.get("tipo_registro") for r in resultado.removidos]
    assert "E110" in tipos_add
    assert "E110" in tipos_rem


def test_to_dict_estrutura():
    resultado = comparar_registros(ORIGINAIS, RETIFICADOS_COM_DIFF)
    d = resultado.to_dict()
    assert "tem_diferencas" in d
    assert "total_alteracoes" in d
    assert "adicionados" in d
    assert "removidos" in d
    assert "modificados" in d
    assert d["total_alteracoes"] == 3


def test_resumo_mudancas():
    resultado = comparar_registros(ORIGINAIS, RETIFICADOS_COM_DIFF)
    resumo = resultado.resumo_mudancas()
    assert resumo["total_adicionados"] == 1
    assert resumo["total_removidos"] == 1
    assert resumo["total_modificados"] == 1
    assert "E110" in resumo["tipos_afetados"]


def test_comparar_listas_vazias():
    resultado = comparar_registros([], [])
    assert not resultado.tem_diferencas


def test_comparar_todos_adicionados():
    resultado = comparar_registros([], ORIGINAIS)
    assert len(resultado.adicionados) == 3
    assert resultado.removidos == []
    assert resultado.modificados == []


def test_comparar_todos_removidos():
    resultado = comparar_registros(ORIGINAIS, [])
    assert resultado.adicionados == []
    assert len(resultado.removidos) == 3
    assert resultado.modificados == []


# ─────────────────────────────────────────────────────────────────────────────
# Testes do layout_validator
# ─────────────────────────────────────────────────────────────────────────────


def test_layout_valido_com_raw():
    # C100 espera 26 campos
    records = [{"tipo_registro": "C100", "dados": {"_raw": list(range(26))}}]
    resultado = validar_layout(records)
    assert resultado.valido
    assert resultado.total_registros == 1
    assert resultado.registros_validados == 1
    assert resultado.erros == []


def test_layout_invalido_campos_errados():
    # C100 espera 26, passamos 10
    records = [{"tipo_registro": "C100", "dados": {"_raw": list(range(10))}}]
    resultado = validar_layout(records)
    assert not resultado.valido
    assert len(resultado.erros) == 1
    erro = resultado.erros[0]
    assert isinstance(erro, ErroLayout)
    assert erro.tipo_registro == "C100"
    assert erro.campos_esperados == 26
    assert erro.campos_encontrados == 10


def test_layout_tipo_desconhecido_gera_aviso():
    records = [{"tipo_registro": "ZZZZ", "dados": {"_raw": [1, 2, 3]}}]
    resultado = validar_layout(records)
    assert resultado.valido
    assert len(resultado.avisos) == 1
    assert "ZZZZ" in resultado.avisos[0]
    assert resultado.registros_validados == 0


def test_layout_sem_raw_conta_chaves():
    # 0001 espera 2 campos (tipo + 1 dado)
    records = [{"tipo_registro": "0001", "dados": {"IND_MOV": "0"}}]
    resultado = validar_layout(records)
    # dados tem 1 chave → +1 = 2 → correto
    assert resultado.valido


def test_layout_to_dict():
    records = [{"tipo_registro": "9999", "dados": {"_raw": [1, 2]}}]
    resultado = validar_layout(records)
    d = resultado.to_dict()
    assert "valido" in d
    assert "total_registros" in d
    assert "registros_validados" in d
    assert "erros" in d
    assert "avisos" in d


# ─────────────────────────────────────────────────────────────────────────────
# Testes dos endpoints (TestClient)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from src.api.app_factory import create_app

    app = create_app()
    return TestClient(app, raise_server_exceptions=True)


def test_endpoint_comparar_sem_diff(client):
    payload = {
        "registros_originais": [
            {"tipo_registro": "C100", "numero_linha": 1, "dados": {"VL_DOC": "100"}}
        ],
        "registros_retificados": [
            {"tipo_registro": "C100", "numero_linha": 1, "dados": {"VL_DOC": "100"}}
        ],
    }
    resp = client.post("/api/v1/fiscal/retificacao/comparar", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tem_diferencas"] is False
    assert data["total_alteracoes"] == 0


def test_endpoint_comparar_com_diff(client):
    payload = {
        "registros_originais": [
            {"tipo_registro": "C100", "numero_linha": 1, "dados": {"VL_DOC": "100"}}
        ],
        "registros_retificados": [
            {"tipo_registro": "C100", "numero_linha": 1, "dados": {"VL_DOC": "200"}}
        ],
    }
    resp = client.post("/api/v1/fiscal/retificacao/comparar", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tem_diferencas"] is True
    assert len(data["modificados"]) == 1


def test_endpoint_validar_layout_ok(client):
    payload = {
        "registros": [
            {
                "tipo_registro": "9999",
                "numero_linha": 1,
                "dados": {"_raw": [1, 2]},
            }
        ]
    }
    resp = client.post("/api/v1/fiscal/retificacao/validar-layout", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valido"] is True


def test_endpoint_validar_layout_erro(client):
    payload = {
        "registros": [
            {
                "tipo_registro": "C100",
                "numero_linha": 1,
                "dados": {"_raw": [1, 2]},  # espera 26, deu 2
            }
        ]
    }
    resp = client.post("/api/v1/fiscal/retificacao/validar-layout", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valido"] is False
    assert len(data["erros"]) == 1


def test_endpoint_nota_correcao_simulada(client):
    """Sem DATABASE_URL → retorna simulado=True."""
    import os

    os.environ.pop("DATABASE_URL", None)

    payload = {
        "escrituracao_original_id": "00000000-0000-0000-0000-000000000001",
        "escrituracao_retificada_id": "00000000-0000-0000-0000-000000000002",
        "motivo": "Correção de valor de ICMS no registro C100.",
    }
    resp = client.post("/api/v1/fiscal/retificacao/nota-correcao", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["simulado"] is True
    assert "id" in data
    assert data["motivo"] == payload["motivo"]


def test_endpoint_nota_correcao_uuid_invalido(client):
    payload = {
        "escrituracao_original_id": "nao-e-uuid",
        "escrituracao_retificada_id": "00000000-0000-0000-0000-000000000002",
        "motivo": "Teste.",
    }
    resp = client.post("/api/v1/fiscal/retificacao/nota-correcao", json=payload)
    assert resp.status_code == 422
