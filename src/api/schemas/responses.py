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
    endpoint: Optional[str] = None
    specialization: Optional[str] = None
    description: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    trust_score: float = Field(..., ge=0.0, le=1.0)
    autonomy_level: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "agent_id": "supervisor_agent",
                "name": "Supervisor Agent",
                "type": "SupervisorAgent",
                "status": "active",
                "endpoint": "/api/v1/agents/supervisor_agent/invoke",
                "specialization": None,
                "description": "Orquestrador central que delega tarefas para agentes especializados",
                "capabilities": ["task_routing", "consensus"],
                "tools": ["ledger", "sanitizer", "tribunal_agents"],
                "version": "1.0.0",
                "trust_score": 0.9,
                "autonomy_level": "supervised",
                "metadata": {},
                "created_at": "2026-06-01T00:00:00+00:00",
            }
        }
    }


class AgentDetailResponse(AgentSummary):
    """Card completo de um agente — ``GET /api/v1/agents/{agent_id}``."""

    model_config = {
        "json_schema_extra": {
            "example": {
                **AgentSummary.model_config["json_schema_extra"]["example"],
                "metadata": {"active_delegates": ["tjsp_agent"], "total_tasks_processed": 42},
            }
        }
    }


class AgentTrustUpdate(BaseModel):
    """Payload para atualizar o trust score de um agente."""

    trust_score: float = Field(..., ge=0.0, le=1.0, description="Novo trust score (0–1)")


class AgentTrustResponse(BaseModel):
    """Resposta da atualização de trust score."""

    agent_id: str
    trust_score: float
    autonomy_level: str


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
    fonte (DecisionLedger, durável). O campo ``cursor`` traz o token opaco da
    próxima página — ``None`` quando não há mais entradas. Repassar ``cursor`` em
    ``?cursor=`` avança a paginação.
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
