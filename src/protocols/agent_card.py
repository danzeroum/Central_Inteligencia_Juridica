"""Agent Card Protocol - Metadata structure for agent capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class AgentCard:
    """Standardized card describing agent capabilities for MCP."""

    agent_id: str
    agent_type: str
    name: str
    description: str
    capabilities: List[str]
    tools: List[str]
    specialization: str
    status: str = "active"
    endpoint: str | None = None
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent card to dictionary for API responses."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "specialization": self.specialization,
            "status": self.status,
            "endpoint": self.endpoint,
            "version": self.version,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_tribunal_agent(cls, agent: Any) -> "AgentCard":
        """Create card from TribunalAgent instance."""
        default_capabilities = [
            "status_check",
            "process_query",
            "generic_responses",
        ]

        return cls(
            agent_id=f"{agent.tribunal_code.lower()}_agent",
            agent_type="TribunalAgent",
            name=f"Agente {agent.tribunal_code}",
            description=f"Agente especializado em consultas ao {agent.tribunal_code}",
            capabilities=getattr(agent, "capabilities", default_capabilities),
            tools=getattr(
                agent,
                "tools",
                ["tribunal_api_client", "cache_manager", "input_sanitizer"],
            ),
            specialization=agent.tribunal_code,
            endpoint=f"/api/v1/agents/{agent.tribunal_code.lower()}",
            metadata={
                "tribunal_config": getattr(agent, "config", {}),
                "task_count": getattr(agent, "task_count", 0),
            },
        )

    @classmethod
    def from_base_agent(cls, agent: Any) -> "AgentCard":
        """Create card from any BaseAgent subclass using its attributes."""
        agent_class = type(agent).__name__
        agent_id = getattr(agent, "agent_type", agent_class).lower().replace(" ", "_")
        return cls(
            agent_id=agent_id,
            agent_type=agent_class,
            name=getattr(agent, "name", agent_class),
            description=getattr(agent, "description", ""),
            capabilities=list(getattr(agent, "capabilities", [])),
            tools=list(getattr(agent, "tools", [])),
            specialization=getattr(agent, "specialization", agent_id),
            status=getattr(agent, "status", "active"),
            endpoint=getattr(agent, "endpoint", f"/api/v1/agents/{agent_id}/invoke"),
            version=getattr(agent, "version", "1.0.0"),
            metadata=dict(getattr(agent, "metadata", {})),
        )

    @classmethod
    def from_supervisor_agent(cls, agent: Any) -> "AgentCard":
        """Create card from SupervisorAgent instance."""
        return cls(
            agent_id="supervisor_agent",
            agent_type="SupervisorAgent",
            name="Supervisor Agent",
            description="Orquestrador central que delega tarefas para agentes especializados",
            capabilities=[
                "task_routing",
                "agent_orchestration",
                "tribunal_identification",
                "task_history_management",
            ],
            tools=["ledger", "sanitizer", "tribunal_agents"],
            specialization="orchestration",
            endpoint="/api/v1/tasks",
            metadata={
                "active_delegates": list(agent.active_delegates.keys()),
                "total_tasks_processed": len(agent.task_history),
            },
        )


@dataclass
class AgentRegistry:
    """Central registry of all active agents in the system."""

    agents: Dict[str, AgentCard] = field(default_factory=dict)

    def register(self, card: AgentCard) -> None:
        """Register an agent card."""
        self.agents[card.agent_id] = card

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from registry."""
        self.agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> AgentCard | None:
        """Get specific agent card."""
        return self.agents.get(agent_id)

    def get_all(self) -> List[AgentCard]:
        """Get all registered agents."""
        return list(self.agents.values())

    def get_by_type(self, agent_type: str) -> List[AgentCard]:
        """Get all agents of specific type."""
        return [card for card in self.agents.values() if card.agent_type == agent_type]

    def get_by_specialization(self, specialization: str) -> List[AgentCard]:
        """Get agents with specific specialization."""
        return [
            card
            for card in self.agents.values()
            if card.specialization.lower() == specialization.lower()
        ]

    def to_mcp_format(self) -> Dict[str, Any]:
        """Export registry in MCP-compatible format."""
        return {
            "protocol": "MCP/1.0",
            "service": "Central de Inteligência Jurídica",
            "version": "1.0.0",
            "total_agents": len(self.agents),
            "agents": [card.to_dict() for card in self.agents.values()],
            "capabilities_summary": self._summarize_capabilities(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _summarize_capabilities(self) -> Dict[str, List[str]]:
        """Summarize all unique capabilities across agents."""
        all_capabilities: set[str] = set()
        all_tools: set[str] = set()

        for card in self.agents.values():
            all_capabilities.update(card.capabilities)
            all_tools.update(card.tools)

        return {
            "capabilities": sorted(all_capabilities),
            "tools": sorted(all_tools),
        }


__all__ = ["AgentCard", "AgentRegistry"]
