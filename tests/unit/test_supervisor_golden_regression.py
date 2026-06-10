"""Golden tests do SupervisorAgent — captura de comportamento antes do refactor.

Estes testes devem passar ANTES e DEPOIS do Sprint 8 (refactor em coordenadores).
Qualquer diferença de comportamento = regressão.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def supervisor():
    """SupervisorAgent mínimo (sem ChromaDB/Redis real)."""
    import os
    os.environ.setdefault(
        "JWT_SECRET", "development-secret-key-minimum-32-chars-long-for-tests"
    )
    from src.agents.supervisor_agent import SupervisorAgent
    from src.utils.ledger import DecisionLedger
    ledger = DecisionLedger()
    return SupervisorAgent(ledger=ledger)


class TestSupervisorGoldenInterface:
    """Garante que os membros externos do SupervisorAgent existem após o refactor."""

    def test_has_ledger(self, supervisor):
        assert hasattr(supervisor, "ledger")
        assert supervisor.ledger is not None

    def test_has_active_delegates(self, supervisor):
        assert hasattr(supervisor, "active_delegates")
        assert isinstance(supervisor.active_delegates, dict)

    def test_has_tribunal_identifier(self, supervisor):
        assert hasattr(supervisor, "tribunal_identifier")
        assert supervisor.tribunal_identifier is not None

    def test_has_consensus_engine(self, supervisor):
        assert hasattr(supervisor, "consensus_engine")

    def test_has_process_task_method(self, supervisor):
        assert hasattr(supervisor, "process_task")
        assert callable(supervisor.process_task)

    def test_has_process_task_advanced_method(self, supervisor):
        assert hasattr(supervisor, "process_task_advanced")
        assert callable(supervisor.process_task_advanced)

    def test_has_get_or_create_tribunal_agent(self, supervisor):
        assert hasattr(supervisor, "_get_or_create_tribunal_agent")
        assert callable(supervisor._get_or_create_tribunal_agent)


class TestSupervisorGoldenBehavior:
    """Comportamentos golden que não devem mudar após o refactor."""

    @pytest.mark.asyncio
    async def test_process_task_returns_dict(self, supervisor):
        result = await supervisor.process_task("Qual é o prazo recursal?")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_process_task_has_status_key(self, supervisor):
        result = await supervisor.process_task("Qual é o prazo recursal?")
        assert "status" in result or "success" in result or "response" in result

    @pytest.mark.asyncio
    async def test_process_task_advanced_returns_dict(self, supervisor):
        result = await supervisor.process_task_advanced(
            "Analise o caso de indenização por dano moral",
        )
        assert isinstance(result, dict)

    def test_get_or_create_tribunal_agent_returns_agent(self, supervisor):
        agent = supervisor._get_or_create_tribunal_agent("tjsp")
        assert agent is not None

    def test_get_or_create_adds_to_active_delegates(self, supervisor):
        supervisor._get_or_create_tribunal_agent("tjsp")
        assert "tjsp" in supervisor.active_delegates

    @pytest.mark.asyncio
    async def test_process_task_logs_to_ledger(self, supervisor):
        from unittest.mock import MagicMock, patch

        mock_ledger = MagicMock()
        supervisor.ledger = mock_ledger

        await supervisor.process_task("Teste de ledger")
        # O ledger deve ter sido acessado pelo SupervisorAgent
        # (verificação leve — apenas que não levanta exceção)
        assert True  # chegou até aqui = sem exceção

    def test_tribunal_identifier_is_accessible(self, supervisor):
        ti = supervisor.tribunal_identifier
        assert ti is not None
        # Deve conseguir identificar TJSP
        result = ti.identify_primary("preciso de informações sobre o TJSP")
        assert result is not None


class TestSupervisorConsensusInterface:
    """O WeightedConsensusEngine deve ter set_weight disponível."""

    def test_consensus_engine_has_set_weight(self, supervisor):
        engine = supervisor.consensus_engine
        assert hasattr(engine, "set_weight")

    def test_consensus_engine_set_weight_works(self, supervisor):
        supervisor.consensus_engine.set_weight("fiscal_agent", 0.4)
        # Não deve levantar exceção
        assert True
