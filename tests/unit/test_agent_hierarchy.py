"""Testes de conformidade da hierarquia de agentes (LSP/ISP).

A auditoria apontou que RecoveryAgent e ExplorationAgent não herdavam de
BaseAgent, quebrando a substituibilidade (LSP) e dificultando "plugar" novos
agentes/domínios. Estes testes garantem a conformidade e a compatibilidade
retroativa do método ``arun``.
"""

from __future__ import annotations

import pytest

from src.agents.base_agent import BaseAgent
from src.agents.exploration_agent import ExplorationAgent
from src.agents.recovery_agent import RecoveryAgent


async def _echo_tool(text: str) -> str:
    return text.upper()


@pytest.mark.parametrize(
    "factory, agent_type, result_key",
    [
        (lambda: RecoveryAgent(_echo_tool), "recovery", "actions"),
        (lambda: ExplorationAgent(_echo_tool), "exploration", "report"),
    ],
)
def test_agents_are_baseagent_subclasses(factory, agent_type, result_key) -> None:
    agent = factory()
    assert isinstance(agent, BaseAgent)
    assert agent.agent_type == agent_type
    assert agent.agent_id  # gerado por BaseAgent
    assert agent.tools  # ferramentas declaradas


@pytest.mark.parametrize(
    "factory, result_key",
    [
        (lambda: RecoveryAgent(_echo_tool), "actions"),
        (lambda: ExplorationAgent(_echo_tool), "report"),
    ],
)
async def test_execute_uniform_interface(factory, result_key) -> None:
    agent = factory()
    result = await agent.execute({"description": "verificar incidente"})
    assert result["success"] is True
    assert result["agent"] == agent.agent_type
    assert "VERIFICAR INCIDENTE" in result[result_key]


async def test_execute_rejects_invalid_payload() -> None:
    agent = RecoveryAgent(_echo_tool)
    with pytest.raises(ValueError):
        await agent.execute({})


async def test_arun_backward_compatible() -> None:
    # A API original (arun) continua funcionando para chamadores existentes.
    recovery = RecoveryAgent(_echo_tool)
    exploration = ExplorationAgent(_echo_tool)
    assert (await recovery.arun("falha")).startswith("Recovery actions:")
    assert (await exploration.arun("scan")).startswith("Exploration report:")
