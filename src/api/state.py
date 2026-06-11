"""Singletons da aplicação — agentes, orquestrador, canal A2A e registry.

Instâncias criadas uma vez na importação e compartilhadas por todos os módulos
de rota. Mantém o mesmo comportamento de ``main.py`` original (inicialização
eager no startup), mas separado para eliminar o god module.
"""

from __future__ import annotations

import logging

from src.agents.architect_agent import ArchitectAgent
from src.agents.auditor_agent import AuditorAgent
from src.agents.designer_agent import DesignerAgent
from src.agents.developer_agent import DeveloperAgent
from src.agents.exploration_agent import ExplorationAgent
from src.agents.ops_agent import OpsAgent
from src.agents.recovery_agent import RecoveryAgent
from src.agents.supervisor_agent import SupervisorAgent
from src.orchestration.unified_orchestrator import UnifiedOrchestrator
from src.protocols.a2a_channel import get_a2a_channel
from src.protocols.agent_card import AgentCard, AgentRegistry

logger = logging.getLogger(__name__)

supervisor_agent = SupervisorAgent()
unified_orchestrator = UnifiedOrchestrator(supervisor_agent=supervisor_agent)
logger.info("UnifiedOrchestrator inicializado para endpoint avançado")
a2a_channel = get_a2a_channel()

_specialized_agents = [
    ArchitectAgent(),
    AuditorAgent(),
    DesignerAgent(),
    DeveloperAgent(),
    ExplorationAgent(),
    OpsAgent(),
    RecoveryAgent(),
]

_functional_agent_cards = [
    AgentCard(
        agent_id="agente_jurisprudencia",
        agent_type="QueueWorker",
        name="Agente Jurisprudência",
        description=(
            "Worker Redis que processa análises de jurisprudência de forma assíncrona."
        ),
        capabilities=["jurisprudencia_search", "cnj_datajud"],
        tools=["redis_queue", "datajud_api"],
        specialization="jurisprudencia",
        endpoint="/api/v1/jurisprudencia",
        status="active",
    ),
    AgentCard(
        agent_id="agente_legislativo",
        agent_type="FunctionalService",
        name="Agente Legislativo",
        description=(
            "Serviço stateless de análise legislativa via Câmara dos Deputados + LLM."
        ),
        capabilities=["legislative_analysis", "bills_search"],
        tools=["camara_api", "llm"],
        specialization="legislativo",
        endpoint="/api/v1/legislativo/analisar",
        status="active",
    ),
]

agent_registry = AgentRegistry()


def initialize_agent_registry() -> None:
    """Popula o registry com todos os agentes conhecidos."""

    agent_registry.agents.clear()

    supervisor_card = AgentCard.from_supervisor_agent(supervisor_agent)
    agent_registry.register(supervisor_card)

    all_tribunal_codes = list(supervisor_agent.tribunal_identifier._tribunals.keys())
    for code in all_tribunal_codes:
        supervisor_agent._get_or_create_tribunal_agent(code)

    for tribunal_agent in supervisor_agent.active_delegates.values():
        tribunal_card = AgentCard.from_tribunal_agent(tribunal_agent)
        agent_registry.register(tribunal_card)

    for agent in _specialized_agents:
        card = AgentCard.from_base_agent(agent)
        agent_registry.register(card)

    for card in _functional_agent_cards:
        agent_registry.register(card)
