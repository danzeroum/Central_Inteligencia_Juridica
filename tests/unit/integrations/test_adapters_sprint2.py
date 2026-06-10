"""Testes unitários para adaptadores DataJud, DJEN, Receita CNPJ (Sprint 2)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.models import (
    AdapterStatus,
    DataMode,
    EmpresaCadastro,
    IdentifierQuery,
    IdentifierType,
    ProcessoNormalizado,
    Publicacao,
    SocioQSA,
)
from src.integrations.settings import SourceSettings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "integrations"


def _make_settings(name: str, mode: str = "real") -> SourceSettings:
    return SourceSettings(name=name, mode=mode, timeout_seconds=5)


# ---------------------------------------------------------------------------
# DataJud Adapter
# ---------------------------------------------------------------------------


class TestDataJudAdapter:
    @pytest.fixture
    def adapter(self):
        from src.integrations.adapters.datajud_adapter import DataJudAdapter

        return DataJudAdapter(_make_settings("datajud"))

    def test_supports_numero_processo(self, adapter):
        assert adapter.supports(IdentifierType.NUMERO_PROCESSO)

    def test_not_supports_cpf(self, adapter):
        assert not adapter.supports(IdentifierType.CPF)

    @pytest.mark.asyncio
    async def test_query_mock_mode(self):
        from src.integrations.adapters.datajud_adapter import DataJudAdapter

        adapter = DataJudAdapter(_make_settings("datajud", "mock"))
        q = IdentifierQuery(
            identifier="0000001-02.2020.8.26.0001",
            identifier_type=IdentifierType.NUMERO_PROCESSO,
        )
        result = await adapter.query(q)
        assert result.status == AdapterStatus.SUCCESS
        assert result.data_mode == DataMode.MOCK
        assert len(result.items) >= 0

    @pytest.mark.asyncio
    async def test_query_never_raises(self):
        from src.integrations.adapters.datajud_adapter import DataJudAdapter

        adapter = DataJudAdapter(_make_settings("datajud"))

        # Mock do DataJudClient para lançar erro
        with patch(
            "src.services.datajud_client.DataJudClient.search",
            new=AsyncMock(side_effect=Exception("Erro de rede")),
        ):
            q = IdentifierQuery(
                identifier="xxx", identifier_type=IdentifierType.NUMERO_PROCESSO
            )
            try:
                result = await adapter.query(q)
                assert result.status == AdapterStatus.FAILED
            except Exception:
                pytest.fail("query() não deve propagar exceções")


# ---------------------------------------------------------------------------
# DJEN Adapter
# ---------------------------------------------------------------------------


class TestDjenAdapter:
    @pytest.fixture
    def adapter(self):
        from src.integrations.adapters.djen_adapter import DjenAdapter

        return DjenAdapter(_make_settings("djen"))

    def test_supports_numero_processo(self, adapter):
        assert adapter.supports(IdentifierType.NUMERO_PROCESSO)

    def test_supports_nome(self, adapter):
        assert adapter.supports(IdentifierType.NOME)

    def test_supports_oab(self, adapter):
        assert adapter.supports(IdentifierType.OAB)

    @pytest.mark.asyncio
    async def test_query_mock_mode(self):
        from src.integrations.adapters.djen_adapter import DjenAdapter

        adapter = DjenAdapter(_make_settings("djen", "mock"))
        q = IdentifierQuery(identifier="Dr. Teste", identifier_type=IdentifierType.NOME)
        result = await adapter.query(q)
        assert result.status == AdapterStatus.SUCCESS
        assert result.data_mode == DataMode.MOCK

    @pytest.mark.asyncio
    async def test_query_200_parses_items(self):
        import respx
        import httpx

        fixture_data = json.loads((FIXTURES / "djen_comunica.json").read_text())

        with respx.mock:
            respx.get("https://comunicaapi.pje.jus.br/api/v1/comunicacao").mock(
                return_value=httpx.Response(200, json=fixture_data)
            )
            from src.integrations.adapters.djen_adapter import DjenAdapter

            adapter = DjenAdapter(_make_settings("djen"))
            q = IdentifierQuery(
                identifier="0001234-56.2023.8.26.0001",
                identifier_type=IdentifierType.NUMERO_PROCESSO,
            )
            result = await adapter.query(q)

        assert result.status == AdapterStatus.SUCCESS
        assert len(result.items) == 2
        pub = result.items[0]
        assert isinstance(pub, Publicacao)
        assert pub.numero_processo == "0001234-56.2023.8.26.0001"

    @pytest.mark.asyncio
    async def test_query_4xx_returns_failed(self):
        import respx
        import httpx

        with respx.mock:
            respx.get("https://comunicaapi.pje.jus.br/api/v1/comunicacao").mock(
                return_value=httpx.Response(429)
            )
            from src.integrations.adapters.djen_adapter import DjenAdapter

            adapter = DjenAdapter(_make_settings("djen"))
            q = IdentifierQuery(identifier="x", identifier_type=IdentifierType.NOME)
            result = await adapter.query(q)

        assert result.status == AdapterStatus.FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_pii_redacted_in_texto(self):
        import respx
        import httpx

        data = {
            "items": [
                {
                    "texto": "CPF do réu: 529.982.247-25 — deve ser redactado.",
                    "numeroProcesso": "000-01",
                }
            ]
        }
        with respx.mock:
            respx.get("https://comunicaapi.pje.jus.br/api/v1/comunicacao").mock(
                return_value=httpx.Response(200, json=data)
            )
            from src.integrations.adapters.djen_adapter import DjenAdapter

            adapter = DjenAdapter(_make_settings("djen"))
            q = IdentifierQuery(
                identifier="000-01", identifier_type=IdentifierType.NUMERO_PROCESSO
            )
            result = await adapter.query(q)

        assert result.status == AdapterStatus.SUCCESS
        pub = result.items[0]
        assert "529.982.247-25" not in (pub.texto or "")
        assert "[REDACTED]" in (pub.texto or "")


# ---------------------------------------------------------------------------
# Receita CNPJ Adapter
# ---------------------------------------------------------------------------


class TestReceitaCnpjAdapter:
    @pytest.fixture
    def adapter(self):
        from src.integrations.adapters.receita_cnpj_adapter import ReceitaCnpjAdapter

        return ReceitaCnpjAdapter(_make_settings("receita_cnpj"))

    def test_supports_cnpj(self, adapter):
        assert adapter.supports(IdentifierType.CNPJ)

    def test_not_supports_cpf(self, adapter):
        assert not adapter.supports(IdentifierType.CPF)

    @pytest.mark.asyncio
    async def test_query_mock_mode(self):
        from src.integrations.adapters.receita_cnpj_adapter import ReceitaCnpjAdapter

        adapter = ReceitaCnpjAdapter(_make_settings("receita_cnpj", "mock"))
        q = IdentifierQuery(
            identifier="00000000000191", identifier_type=IdentifierType.CNPJ
        )
        result = await adapter.query(q)
        assert result.status == AdapterStatus.SUCCESS
        assert result.data_mode == DataMode.MOCK

    @pytest.mark.asyncio
    async def test_query_200_parses_empresa(self):
        import respx
        import httpx

        fixture_data = json.loads((FIXTURES / "brasilapi_cnpj.json").read_text())

        with respx.mock:
            respx.get("https://brasilapi.com.br/api/cnpj/v1/00000000000191").mock(
                return_value=httpx.Response(200, json=fixture_data)
            )
            from src.integrations.adapters.receita_cnpj_adapter import (
                ReceitaCnpjAdapter,
            )

            adapter = ReceitaCnpjAdapter(_make_settings("receita_cnpj"))
            q = IdentifierQuery(
                identifier="00.000.000/0001-91",
                identifier_type=IdentifierType.CNPJ,
            )
            result = await adapter.query(q)

        assert result.status == AdapterStatus.SUCCESS
        assert len(result.items) == 1
        empresa = result.items[0]
        assert isinstance(empresa, EmpresaCadastro)
        assert empresa.situacao_cadastral == "ATIVA"
        assert empresa.capital_social == 500000.0

    @pytest.mark.asyncio
    async def test_qsa_parsed_correctly(self):
        import respx
        import httpx

        fixture_data = json.loads((FIXTURES / "brasilapi_cnpj.json").read_text())

        with respx.mock:
            respx.get("https://brasilapi.com.br/api/cnpj/v1/00000000000191").mock(
                return_value=httpx.Response(200, json=fixture_data)
            )
            from src.integrations.adapters.receita_cnpj_adapter import (
                ReceitaCnpjAdapter,
            )

            adapter = ReceitaCnpjAdapter(_make_settings("receita_cnpj"))
            q = IdentifierQuery(
                identifier="00000000000191", identifier_type=IdentifierType.CNPJ
            )
            result = await adapter.query(q)

        empresa = result.items[0]
        assert len(empresa.qsa) == 2
        pf_socio = next(s for s in empresa.qsa if s.tipo == "PF")
        pj_socio = next(s for s in empresa.qsa if s.tipo == "PJ")
        assert pf_socio.nome == "João Teste da Silva"
        assert pj_socio.nome == "Empresa Parceira SA"

    @pytest.mark.asyncio
    async def test_query_5xx_returns_failed(self):
        import respx
        import httpx

        with respx.mock:
            respx.get("https://brasilapi.com.br/api/cnpj/v1/00000000000191").mock(
                return_value=httpx.Response(500)
            )
            from src.integrations.adapters.receita_cnpj_adapter import (
                ReceitaCnpjAdapter,
            )

            adapter = ReceitaCnpjAdapter(_make_settings("receita_cnpj"))
            q = IdentifierQuery(
                identifier="00000000000191", identifier_type=IdentifierType.CNPJ
            )
            result = await adapter.query(q)

        assert result.status == AdapterStatus.FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_query_timeout_returns_failed(self):
        import respx
        import httpx

        with respx.mock:
            respx.get("https://brasilapi.com.br/api/cnpj/v1/00000000000191").mock(
                side_effect=httpx.TimeoutException("timeout")
            )
            from src.integrations.adapters.receita_cnpj_adapter import (
                ReceitaCnpjAdapter,
            )

            adapter = ReceitaCnpjAdapter(_make_settings("receita_cnpj"))
            q = IdentifierQuery(
                identifier="00000000000191", identifier_type=IdentifierType.CNPJ
            )
            result = await adapter.query(q)

        assert result.status == AdapterStatus.FAILED

    @pytest.mark.asyncio
    async def test_malformed_payload_returns_failed(self):
        import respx
        import httpx

        with respx.mock:
            respx.get("https://brasilapi.com.br/api/cnpj/v1/00000000000191").mock(
                return_value=httpx.Response(200, text="not-json{{{")
            )
            from src.integrations.adapters.receita_cnpj_adapter import (
                ReceitaCnpjAdapter,
            )

            adapter = ReceitaCnpjAdapter(_make_settings("receita_cnpj"))
            q = IdentifierQuery(
                identifier="00000000000191", identifier_type=IdentifierType.CNPJ
            )
            result = await adapter.query(q)

        assert result.status == AdapterStatus.FAILED

    @pytest.mark.asyncio
    async def test_query_never_raises(self):
        import respx
        import httpx

        with respx.mock:
            respx.get("https://brasilapi.com.br/api/cnpj/v1/00000000000191").mock(
                side_effect=RuntimeError("Unexpected crash")
            )
            from src.integrations.adapters.receita_cnpj_adapter import (
                ReceitaCnpjAdapter,
            )

            adapter = ReceitaCnpjAdapter(_make_settings("receita_cnpj"))
            q = IdentifierQuery(
                identifier="00000000000191", identifier_type=IdentifierType.CNPJ
            )
            # Nunca deve levantar exceção
            try:
                result = await adapter.query(q)
                assert result.status == AdapterStatus.FAILED
            except Exception:
                pytest.fail("query() não deve propagar exceções")
