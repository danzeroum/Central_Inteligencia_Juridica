"""Response schemas declarados — elimina ``Dict[str, Any]`` opaco nos GETs (API-05).

Cada modelo declara um exemplo via ``json_schema_extra`` para que o Swagger/OpenAPI
mostre request/response concretos, conforme exigido pelo ADR-003. Os campos refletem
exatamente o que os handlers de ``src/api/main.py`` já retornam — a introdução do
``response_model`` é aditiva e não altera o shape das respostas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentSummary(BaseModel):
    """Resumo de um agente no registry (MCP)."""

    agent_id: str
    name: str
    type: str
    status: str
    endpoint: str
    specialization: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    trust_score: float = Field(..., ge=0.0, le=1.0)
    autonomy_level: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "agent_id": "supervisor_agent",
                "name": "Supervisor Agent",
                "type": "SupervisorAgent",
                "status": "active",
                "endpoint": "/api/v1/agents/supervisor_agent/invoke",
                "specialization": None,
                "capabilities": ["task_routing", "consensus"],
                "trust_score": 0.9,
                "autonomy_level": "supervised",
            }
        }
    }


class AgentListResponse(BaseModel):
    """Lista de agentes registrados (``GET /api/v1/agents``)."""

    total: int
    agents: List[AgentSummary]

    model_config = {
        "json_schema_extra": {
            "example": {
                "total": 1,
                "agents": [AgentSummary.model_config["json_schema_extra"]["example"]],
            }
        }
    }


class AgentCapabilityMatch(BaseModel):
    """Agente que satisfaz uma busca por capacidade."""

    agent_id: str
    name: str
    endpoint: str


class AgentsByCapabilityResponse(BaseModel):
    """Resultado de busca por capacidade (``GET /api/v1/agents/by-capability/{cap}``)."""

    capability: str
    total_matches: int
    agents: List[AgentCapabilityMatch]

    model_config = {
        "json_schema_extra": {
            "example": {
                "capability": "task_routing",
                "total_matches": 1,
                "agents": [
                    {
                        "agent_id": "supervisor_agent",
                        "name": "Supervisor Agent",
                        "endpoint": "/api/v1/agents/supervisor_agent/invoke",
                    }
                ],
            }
        }
    }


class A2AMessageResponse(BaseModel):
    """Confirmação de envio de mensagem A2A (``POST /api/v1/a2a/send``)."""

    status: str
    message_id: str
    sender: str
    receiver: str
    timestamp: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "sent",
                "message_id": "msg_abc123",
                "sender": "supervisor_agent",
                "receiver": "tjsp_agent",
                "timestamp": "2026-06-04T12:00:00+00:00",
            }
        }
    }


class A2AMessagesResponse(BaseModel):
    """Mensagens pendentes de um agente (``GET /api/v1/a2a/messages/{agent_id}``)."""

    agent_id: str
    message_count: int
    messages: List[Dict[str, Any]]


class A2AHistoryResponse(BaseModel):
    """Histórico de mensagens de um agente (``GET /api/v1/a2a/history/{agent_id}``)."""

    agent_id: str
    total_messages: int
    messages: List[Dict[str, Any]]


class A2ABroadcastResponse(BaseModel):
    """Confirmação de broadcast A2A (``POST /api/v1/a2a/broadcast``)."""

    status: str
    sender: str
    receivers: List[str]
    message_ids: List[str]
    total_sent: int


class HistoryRecord(BaseModel):
    """Uma consulta processada no histórico do consulente."""

    task: str
    operation: str
    tribunals: List[str] = Field(default_factory=list)
    timestamp: Optional[str] = None
    status: str = Field(..., description="'concluida' | 'em_revisao_humana'")


class HistoryResponse(BaseModel):
    """Histórico de consultas (``GET /api/v1/history``).

    ``count`` é o tamanho da página retornada; ``total`` é o total disponível na
    fonte. O campo ``cursor`` está reservado para a paginação cursor-based que a
    Frente B (persistência no DecisionLedger) habilitará — hoje é sempre ``None``.
    """

    count: int
    total: int
    cursor: Optional[str] = None
    history: List[HistoryRecord]

    model_config = {
        "json_schema_extra": {
            "example": {
                "count": 1,
                "total": 1,
                "cursor": None,
                "history": [
                    {
                        "task": "status do processo no TJSP",
                        "operation": "consulta_processual",
                        "tribunals": ["TJSP"],
                        "timestamp": "2026-06-04T12:00:00+00:00",
                        "status": "concluida",
                    }
                ],
            }
        }
    }
