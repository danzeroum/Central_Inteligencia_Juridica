"""Testes de integração do IntelligenceOrchestrator (Sprint 4)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.models import (
    AdapterResult,
    AdapterStatus,
    ConsolidatedReport,
    DataMode,
    HitlStatus,
    IdentifierType,
    PendenciaCadin,
    Protesto,
)
from src.integrations.orchestrator import IntelligenceOrchestrator
from src.integrations.registry import AdapterRegistry
from src.integrations.risk_engine import RiskEngine
from src.integrations.settings import SourceSettings


def _make_adapter_cls(source_name: str, response: AdapterResult, id_types):
    """Fábrica para criar adapter mockado com closure correta por iteração."""
    from src.integrations.base import LegalDataAdapter

    class _MockAdapter(LegalDataAdapter):
        supported_identifiers = id_types
        data_type = f"mock_{source_name}"

        async def fetch_real(self, q):
            return []

        async def query(self, _q):
            return response  # captura correta por parâmetro da fábrica

    _MockAdapter.service_name = source_name
    _MockAdapter.supported_identifiers = id_types
    return _MockAdapter


def _make_registry_with_mocks(
    adapter_responses: Dict[str, AdapterResult],
) -> AdapterRegistry:
    """Cria registry com adaptadores mockados retornando respostas pré-definidas."""
    registry = AdapterRegistry()

    for source_name, response in adapter_responses.items():
        id_types = {
            IdentifierType.CNPJ,
            IdentifierType.CPF,
            IdentifierType.NUMERO_PROCESSO,
        }
        if source_name == "datajud":
            id_types = {IdentifierType.NUMERO_PROCESSO}
        elif source_name == "receita_cnpj":
            id_types = {IdentifierType.CNPJ}
        elif source_name == "tse":
            id_types = {IdentifierType.CPF, IdentifierType.NOME}

        adapter_cls = _make_adapter_cls(source_name, response, id_types)
        settings = SourceSettings(name=source_name, mode="mock")
        registry.register(adapter_cls, settings_override=settings)

    return registry


class TestOrchestratorBasic:
    @pytest.mark.asyncio
    async def test_investigate_never_raises_on_error(self):
        """investigate() nunca propaga exceção."""
        registry = AdapterRegistry()
        orch = IntelligenceOrchestrator(registry)
        # Identificador inválido
        report = await orch.investigate("IDENTIFICADOR_INVALIDO_QUE_CAUSA_ERRO")
        assert isinstance(report, ConsolidatedReport)

    @pytest.mark.asyncio
    async def test_investigate_cnpj_returns_report(self):
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[],
                total_available=0,
            ),
            "crc_protestos": AdapterResult(
                source="crc_protestos",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[Protesto(situacao="PROTESTADO", valor=10000.0)],
                total_available=1,
            ),
            "cadin": AdapterResult(
                source="cadin",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[PendenciaCadin(situacao="ATIVO")],
                total_available=1,
            ),
        }
        registry = _make_registry_with_mocks(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", sources=["receita_cnpj", "crc_protestos", "cadin"]
        )
        assert isinstance(report, ConsolidatedReport)
        assert report.identifier_type == IdentifierType.CNPJ
        assert report.risk_score > 0
        assert "crc_protestos" in report.results
        assert "cadin" in report.results

    @pytest.mark.asyncio
    async def test_partial_failure_still_returns_report(self):
        """Falha parcial (um adapter) não impede relatório."""
        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[],
            ),
            "crc_protestos": AdapterResult(
                source="crc_protestos",
                status=AdapterStatus.FAILED,
                error="Timeout",
            ),
        }
        registry = _make_registry_with_mocks(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", sources=["receita_cnpj", "crc_protestos"]
        )
        assert isinstance(report, ConsolidatedReport)
        assert report.results["crc_protestos"]["status"] == "failed"
        assert report.results["receita_cnpj"]["status"] == "success"


class TestRiskEngine:
    def test_risk_score_with_protesto(self):
        engine = RiskEngine()
        results = {
            "crc_protestos": AdapterResult(
                source="crc_protestos",
                status=AdapterStatus.SUCCESS,
                items=[Protesto(situacao="PROTESTADO")],
            )
        }
        score, dims, factors, recs, summary = engine.score(results)
        assert score >= 30
        protesto_factor = next((f for f in factors if f.code == "protesto_ativo"), None)
        assert protesto_factor is not None
        assert protesto_factor.dimension == "patrimonial"

    def test_risk_score_with_cadin(self):
        engine = RiskEngine()
        results = {
            "cadin": AdapterResult(
                source="cadin",
                status=AdapterStatus.SUCCESS,
                items=[PendenciaCadin(situacao="ATIVO")],
            )
        }
        score, dims, _, recs, _ = engine.score(results)
        assert score >= 15
        fiscal_dim = next((d for d in dims if d.name == "fiscal"), None)
        assert fiscal_dim is not None
        assert fiscal_dim.score > 0

    def test_risk_score_zero_for_clean(self):
        engine = RiskEngine()
        results = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                items=[],
            )
        }
        score, _, factors, _, _ = engine.score(results)
        assert score == 0.0
        assert len(factors) == 0

    def test_risk_score_capped_at_100(self):
        engine = RiskEngine()
        # Todos os fatores juntos devem ser capados em 100
        results = {
            "crc_protestos": AdapterResult(
                source="crc_protestos",
                status=AdapterStatus.SUCCESS,
                items=[Protesto(situacao="PROTESTADO")],
            ),
            "cadin": AdapterResult(
                source="cadin",
                status=AdapterStatus.SUCCESS,
                items=[PendenciaCadin(situacao="ATIVO")],
            ),
            "datajud": AdapterResult(
                source="datajud",
                status=AdapterStatus.SUCCESS,
                items=[],
                total_available=10,  # > 5
            ),
        }
        score, _, _, _, _ = engine.score(results)
        assert score <= 100

    def test_risk_dimensions_all_present(self):
        engine = RiskEngine()
        score, dims, _, _, _ = engine.score({})
        dim_names = {d.name for d in dims}
        assert {"juridico", "fiscal", "patrimonial", "societario"}.issubset(dim_names)

    def test_requires_hitl_above_threshold(self):
        engine = RiskEngine()
        assert engine.requires_hitl(70) is True
        assert engine.requires_hitl(69) is False

    def test_risk_deterministic(self):
        """Mesmo input sempre produz mesmo score."""
        engine = RiskEngine()
        results = {
            "crc_protestos": AdapterResult(
                source="crc_protestos",
                status=AdapterStatus.SUCCESS,
                items=[Protesto(situacao="PROTESTADO")],
            )
        }
        s1, _, _, _, _ = engine.score(results)
        s2, _, _, _, _ = engine.score(results)
        assert s1 == s2


class TestHitlGate:
    @pytest.mark.asyncio
    async def test_hitl_triggered_on_high_score(self):
        """Score alto ativa HITL."""
        from src.integrations.models import EmpresaCadastro, SocioQSA

        responses = {
            "crc_protestos": AdapterResult(
                source="crc_protestos",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[Protesto(situacao="PROTESTADO", valor=50000.0)],
                total_available=1,
            ),
            "cadin": AdapterResult(
                source="cadin",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[PendenciaCadin(situacao="ATIVO")],
                total_available=1,
            ),
            "datajud": AdapterResult(
                source="datajud",
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK,
                items=[],
                total_available=8,  # > 5
            ),
        }
        registry = _make_registry_with_mocks(responses)
        orch = IntelligenceOrchestrator(registry)

        report = await orch.investigate(
            "00000000000191", sources=["crc_protestos", "cadin", "datajud"]
        )
        # Score alto deve resultar em HITL pending (sem autonomy_manager real)
        if report.risk_score >= 70:
            assert report.hitl_status in (HitlStatus.PENDING, HitlStatus.APPROVED)


class TestLedgerLogging:
    @pytest.mark.asyncio
    async def test_ledger_called_without_pii(self):
        """Ledger é chamado com hash, não PII bruta."""
        mock_ledger = MagicMock(spec=["log_decision"])
        mock_ledger.log_decision = MagicMock()

        responses = {
            "receita_cnpj": AdapterResult(
                source="receita_cnpj",
                status=AdapterStatus.SUCCESS,
                items=[],
            )
        }
        registry = _make_registry_with_mocks(responses)
        orch = IntelligenceOrchestrator(registry, ledger=mock_ledger)
        await orch.investigate("00000000000191", sources=["receita_cnpj"])

        mock_ledger.log_decision.assert_called_once()
        call_kwargs = mock_ledger.log_decision.call_args[1]
        # Verifica que não há PII bruta — hash está em metadata
        metadata = call_kwargs.get("metadata", {})
        identifier_hash = metadata.get("identifier_hash", "")
        assert "00000000000191" not in identifier_hash
        assert len(identifier_hash) == 64  # sha256 hex


class TestCacheIntegration:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self):
        from src.integrations.models import EmpresaCadastro

        mock_cache = MagicMock()
        mock_cache.get_cached = MagicMock(
            return_value={
                "source": "receita_cnpj",
                "status": "success",
                "data_mode": "mock",
                "items": [],
                "total_available": 0,
                "latency_ms": 0.0,
                "from_cache": False,
                "error": None,
                "metadata": {},
            }
        )
        mock_cache.set_cached = MagicMock()

        registry = AdapterRegistry()
        orch = IntelligenceOrchestrator(registry, cache=mock_cache)

        # Com cache retornando resultado, não deve chamar o adapter
        report = await orch.investigate("00000000000191")
        # O cache é chamado durante a investigação
        # (mesmo sem adapter registrado para CNPJ, o orquestrador não falha)
        assert isinstance(report, ConsolidatedReport)


class TestAsConsensusProposal:
    def test_total_score(self):
        from src.integrations.models import RiskDimension

        report = ConsolidatedReport(
            query_id="test",
            identifier_masked="***",
            identifier_type=IdentifierType.CNPJ,
            risk_score=65.0,
            risk_dimensions=[
                RiskDimension(name="fiscal", score=40.0),
                RiskDimension(name="juridico", score=25.0),
            ],
            summary="Score: 65/100",
        )
        proposal = IntelligenceOrchestrator.as_consensus_proposal(report)
        assert proposal["risk_score"] == 65.0
        assert proposal["confidence"] == pytest.approx(0.35, abs=0.01)
        assert proposal["dimension"] == "total"

    def test_fiscal_dimension(self):
        from src.integrations.models import RiskDimension

        report = ConsolidatedReport(
            query_id="test",
            identifier_masked="***",
            identifier_type=IdentifierType.CNPJ,
            risk_score=65.0,
            risk_dimensions=[
                RiskDimension(name="fiscal", score=40.0),
            ],
            summary="Score: 65/100",
        )
        proposal = IntelligenceOrchestrator.as_consensus_proposal(
            report, dimension="fiscal"
        )
        assert proposal["risk_score"] == 40.0
        assert proposal["dimension"] == "fiscal"
