"""Testes de integração para IntelligenceAgent e FiscalAgent (Sprint 8)."""

from __future__ import annotations

from typing import Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.integrations.models import (
    AdapterResult,
    AdapterStatus,
    ConsolidatedReport,
    DataMode,
    EmpresaCadastro,
    HitlStatus,
    IdentifierType,
    PendenciaCadin,
    Protesto,
    RiskDimension,
)
from src.integrations.orchestrator import IntelligenceOrchestrator
from src.integrations.registry import AdapterRegistry
from src.integrations.settings import SourceSettings


def _mock_orchestrator(risk_score: float = 20.0) -> MagicMock:
    orch = MagicMock(spec=IntelligenceOrchestrator)
    report = ConsolidatedReport(
        query_id="test-id",
        identifier_masked="**.***.***/****-91",
        identifier_type=IdentifierType.CNPJ,
        risk_score=risk_score,
        risk_dimensions=[
            RiskDimension(name="juridico", score=0.0),
            RiskDimension(name="fiscal", score=risk_score),
            RiskDimension(name="patrimonial", score=0.0),
            RiskDimension(name="societario", score=0.0),
        ],
        recommendations=["Verificar situação fiscal"],
        summary=f"Score: {risk_score}/100",
        hitl_status=HitlStatus.NOT_REQUIRED,
        results={},
    )
    orch.investigate = AsyncMock(return_value=report)
    orch.as_consensus_proposal = IntelligenceOrchestrator.as_consensus_proposal
    return orch, report


class TestIntelligenceAgent:
    @pytest.mark.asyncio
    async def test_process_task_with_cnpj(self):
        from src.agents.intelligence_agent import IntelligenceAgent

        mock_orch, mock_report = _mock_orchestrator()
        agent = IntelligenceAgent(orchestrator=mock_orch)

        result = await agent.process_task("Analisar empresa 00.000.000/0001-91")
        assert result["status"] == "success"
        assert result["agent"] == "intelligence_agent"
        assert "risk_score" in result

    @pytest.mark.asyncio
    async def test_process_task_without_identifier(self):
        from src.agents.intelligence_agent import IntelligenceAgent

        mock_orch, _ = _mock_orchestrator()
        agent = IntelligenceAgent(orchestrator=mock_orch)

        result = await agent.process_task("Analisar empresa sem identificador")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_investigate_returns_dict(self):
        from src.agents.intelligence_agent import IntelligenceAgent

        mock_orch, mock_report = _mock_orchestrator()
        agent = IntelligenceAgent(orchestrator=mock_orch)

        result = await agent.investigate("00000000000191")
        assert isinstance(result, dict)
        assert "risk_score" in result

    @pytest.mark.asyncio
    async def test_process_task_with_cpf(self):
        from src.agents.intelligence_agent import IntelligenceAgent

        mock_orch, mock_report = _mock_orchestrator()
        mock_report.identifier_type = IdentifierType.CPF
        agent = IntelligenceAgent(orchestrator=mock_orch)

        result = await agent.process_task("Due diligence CPF 529.982.247-25")
        assert result["status"] == "success"


class TestFiscalAgent:
    @pytest.mark.asyncio
    async def test_get_fiscal_profile_returns_profile(self):
        from src.agents.fiscal_agent import FiscalAgent

        mock_orch, mock_report = _mock_orchestrator(risk_score=35.0)
        agent = FiscalAgent(orchestrator=mock_orch)

        profile = await agent.get_fiscal_profile("00000000000191")
        assert "fiscal_dimension" in profile
        assert "consensus_proposal" in profile
        assert profile["risk_score"] == 35.0

    @pytest.mark.asyncio
    async def test_consensus_proposal_fiscal_dimension(self):
        from src.agents.fiscal_agent import FiscalAgent

        mock_orch, mock_report = _mock_orchestrator(risk_score=40.0)
        agent = FiscalAgent(orchestrator=mock_orch)

        profile = await agent.get_fiscal_profile("00000000000191")
        proposal = profile["consensus_proposal"]
        assert proposal["dimension"] == "fiscal"
        # confidence = 1 - score/100
        assert abs(proposal["confidence"] - 0.6) < 0.01

    @pytest.mark.asyncio
    async def test_process_task_with_cnpj(self):
        from src.agents.fiscal_agent import FiscalAgent

        mock_orch, mock_report = _mock_orchestrator()
        agent = FiscalAgent(orchestrator=mock_orch)

        result = await agent.process_task("Perfil fiscal empresa 11.222.333/0001-81")
        assert result["status"] == "success"
        assert result["agent"] == "fiscal_agent"

    @pytest.mark.asyncio
    async def test_process_task_without_cnpj(self):
        from src.agents.fiscal_agent import FiscalAgent

        mock_orch, _ = _mock_orchestrator()
        agent = FiscalAgent(orchestrator=mock_orch)

        result = await agent.process_task("Relatório sem identificador fiscal")
        assert result["status"] == "error"


class TestConsensusIntegration:
    """Teste de consenso entre TribunalAgent (jurídico) e FiscalAgent (fiscal)."""

    def test_consensus_engine_weights_fiscal(self):
        from src.consensus.weighted_voting import WeightedConsensusEngine

        engine = WeightedConsensusEngine()
        engine.set_weight("fiscal_agent", 0.4)
        assert engine.get_weight("fiscal_agent") == pytest.approx(0.4)

    def test_as_consensus_proposal_for_fiscal(self):
        from src.integrations.orchestrator import IntelligenceOrchestrator

        report = ConsolidatedReport(
            query_id="test",
            identifier_masked="***",
            identifier_type=IdentifierType.CNPJ,
            risk_score=60.0,
            risk_dimensions=[
                RiskDimension(name="fiscal", score=50.0),
                RiskDimension(name="juridico", score=10.0),
            ],
            summary="Score: 60/100",
        )
        # FiscalAgent usa dimension='fiscal'
        fiscal_proposal = IntelligenceOrchestrator.as_consensus_proposal(
            report, dimension="fiscal"
        )
        assert fiscal_proposal["dimension"] == "fiscal"
        assert fiscal_proposal["risk_score"] == 50.0
        assert fiscal_proposal["confidence"] == pytest.approx(0.5)

        # TribunalAgent usa total ou dimension='juridico'
        juridico_proposal = IntelligenceOrchestrator.as_consensus_proposal(
            report, dimension="juridico"
        )
        assert juridico_proposal["dimension"] == "juridico"
        assert juridico_proposal["risk_score"] == 10.0


class TestGoldenRegressionPostRefactor:
    """Testes golden passam ANTES e DEPOIS do refactor (Sprint 8)."""

    def test_supervisor_members_intact(self):
        import os

        os.environ.setdefault(
            "JWT_SECRET", "development-secret-key-minimum-32-chars-long-for-tests"
        )
        os.environ["ENVIRONMENT"] = "test"
        from src.agents.supervisor_agent import SupervisorAgent

        sv = SupervisorAgent()
        # Membros externos que main.py e unified_orchestrator usam
        assert hasattr(sv, "active_delegates")
        assert hasattr(sv, "ledger")
        assert hasattr(sv, "tribunal_identifier")
        assert hasattr(sv, "_get_or_create_tribunal_agent")
        assert hasattr(sv, "process_task")
        assert hasattr(sv, "process_task_advanced")
        assert hasattr(sv, "consensus_engine")
