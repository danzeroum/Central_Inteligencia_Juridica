"""Rotas MCP de agentes — discovery, detalhes, trust e invocação direta."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from src.api.auth import AuthManager
from src.api.rbac import Principal, current_principal, require_permissions
from src.api.rate_limit import enforce_rate_limit
from src.api.schemas.requests import ProblemDetail, TaskRequest
from src.api.schemas.responses import (
    AgentDetailResponse,
    AgentListResponse,
    AgentSummary,
    AgentTrustResponse,
    AgentTrustUpdate,
    AgentsByCapabilityResponse,
)
from src.api.routes._shared import validate_agent_id
from src.api.state import (
    agent_registry,
    initialize_agent_registry,
    supervisor_agent,
)
from src.hitl.progressive_autonomy import get_autonomy_manager

logger = logging.getLogger(__name__)

router = APIRouter()

_static_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"
)


@router.get("/hitl", response_class=HTMLResponse, include_in_schema=False)
async def hitl_console() -> HTMLResponse:
    """Serve a UI do console HITL."""

    hitl_path = os.path.join(_static_dir, "hitl.html")
    if os.path.exists(hitl_path):
        with open(hitl_path, "r", encoding="utf-8") as fh:
            return HTMLResponse(content=fh.read())
    return HTMLResponse(content="<h1>HITL UI não encontrada.</h1>", status_code=404)


@router.get("/training-dashboard", response_class=HTMLResponse, include_in_schema=False)
async def training_dashboard() -> HTMLResponse:
    """Serve o dashboard de treinamento contínuo."""

    dashboard_path = os.path.join(_static_dir, "training-dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as fh:
            return HTMLResponse(content=fh.read())
    return HTMLResponse(
        content="<h1>Training Dashboard não encontrado.</h1>", status_code=404
    )


@router.get(
    "/api/v1/agents/capabilities",
    tags=["MCP"],
    summary="Lista todas as capacidades dos agentes",
    description="Retorna o registry completo de agentes em formato MCP-compatível.",
)
async def get_agent_capabilities(
    _principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Endpoint MCP para discovery de capacidades dos agentes."""

    initialize_agent_registry()
    return agent_registry.to_mcp_format()


@router.get(
    "/api/v1/agents",
    tags=["MCP"],
    summary="Lista todos os agentes registrados",
    description=(
        "Retorna lista simplificada de agentes ativos. Aceita o filtro opcional "
        "``?capability=`` — forma canônica (query param) da busca por capacidade, "
        "preferível ao path ``/agents/by-capability/{capability}``."
    ),
    response_model=AgentListResponse,
)
async def list_agents(
    capability: Optional[str] = Query(
        None, description="Filtra os agentes por capacidade (forma canônica de busca)"
    ),
    _principal: Principal = Depends(current_principal),
) -> AgentListResponse:
    """Lista todos os agentes registrados no sistema, opcionalmente filtrados."""

    initialize_agent_registry()
    autonomy = get_autonomy_manager()

    cards = agent_registry.get_all()
    if capability is not None:
        wanted = capability.lower()
        cards = [
            card for card in cards if wanted in [c.lower() for c in card.capabilities]
        ]

    agents = [
        AgentSummary(
            agent_id=card.agent_id,
            name=card.name,
            type=card.agent_type,
            status=card.status,
            endpoint=card.endpoint,
            specialization=card.specialization,
            description=card.description,
            capabilities=card.capabilities,
            tools=card.tools,
            version=card.version,
            trust_score=round(
                autonomy.agent_trust_scores.get(
                    card.agent_id, autonomy.default_trust_score
                ),
                2,
            ),
            autonomy_level=autonomy.get_autonomy_level(card.agent_id),
            metadata=card.metadata,
            created_at=card.created_at,
        )
        for card in cards
    ]
    return AgentListResponse(total=len(agents), agents=agents)


@router.get(
    "/api/v1/agents/by-capability/{capability}",
    tags=["MCP"],
    summary="Busca agentes por capacidade",
    description=(
        "Retorna agentes que possuem uma capacidade específica. Forma canônica "
        "equivalente: ``GET /api/v1/agents?capability=...`` (filtragem via query). "
        "Este path é mantido por compatibilidade/bookmarks."
    ),
    response_model=AgentsByCapabilityResponse,
)
async def get_agents_by_capability(
    capability: str,
    _principal: Principal = Depends(current_principal),
) -> AgentsByCapabilityResponse:
    """Busca agentes que possuem determinada capacidade."""

    initialize_agent_registry()

    matching_agents = [
        card
        for card in agent_registry.get_all()
        if capability.lower() in [c.lower() for c in card.capabilities]
    ]

    return AgentsByCapabilityResponse(
        capability=capability,
        total_matches=len(matching_agents),
        agents=[
            {
                "agent_id": card.agent_id,
                "name": card.name,
                "endpoint": card.endpoint,
            }
            for card in matching_agents
        ],
    )


@router.get(
    "/api/v1/agents/{agent_id}",
    tags=["MCP"],
    summary="Detalhes de um agente específico",
    description="Retorna agent card completo com todas as capacidades.",
    response_model=AgentDetailResponse,
)
async def get_agent_details(
    agent_id: str,
    _principal: Principal = Depends(current_principal),
) -> AgentDetailResponse:
    """Retorna detalhes completos de um agente específico."""

    initialize_agent_registry()
    autonomy = get_autonomy_manager()

    card = agent_registry.get_agent(agent_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    return AgentDetailResponse(
        agent_id=card.agent_id,
        name=card.name,
        type=card.agent_type,
        agent_type=card.agent_type,
        status=card.status,
        endpoint=card.endpoint,
        specialization=card.specialization,
        description=card.description,
        capabilities=card.capabilities,
        tools=card.tools,
        version=card.version,
        trust_score=round(
            autonomy.agent_trust_scores.get(
                card.agent_id, autonomy.default_trust_score
            ),
            2,
        ),
        autonomy_level=autonomy.get_autonomy_level(card.agent_id),
        metadata=card.metadata,
        created_at=card.created_at,
    )


@router.patch(
    "/api/v1/agents/{agent_id}/trust",
    tags=["MCP"],
    summary="Atualiza o trust score de um agente",
    description="Permite ajustar o trust score individual de um agente, alterando seu nível de autonomia.",
    response_model=AgentTrustResponse,
    responses={404: {"model": ProblemDetail}, 403: {"model": ProblemDetail}},
)
async def update_agent_trust(
    agent_id: str,
    body: AgentTrustUpdate,
    _principal: Principal = Depends(require_permissions("config:write")),
) -> AgentTrustResponse:
    """Atualiza o trust score de um agente específico."""

    initialize_agent_registry()
    card = agent_registry.get_agent(agent_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found",
        )

    autonomy = get_autonomy_manager()
    autonomy.agent_trust_scores[agent_id] = body.trust_score
    new_level = autonomy.get_autonomy_level(agent_id)

    logger.info(
        "Trust score atualizado",
        extra={
            "agent_id": agent_id,
            "trust_score": body.trust_score,
            "level": new_level,
        },
    )

    return AgentTrustResponse(
        agent_id=agent_id,
        trust_score=body.trust_score,
        autonomy_level=new_level,
    )


@router.post(
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
        if tribunal_code in supervisor_agent.identify_all_tribunals(tribunal_code):
            result = await supervisor_agent.delegate_to_tribunal_agent(
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
        result = await supervisor_agent.delegate_to_tribunal_agent(
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
