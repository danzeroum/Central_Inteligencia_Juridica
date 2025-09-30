from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from src.agents.supervisor_agent import SupervisorAgent
from src.protocols.agent_card import AgentCard, AgentRegistry

logger = logging.getLogger(__name__)

app = FastAPI(title="Central Inteligência Jurídica")

AUTH_REQUIRED = False


class TaskRequest(BaseModel):
    task_description: str = Field(..., description="Descrição da tarefa jurídica")


class SuccessfulTaskResponse(BaseModel):
    status: str
    supervisor_result: Dict[str, Any]
    tribunals_used: list[str]
    task_id: str
    execution_time: float
    parallel: bool
    timestamp: str


class AuthManager:
    @staticmethod
    async def verify_token() -> str:
        return "anonymous"


async def enforce_rate_limit() -> None:  # pragma: no cover - placeholder
    return None


supervisor_agent = SupervisorAgent()

# Initialize MCP Agent Registry
agent_registry = AgentRegistry()


def initialize_agent_registry() -> None:
    """Populate agent registry with supervisor and active delegates."""

    agent_registry.agents.clear()

    supervisor_card = AgentCard.from_supervisor_agent(supervisor_agent)
    agent_registry.register(supervisor_card)

    for tribunal_code, tribunal_agent in supervisor_agent.active_delegates.items():
        tribunal_card = AgentCard.from_tribunal_agent(tribunal_agent)
        agent_registry.register(tribunal_card)


@app.get(
    "/api/v1/agents/capabilities",
    tags=["MCP"],
    summary="Lista todas as capacidades dos agentes",
    description="Retorna o registry completo de agentes em formato MCP-compatível.",
)
async def get_agent_capabilities() -> Dict[str, Any]:
    """Endpoint MCP para discovery de capacidades dos agentes."""

    initialize_agent_registry()
    return agent_registry.to_mcp_format()


@app.get(
    "/api/v1/agents",
    tags=["MCP"],
    summary="Lista todos os agentes registrados",
    description="Retorna lista simplificada de agentes ativos.",
)
async def list_agents() -> Dict[str, Any]:
    """Lista todos os agentes registrados no sistema."""

    initialize_agent_registry()

    return {
        "total": len(agent_registry.agents),
        "agents": [
            {
                "agent_id": card.agent_id,
                "name": card.name,
                "type": card.agent_type,
                "status": card.status,
                "endpoint": card.endpoint,
            }
            for card in agent_registry.get_all()
        ],
    }


@app.get(
    "/api/v1/agents/{agent_id}",
    tags=["MCP"],
    summary="Detalhes de um agente específico",
    description="Retorna agent card completo com todas as capacidades.",
)
async def get_agent_details(agent_id: str) -> Dict[str, Any]:
    """Retorna detalhes completos de um agente específico."""

    initialize_agent_registry()

    card = agent_registry.get_agent(agent_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    return card.to_dict()


@app.post(
    "/api/v1/agents/{agent_id}/invoke",
    tags=["MCP"],
    summary="Invoca um agente diretamente",
    description="Permite invocar um agente específico sem passar pelo supervisor.",
)
async def invoke_agent_directly(
    agent_id: str,
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Invoca um agente específico diretamente via MCP."""

    initialize_agent_registry()

    card = agent_registry.get_agent(agent_id)
    if not card and agent_id.endswith("_agent"):
        tribunal_code = agent_id[:-6].upper()
        if tribunal_code in supervisor_agent._identify_all_tribunals(tribunal_code):
            result = await supervisor_agent._delegate_to_tribunal_agent(
                tribunal_code,
                task_request.task_description,
            )
            initialize_agent_registry()
            return {
                "status": "success",
                "agent_invoked": agent_id,
                "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    if card.agent_type == "SupervisorAgent":
        result = await supervisor_agent.process_task(task_request.task_description)
    elif card.agent_type == "TribunalAgent":
        tribunal_code = card.specialization
        result = await supervisor_agent._delegate_to_tribunal_agent(
            tribunal_code,
            task_request.task_description,
        )
        initialize_agent_registry()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown agent type: {card.agent_type}",
        )

    return {
        "status": "success",
        "agent_invoked": agent_id,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get(
    "/api/v1/agents/by-capability/{capability}",
    tags=["MCP"],
    summary="Busca agentes por capacidade",
    description="Retorna agentes que possuem uma capacidade específica.",
)
async def get_agents_by_capability(capability: str) -> Dict[str, Any]:
    """Busca agentes que possuem determinada capacidade."""

    initialize_agent_registry()

    matching_agents = [
        card
        for card in agent_registry.get_all()
        if capability.lower() in [c.lower() for c in card.capabilities]
    ]

    return {
        "capability": capability,
        "total_matches": len(matching_agents),
        "agents": [
            {
                "agent_id": card.agent_id,
                "name": card.name,
                "endpoint": card.endpoint,
            }
            for card in matching_agents
        ],
    }


async def _process_task_internal(
    task_request: TaskRequest,
    user_id: str,
) -> SuccessfulTaskResponse:
    logger.info(
        "Recebida tarefa para processamento%s: %s",
        f" do usuário {user_id}" if AUTH_REQUIRED else "",
        task_request.task_description,
    )

    result = await supervisor_agent.process_task(task_request.task_description)

    response = SuccessfulTaskResponse.model_validate(result)
    return response


@app.post("/tasks", response_model=SuccessfulTaskResponse)
async def process_task(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> SuccessfulTaskResponse:
    """Processa uma tarefa jurídica utilizando o SupervisorAgent."""

    return await _process_task_internal(task_request, user_id)


@app.post("/api/v1/tasks", response_model=SuccessfulTaskResponse, tags=["MCP"])
async def process_task_v1(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> SuccessfulTaskResponse:
    """Processa tarefa jurídica utilizando o padrão MCP."""

    return await _process_task_internal(task_request, user_id)
