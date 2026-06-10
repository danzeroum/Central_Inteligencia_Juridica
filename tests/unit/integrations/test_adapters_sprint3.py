"""Testes unitários para adaptadores TSE, CRC, Cadin, ONR (Sprint 3)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.integrations.models import (
    AdapterStatus,
    CandidaturaTSE,
    DataMode,
    IdentifierQuery,
    IdentifierType,
    Imovel,
    PendenciaCadin,
    Protesto,
)
from src.integrations.settings import SourceSettings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "integrations"


def _settings(name: str, mode: str = "real") -> SourceSettings:
    return SourceSettings(name=name, mode=mode, timeout_seconds=5)


# ---------------------------------------------------------------------------
# TSE Adapter
# ---------------------------------------------------------------------------

class TestTseAdapter:
    def test_supports_cpf(self):
        from src.integrations.adapters.tse_adapter import TseAdapter
        a = TseAdapter(_settings("tse"))
        assert a.supports(IdentifierType.CPF)

    def test_supports_nome(self):
        from src.integrations.adapters.tse_adapter import TseAdapter
        a = TseAdapter(_settings("tse"))
        assert a.supports(IdentifierType.NOME)

    @pytest.mark.asyncio
    async def test_mock_mode(self):
        from src.integrations.adapters.tse_adapter import TseAdapter
        a = TseAdapter(_settings("tse", "mock"))
        q = IdentifierQuery(identifier="João", identifier_type=IdentifierType.NOME)
        result = await a.query(q)
        assert result.status == AdapterStatus.SUCCESS
        assert result.data_mode == DataMode.MOCK

    @pytest.mark.asyncio
    async def test_real_200_parses(self):
        import respx
        import httpx
        from src.integrations.adapters.tse_adapter import TseAdapter

        fixture = json.loads((FIXTURES / "tse_ckan_search.json").read_text())
        with respx.mock:
            respx.get("https://dadosabertos.tse.jus.br/api/3/action/datastore_search").mock(
                return_value=httpx.Response(200, json=fixture)
            )
            a = TseAdapter(_settings("tse"))
            q = IdentifierQuery(identifier="52998224725", identifier_type=IdentifierType.CPF)
            result = await a.query(q)

        assert result.status == AdapterStatus.SUCCESS
        assert len(result.items) == 1
        candidatura = result.items[0]
        assert isinstance(candidatura, CandidaturaTSE)
        assert candidatura.partido == "PSD"
        # CPF deve ser mascarado
        assert "529" not in (candidatura.cpf or "")

    @pytest.mark.asyncio
    async def test_real_error_returns_failed(self):
        import respx
        import httpx
        from src.integrations.adapters.tse_adapter import TseAdapter

        with respx.mock:
            respx.get("https://dadosabertos.tse.jus.br/api/3/action/datastore_search").mock(
                return_value=httpx.Response(500)
            )
            a = TseAdapter(_settings("tse"))
            q = IdentifierQuery(identifier="João", identifier_type=IdentifierType.NOME)
            result = await a.query(q)

        assert result.status == AdapterStatus.FAILED


# ---------------------------------------------------------------------------
# CRC Protestos Adapter
# ---------------------------------------------------------------------------

class TestCrcProtestosAdapter:
    def test_supports_cpf_cnpj(self):
        from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter
        a = CrcProtestosAdapter(_settings("crc_protestos", "mock"))
        assert a.supports(IdentifierType.CPF)
        assert a.supports(IdentifierType.CNPJ)

    @pytest.mark.asyncio
    async def test_mock_mode_returns_success(self):
        from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter
        a = CrcProtestosAdapter(_settings("crc_protestos", "mock"))
        q = IdentifierQuery(identifier="00000000000191", identifier_type=IdentifierType.CNPJ)
        result = await a.query(q)
        assert result.status == AdapterStatus.SUCCESS
        assert result.data_mode == DataMode.MOCK
        assert len(result.items) > 0
        assert isinstance(result.items[0], Protesto)

    @pytest.mark.asyncio
    async def test_real_mode_returns_failed_not_raises(self):
        from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter
        a = CrcProtestosAdapter(_settings("crc_protestos", "real"))
        q = IdentifierQuery(identifier="00000000000191", identifier_type=IdentifierType.CNPJ)
        result = await a.query(q)
        # real mode não implementado → FAILED com error="real_mode_unavailable"
        assert result.status == AdapterStatus.FAILED
        assert result.error == "real_mode_unavailable"


# ---------------------------------------------------------------------------
# Cadin Adapter
# ---------------------------------------------------------------------------

class TestCadinAdapter:
    @pytest.mark.asyncio
    async def test_mock_mode_returns_pendencias(self):
        from src.integrations.adapters.cadin_adapter import CadinAdapter
        a = CadinAdapter(_settings("cadin", "mock"))
        q = IdentifierQuery(identifier="52998224725", identifier_type=IdentifierType.CPF)
        result = await a.query(q)
        assert result.status == AdapterStatus.SUCCESS
        assert result.data_mode == DataMode.MOCK
        assert isinstance(result.items[0], PendenciaCadin)

    @pytest.mark.asyncio
    async def test_real_mode_unavailable(self):
        from src.integrations.adapters.cadin_adapter import CadinAdapter
        a = CadinAdapter(_settings("cadin", "real"))
        q = IdentifierQuery(identifier="52998224725", identifier_type=IdentifierType.CPF)
        result = await a.query(q)
        assert result.status == AdapterStatus.FAILED
        assert result.error == "real_mode_unavailable"


# ---------------------------------------------------------------------------
# ONR Imóveis Adapter
# ---------------------------------------------------------------------------

class TestOnrImoveisAdapter:
    @pytest.mark.asyncio
    async def test_mock_mode_returns_imoveis(self):
        from src.integrations.adapters.onr_imoveis_adapter import OnrImoveisAdapter
        a = OnrImoveisAdapter(_settings("onr_imoveis", "mock"))
        q = IdentifierQuery(identifier="52998224725", identifier_type=IdentifierType.CPF)
        result = await a.query(q)
        assert result.status == AdapterStatus.SUCCESS
        assert result.data_mode == DataMode.MOCK
        assert isinstance(result.items[0], Imovel)

    @pytest.mark.asyncio
    async def test_real_mode_unavailable(self):
        from src.integrations.adapters.onr_imoveis_adapter import OnrImoveisAdapter
        a = OnrImoveisAdapter(_settings("onr_imoveis", "real"))
        q = IdentifierQuery(identifier="52998224725", identifier_type=IdentifierType.CPF)
        result = await a.query(q)
        assert result.status == AdapterStatus.FAILED
        assert result.error == "real_mode_unavailable"


# ---------------------------------------------------------------------------
# Teste da Matriz supported_identifiers de todos os 7 adaptadores
# ---------------------------------------------------------------------------

class TestAdapterMatrix:
    """Verifica que a matriz de supported_identifiers está correta para todos os adapters."""

    def _get_all_adapters(self):
        from src.integrations.adapters.datajud_adapter import DataJudAdapter
        from src.integrations.adapters.djen_adapter import DjenAdapter
        from src.integrations.adapters.receita_cnpj_adapter import ReceitaCnpjAdapter
        from src.integrations.adapters.tse_adapter import TseAdapter
        from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter
        from src.integrations.adapters.cadin_adapter import CadinAdapter
        from src.integrations.adapters.onr_imoveis_adapter import OnrImoveisAdapter

        return [
            DataJudAdapter(_settings("datajud", "mock")),
            DjenAdapter(_settings("djen", "mock")),
            ReceitaCnpjAdapter(_settings("receita_cnpj", "mock")),
            TseAdapter(_settings("tse", "mock")),
            CrcProtestosAdapter(_settings("crc_protestos", "mock")),
            CadinAdapter(_settings("cadin", "mock")),
            OnrImoveisAdapter(_settings("onr_imoveis", "mock")),
        ]

    def test_all_7_adapters_have_service_name(self):
        adapters = self._get_all_adapters()
        names = [a.service_name for a in adapters]
        assert len(set(names)) == 7  # todos únicos

    def test_datajud_only_processo(self):
        from src.integrations.adapters.datajud_adapter import DataJudAdapter
        a = DataJudAdapter(_settings("datajud", "mock"))
        assert a.supports(IdentifierType.NUMERO_PROCESSO)
        assert not a.supports(IdentifierType.CPF)
        assert not a.supports(IdentifierType.CNPJ)

    def test_receita_only_cnpj(self):
        from src.integrations.adapters.receita_cnpj_adapter import ReceitaCnpjAdapter
        a = ReceitaCnpjAdapter(_settings("receita_cnpj", "mock"))
        assert a.supports(IdentifierType.CNPJ)
        assert not a.supports(IdentifierType.CPF)

    def test_registry_all_7_registrable(self):
        from src.integrations.registry import AdapterRegistry
        from src.integrations.adapters.datajud_adapter import DataJudAdapter
        from src.integrations.adapters.djen_adapter import DjenAdapter
        from src.integrations.adapters.receita_cnpj_adapter import ReceitaCnpjAdapter
        from src.integrations.adapters.tse_adapter import TseAdapter
        from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter
        from src.integrations.adapters.cadin_adapter import CadinAdapter
        from src.integrations.adapters.onr_imoveis_adapter import OnrImoveisAdapter

        reg = AdapterRegistry()
        for cls in [DataJudAdapter, DjenAdapter, ReceitaCnpjAdapter, TseAdapter,
                    CrcProtestosAdapter, CadinAdapter, OnrImoveisAdapter]:
            s = _settings(cls.service_name, "mock")
            reg.register(cls, settings_override=s)

        assert len(reg.names()) == 7

    def test_mock_to_real_is_config_only(self, monkeypatch):
        """Demonstra que troca mock→real é somente configuração (sem mudança de código)."""
        from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter

        # Em modo mock → SUCCESS
        a_mock = CrcProtestosAdapter(_settings("crc_protestos", "mock"))
        # Em modo real → FAILED (não implementado)
        a_real = CrcProtestosAdapter(_settings("crc_protestos", "real"))

        assert a_mock.settings.is_mock() is True
        assert a_real.settings.is_real() is True
        assert a_mock.service_name == a_real.service_name  # mesmo contrato
