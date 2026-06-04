"""Testes da camada DataJud (Frente F.1) — query builder, cliente e serviço.

Os testes de rede usam ``respx`` para mockar o ElasticSearch do DataJud: são
determinísticos e não dependem de rede externa nem da ``DATAJUD_API_KEY`` real.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402

from src.services.datajud_client import DataJudClient  # noqa: E402
from src.services.datajud_query_builder import DataJudQueryBuilder  # noqa: E402
from src.services.datajud_service import (  # noqa: E402
    DataJudService,
    register_datajud_tools,
)
from src.tools.circuit_breaker import CircuitBreaker, CircuitBreakerConfig  # noqa: E402
from src.tools.mcp_registry import MCPToolRegistry  # noqa: E402

_ENDPOINT = "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"

_ES_RESPONSE = {
    "hits": {
        "total": {"value": 2},
        "hits": [
            {
                "_source": {
                    "numeroProcesso": "00008323520184013202",
                    "tribunal": "TJSP",
                    "grau": "G1",
                    "assuntos": [{"codigo": 2086, "nome": "Rescisão"}],
                    "campoExtra": "preservado",
                }
            },
            {"_source": {"numeroProcesso": "00009999520184013202", "tribunal": "TJSP"}},
        ],
    }
}


# ── Query Builder ────────────────────────────────────────────────────────────
def test_builder_compoe_bool_filter_must_not():
    query = (
        DataJudQueryBuilder()
        .with_numero_processo("123")
        .with_assuntos([2086, 2087])
        .excluir_movimentos([246])
        .pagina(7)
        .build()
    )
    bool_block = query["query"]["bool"]
    assert {"match": {"numeroProcesso": "123"}} in bool_block["must"]
    assert {"terms": {"assuntos.codigo": [2086, 2087]}} in bool_block["filter"]
    assert {"terms": {"movimentos.codigo": [246]}} in bool_block["must_not"]
    assert query["size"] == 7


def test_builder_search_after_present_only_quando_definido():
    assert "search_after" not in DataJudQueryBuilder().build()
    q = DataJudQueryBuilder().pagina(10, after=["x"]).build()
    assert q["search_after"] == ["x"]


# ── Cliente: fallback sem chave ──────────────────────────────────────────────
async def test_search_sem_chave_usa_mock():
    client = DataJudClient("tjsp", api_key=None)
    result = await client.search(DataJudQueryBuilder().build())
    assert result.source == "simulated"
    assert result.fallback is True
    assert result.reason == "sem_api_key"


# ── Cliente: sucesso com API real (mockada) ──────────────────────────────────
@respx.mock
async def test_search_real_api_sucesso():
    route = respx.post(_ENDPOINT).mock(
        return_value=httpx.Response(200, json=_ES_RESPONSE)
    )
    client = DataJudClient("tjsp", api_key="chave-de-teste")
    result = await client.search(DataJudQueryBuilder().with_assuntos([2086]).build())

    assert route.called
    # Header de autenticação no formato esperado pelo DataJud.
    assert route.calls.last.request.headers["Authorization"] == "APIKey chave-de-teste"
    assert result.source == "real_api"
    assert result.fallback is False
    assert result.total == 2
    assert result.processos[0].numeroProcesso == "00008323520184013202"
    # extra="allow" preserva campos não modelados.
    assert result.processos[0].model_dump()["campoExtra"] == "preservado"


# ── Cliente: erro HTTP → fallback gracioso ───────────────────────────────────
@respx.mock
async def test_search_http_error_faz_fallback():
    respx.post(_ENDPOINT).mock(return_value=httpx.Response(500))
    client = DataJudClient("tjsp", api_key="chave-de-teste")
    result = await client.search(DataJudQueryBuilder().build())
    assert result.source == "simulated"
    assert result.fallback is True


# ── Cliente: circuit breaker abre após falhas ────────────────────────────────
@respx.mock
async def test_circuit_breaker_abre_apos_falhas():
    respx.post(_ENDPOINT).mock(return_value=httpx.Response(503))
    breaker = CircuitBreaker(
        config=CircuitBreakerConfig(
            name="datajud_test",
            failure_threshold=2,
            recovery_timeout=30.0,
            success_threshold=1,
            half_open_max_calls=1,
        )
    )
    client = DataJudClient("tjsp", api_key="k", breaker=breaker)

    for _ in range(2):
        await client.search(DataJudQueryBuilder().build())

    assert breaker.is_open()
    # Próxima chamada nem toca a rede: cai no mock com motivo circuit_open.
    result = await client.search(DataJudQueryBuilder().build())
    assert result.source == "simulated"
    assert result.reason == "circuit_open"


# ── Serviço: monta a query certa e delega ao cliente ─────────────────────────
async def test_service_buscar_por_assunto(monkeypatch):
    captured = {}

    class _FakeClient:
        def __init__(self, alias):
            self.alias = alias

        async def search(self, query):
            captured["alias"] = self.alias
            captured["query"] = query
            from src.services.datajud_schemas import DataJudSearchResult

            return DataJudSearchResult(total=0, alias=self.alias)

    service = DataJudService(client_factory=_FakeClient)
    await service.buscar_por_assunto("trf1", [2086], grau="G2", size=3)

    assert captured["alias"] == "trf1"
    bool_block = captured["query"]["query"]["bool"]
    assert {"terms": {"assuntos.codigo": [2086]}} in bool_block["filter"]
    assert {"match": {"grau": "G2"}} in bool_block["filter"]
    assert captured["query"]["size"] == 3


# ── Tools MCP registradas ────────────────────────────────────────────────────
async def test_registro_de_tools_mcp():
    registry = MCPToolRegistry()

    class _FakeClient:
        def __init__(self, alias):
            self.alias = alias

        async def search(self, query):
            from src.services.datajud_schemas import DataJudSearchResult

            return DataJudSearchResult(total=1, source="real_api", alias=self.alias)

    register_datajud_tools(registry, DataJudService(client_factory=_FakeClient))

    assert "datajud_buscar_processo" in registry.tools
    assert "datajud_buscar_por_assunto" in registry.tools
    assert "datajud_monitorar_atualizacoes" in registry.tools

    result = await registry.execute("datajud_buscar_processo", "tjsp", "123")
    assert result.alias == "tjsp"
    assert result.total == 1
