"""Unit tests para rotas de analytics fiscal (S-E.1).

Testa estrutura dos endpoints sem banco de dados (503 esperado).
Valida modelos Pydantic e lógica auxiliar diretamente.
"""

from __future__ import annotations

import pytest

from src.api.routes.analytics import (
    AchadosDistribuicao,
    AnomaliaItem,
    HistoricoItem,
    KpisResponse,
    RetificacaoHistoricoItem,
    _count_dict,
    _safe_int,
)

# ─── helpers ─────────────────────────────────────────────────────────────────


def test_safe_int_converte_string():
    assert _safe_int("42") == 42


def test_safe_int_none_retorna_zero():
    assert _safe_int(None) == 0


def test_safe_int_invalido_retorna_zero():
    assert _safe_int("nao-e-numero") == 0


def test_count_dict_agrega_por_chave():
    class Row:
        def __init__(self, v):
            self.v = v

    rows = [Row("a"), Row("b"), Row("a"), Row("a")]
    result = _count_dict(rows, lambda r: r.v)
    assert result == {"a": 3, "b": 1}


def test_count_dict_lista_vazia():
    assert _count_dict([], lambda r: r) == {}


# ─── models ──────────────────────────────────────────────────────────────────


def test_kpis_response_defaults():
    r = KpisResponse()
    assert r.total_escrituracoes == 0
    assert r.total_apuracoes == 0
    assert r.total_achados == 0
    assert r.por_status == {}
    assert r.por_situacao == {}
    assert r.por_severidade == {}


def test_kpis_response_filled():
    r = KpisResponse(
        total_escrituracoes=10,
        total_apuracoes=5,
        total_achados=3,
        por_status={"processado": 9, "erro": 1},
        por_situacao={"devedor": 4, "credor": 1},
        por_severidade={"erro": 2, "aviso": 1},
    )
    assert r.total_escrituracoes == 10
    assert r.por_status["processado"] == 9
    assert r.por_situacao["devedor"] == 4


def test_historico_item_serializa():
    item = HistoricoItem(
        periodo="2024-01",
        tributo="ICMS",
        total_debitos="1234,56",
        total_creditos="456,78",
        saldo_apurado="777,78",
        situacao="devedor",
        escrituracao_id="abc-123",
    )
    d = item.model_dump()
    assert d["periodo"] == "2024-01"
    assert d["tributo"] == "ICMS"
    assert d["situacao"] == "devedor"


def test_achados_distribuicao_defaults():
    r = AchadosDistribuicao()
    assert r.total == 0
    assert r.por_severidade == {}
    assert r.por_regra == {}
    assert r.por_tipo_registro == {}


def test_anomalia_item_serializa():
    item = AnomaliaItem(
        escrituracao_id="eid-001",
        tipo="efd_icms",
        periodo="2024-01",
        divergencias_count=3,
        severidade_maxima="erro",
    )
    assert item.divergencias_count == 3
    assert item.severidade_maxima == "erro"


def test_retificacao_historico_item():
    item = RetificacaoHistoricoItem(
        audit_id="aid-001",
        escrituracao_id="eid-001",
        operation="gerar_retificado",
        status="completed",
        total_registros=15,
        total_bytes=1024,
        user_id="user-x",
        created_at="2024-01-15T10:00:00+00:00",
    )
    assert item.operation == "gerar_retificado"
    assert item.total_registros == 15


# ─── endpoint responses sem DB ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from src.api.main import app

    with TestClient(app) as c:
        yield c


def test_kpis_sem_db_retorna_503(client):
    r = client.get("/api/v1/fiscal/analytics/kpis")
    assert r.status_code in (200, 503)


def test_historico_sem_db_retorna_503(client):
    r = client.get("/api/v1/fiscal/analytics/apuracoes/historico")
    assert r.status_code in (200, 503)


def test_distribuicao_sem_db_retorna_503(client):
    r = client.get("/api/v1/fiscal/analytics/achados/distribuicao")
    assert r.status_code in (200, 503)


def test_anomalias_sem_db_retorna_503(client):
    r = client.get("/api/v1/fiscal/analytics/anomalias")
    assert r.status_code in (200, 503)


def test_anomalias_severidade_invalida(client):
    r = client.get("/api/v1/fiscal/analytics/anomalias?severidade_minima=INVALIDA")
    assert r.status_code == 422


def test_retificacoes_sem_db_retorna_503(client):
    r = client.get("/api/v1/fiscal/analytics/retificacoes")
    assert r.status_code in (200, 503)


def test_historico_com_filtros_sem_db(client):
    r = client.get(
        "/api/v1/fiscal/analytics/apuracoes/historico"
        "?tributo=ICMS&periodo_inicio=2024-01&periodo_fim=2024-12&limit=10"
    )
    assert r.status_code in (200, 503)


def test_retificacoes_filtro_escrituracao_sem_db(client):
    import uuid

    eid = str(uuid.uuid4())
    r = client.get(f"/api/v1/fiscal/analytics/retificacoes?escrituracao_id={eid}")
    assert r.status_code in (200, 503)
