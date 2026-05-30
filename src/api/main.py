from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import Body, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agents.agente_legislativo import analisar_cenario_legislativo
from src.agents.supervisor_agent import SupervisorAgent
from src.api.autonomy_endpoints import router as autonomy_router
from src.api.hitl_endpoints import router as hitl_router
from src.api.ledger_endpoints import router as ledger_router
from src.api.monitoring_endpoints import router as monitoring_router
from src.api.training_endpoints import router as training_router
from src.hitl.hitl_queue import get_hitl_queue
from src.hitl.progressive_autonomy import get_autonomy_manager
from src.orchestration.unified_orchestrator import UnifiedOrchestrator
from src.protocols.a2a_channel import get_a2a_channel
from src.protocols.agent_card import AgentCard, AgentRegistry
from src.services.camara_client import buscar_projetos_de_lei
from src.utils.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

app = FastAPI(title="Central Inteligência Jurídica")

static_dir = os.path.join(os.path.dirname(__file__), "static")

AUTH_REQUIRED = False

# CORS — permite o dev server do Vite (localhost:5173) durante o desenvolvimento.
# Em produção a SPA é servida pela mesma origem (StaticFiles), tornando isto inócuo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(hitl_router)
app.include_router(training_router)
app.include_router(ledger_router)
app.include_router(autonomy_router)
app.include_router(monitoring_router)


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


class ProblemDetail(BaseModel):
    status: int = Field(..., description="HTTP status code do erro")
    title: str = Field(..., description="Resumo do problema")
    detail: str = Field(..., description="Detalhes adicionais")


class A2AMessageRequest(BaseModel):
    """Payload para envio de mensagens A2A."""

    receiver_id: str = Field(..., description="Identificador do agente de destino")
    message_type: str = Field(..., description="Tipo da mensagem a ser enviada")
    payload: Dict[str, Any] = Field(..., description="Dados da mensagem")
    priority: int = Field(1, ge=1, le=3, description="Prioridade da mensagem (1-3)")
    requires_response: bool = Field(
        False, description="Se é necessário aguardar resposta"
    )


class A2ABroadcastRequest(BaseModel):
    """Payload para broadcast de mensagens A2A."""

    sender_id: str = Field(..., description="Agente emissor da mensagem")
    receiver_ids: List[str] = Field(..., description="Lista de agentes destinatários")
    message_type: str = Field(..., description="Tipo da mensagem a ser enviada")
    payload: Dict[str, Any] = Field(..., description="Conteúdo da mensagem")
    priority: int = Field(1, ge=1, le=3, description="Prioridade da mensagem (1-3)")


class AuthManager:
    @staticmethod
    async def verify_token() -> str:
        return "anonymous"


async def enforce_rate_limit() -> None:  # pragma: no cover - placeholder
    return None


supervisor_agent = SupervisorAgent()
unified_orchestrator = UnifiedOrchestrator(supervisor_agent=supervisor_agent)
logger.info("UnifiedOrchestrator inicializado para endpoint avançado")
a2a_channel = get_a2a_channel()

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


@app.get("/hitl", response_class=HTMLResponse, include_in_schema=False)
async def hitl_console() -> HTMLResponse:
    """Serve a UI do console HITL."""
    hitl_path = os.path.join(static_dir, "hitl.html")
    if os.path.exists(hitl_path):
        with open(hitl_path, "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read())
    return HTMLResponse(content="<h1>HITL UI não encontrada.</h1>", status_code=404)


@app.get("/training-dashboard", response_class=HTMLResponse, include_in_schema=False)
async def training_dashboard() -> HTMLResponse:
    """Serve o dashboard de treinamento contínuo."""
    dashboard_path = os.path.join(static_dir, "training-dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read())
    return HTMLResponse(
        content="<h1>Training Dashboard não encontrado.</h1>", status_code=404
    )


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
    autonomy = get_autonomy_manager()

    return {
        "total": len(agent_registry.agents),
        "agents": [
            {
                "agent_id": card.agent_id,
                "name": card.name,
                "type": card.agent_type,
                "status": card.status,
                "endpoint": card.endpoint,
                "specialization": card.specialization,
                "capabilities": card.capabilities,
                "trust_score": round(
                    autonomy.agent_trust_scores.get(
                        card.agent_id, autonomy.default_trust_score
                    ),
                    2,
                ),
                "autonomy_level": autonomy.get_autonomy_level(card.agent_id),
            }
            for card in agent_registry.get_all()
        ],
    }


@app.post(
    "/api/v1/a2a/send",
    tags=["A2A"],
    summary="Envia mensagem entre agentes",
    description="Permite enviar mensagem direta de um agente para outro.",
)
async def send_a2a_message(
    sender_id: str,
    message: A2AMessageRequest,
    user_id: str = Depends(AuthManager.verify_token),
) -> Dict[str, Any]:
    """Envia mensagem entre agentes utilizando o canal A2A."""

    message_id = await a2a_channel.send_message(
        sender_id=sender_id,
        receiver_id=message.receiver_id,
        message_type=message.message_type,
        payload=message.payload,
        priority=message.priority,
        requires_response=message.requires_response,
    )

    return {
        "status": "sent",
        "message_id": message_id,
        "sender": sender_id,
        "receiver": message.receiver_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get(
    "/api/v1/a2a/messages/{agent_id}",
    tags=["A2A"],
    summary="Recebe mensagens pendentes de um agente",
    description="Retorna lista de mensagens A2A pendentes para um agente.",
)
async def get_agent_messages(
    agent_id: str,
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, Any]:
    """Recupera mensagens pendentes para um agente específico."""

    messages = await a2a_channel.receive_messages(agent_id, limit)

    return {
        "agent_id": agent_id,
        "message_count": len(messages),
        "messages": [msg.to_dict() for msg in messages],
    }


@app.get(
    "/api/v1/a2a/history/{agent_id}",
    tags=["A2A"],
    summary="Histórico de mensagens A2A",
    description="Retorna histórico de mensagens enviadas/recebidas por um agente.",
)
async def get_a2a_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Retorna histórico de mensagens para o agente informado."""

    history = a2a_channel.get_message_history(agent_id, limit)

    return {
        "agent_id": agent_id,
        "total_messages": len(history),
        "messages": [msg.to_dict() for msg in history],
    }


@app.post(
    "/api/v1/a2a/broadcast",
    tags=["A2A"],
    summary="Broadcast para múltiplos agentes",
    description="Envia mensagem para múltiplos agentes simultaneamente.",
)
async def broadcast_a2a_message(
    request: A2ABroadcastRequest,
    user_id: str = Depends(AuthManager.verify_token),
) -> Dict[str, Any]:
    """Realiza broadcast de mensagens para múltiplos agentes."""

    message_ids = []

    for receiver_id in request.receiver_ids:
        msg_id = await a2a_channel.send_message(
            sender_id=request.sender_id,
            receiver_id=receiver_id,
            message_type=request.message_type,
            payload=request.payload,
            priority=request.priority,
        )
        message_ids.append(msg_id)

    return {
        "status": "broadcasted",
        "sender": request.sender_id,
        "receivers": request.receiver_ids,
        "message_ids": message_ids,
        "total_sent": len(message_ids),
    }


@app.get(
    "/api/v1/a2a/health",
    tags=["A2A"],
    summary="Status do canal A2A",
    description="Verifica saúde do sistema de comunicação A2A.",
)
async def a2a_health_check() -> Dict[str, Any]:
    """Retorna informações de saúde do canal A2A."""

    return await a2a_channel.health_check()


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


@app.post(
    "/api/v1/tasks/advanced",
    tags=["Advanced AI Agent"],
    summary="Processa tarefa com orquestração completa de agentes",
    description="""
    Endpoint avançado que ativa o UnifiedOrchestrator com:
    - Squad completo de agentes especializados
    - RAG para enriquecimento de contexto
    - Chain-of-Thought para raciocínio
    - Consensus mechanism para decisões complexas
    - Adaptive planning com replanning automático
    """,
    responses={
        200: {"description": "Tarefa processada com sucesso pelo squad"},
        400: {"model": ProblemDetail},
        500: {"model": ProblemDetail},
    },
)
async def process_advanced_task(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Processa uma tarefa jurídica complexa utilizando o UnifiedOrchestrator."""

    logger.info(
        "🚀 ADVANCED MODE: Tarefa recebida do usuário %s: %s",
        user_id if AUTH_REQUIRED else "anonymous",
        task_request.task_description,
    )

    try:
        task_payload = {
            "task_id": f"adv_{user_id}_{int(time.time())}",
            "description": task_request.task_description,
            "priority": "high",
            "user_id": user_id,
            "requires_consensus": True,
        }

        result = await unified_orchestrator.execute_complex_task(task_payload)
        result["api_mode"] = "advanced"
        result["api_version"] = "1.1.0"

        logger.info(
            "✅ ADVANCED MODE: Tarefa concluída com sucesso=%s, confidence=%s",
            result.get("success"),
            result.get("consensus_strength", "N/A"),
        )

        return result

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive safeguard
        logger.error(f"❌ ADVANCED MODE: Erro no processamento: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no orquestrador avançado: {str(exc)}",
        )


@app.post(
    "/api/v1/tasks/compare",
    tags=["Advanced AI Agent"],
    summary="Compara processamento simples vs avançado",
    description="Executa a mesma tarefa nos dois modos e retorna comparação",
)
async def compare_modes(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Compara resultado do modo simples vs avançado para análise."""

    simple_result = await supervisor_agent.process_task(task_request.task_description)

    advanced_payload = {
        "task_id": f"cmp_{user_id}_{int(time.time())}",
        "description": task_request.task_description,
        "priority": "medium",
        "requires_consensus": False,
    }
    advanced_result = await unified_orchestrator.execute_complex_task(advanced_payload)

    advanced_mode_data = advanced_result.get("advanced_result", {})

    return {
        "comparison": {
            "simple_mode": simple_result,
            "advanced_mode": advanced_result,
            "differences": {
                "reasoning_depth": (
                    "advanced" if "reasoning" in advanced_mode_data else "simple"
                ),
                "consensus_used": bool(advanced_mode_data.get("consensus")),
                "rag_enabled": any(
                    "rag" in str(value).lower() for value in advanced_mode_data.values()
                ),
            },
        },
        "recommendation": "Use /api/v1/tasks/advanced para tarefas complexas",
    }


@app.get("/consultar-projetos-lei/", tags=["Consultas"])
async def consultar_projetos_endpoint(
    q: str = Query(..., description="Termo de busca para proposições legislativas"),
):
    """Consulta projetos de lei diretamente na API da Câmara dos Deputados."""

    termo_busca = q.strip()
    if not termo_busca:
        raise HTTPException(status_code=400, detail="Parametro 'q' e obrigatorio.")

    resultado = buscar_projetos_de_lei(termo_busca)
    if "error" in resultado:
        raise HTTPException(status_code=502, detail=resultado["error"])
    return resultado


@app.post("/analise-legislativa/", tags=["Análises de IA"])
async def analisar_legislacao_endpoint(
    tema: str = Body(
        ..., embed=True, description="Tema legislativo para análise de IA"
    ),
):
    """Inicia uma análise de IA sobre um tema legislativo."""

    tema_legislativo = tema.strip()
    if not tema_legislativo:
        raise HTTPException(status_code=400, detail="Parametro 'tema' e obrigatorio.")

    resultado_analise = analisar_cenario_legislativo(tema_legislativo)

    return {"tema_analisado": tema_legislativo, "analise_ia": resultado_analise}


@app.get("/health")
async def health_check(
    verbose: bool = Query(False, description="Inclui detalhes completos")
) -> Dict[str, Any]:
    """Endpoint simples de saúde da aplicação."""

    timestamp = datetime.now(timezone.utc).isoformat()
    overall_status = "ok"

    if not verbose:
        return {"status": overall_status, "timestamp": timestamp}

    agent_stats = {
        "supervisor_active": True,
        "active_delegates": list(supervisor_agent.active_delegates.keys()),
    }

    metrics_snapshot = MetricsCollector.snapshot()
    a2a_status = await a2a_channel.health_check()

    return {
        "status": overall_status,
        "timestamp": timestamp,
        "details": {
            "agents": agent_stats,
            "metrics": metrics_snapshot,
            "a2a": a2a_status,
        },
    }


@app.get(
    "/api/v1/history",
    tags=["Consultas"],
    summary="Histórico de consultas do consulente",
)
async def list_history(
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Lista as consultas processadas pelo Supervisor.

    Consultas cuja ação derivada entrou em revisão humana e ainda está pendente
    são marcadas com status ``em_revisao_humana``; as demais, ``concluida``.
    """

    pending_actions = {
        req.get("action", {}).get("task")
        for req in get_hitl_queue().get_pending_requests()
    }

    history = []
    for record in reversed(supervisor_agent.task_history[-limit:]):
        intent = record.get("intent", {})
        task = record.get("task", "")
        in_review = task in pending_actions
        history.append(
            {
                "task": task,
                "operation": intent.get("operacao", "generic"),
                "tribunals": record.get("tribunals", []),
                "timestamp": record.get("timestamp"),
                "status": "em_revisao_humana" if in_review else "concluida",
            }
        )

    return {"count": len(history), "history": history}


# ----------------------------------------------------------------------
# SPA (Vite build) — montada por último para não sombrear as rotas de API.
# O build do frontend gera estáticos em static/spa; servida em /app com
# fallback de HTML (html=True) para roteamento client-side.
# ----------------------------------------------------------------------
spa_dir = os.path.join(static_dir, "spa")
if os.path.isdir(spa_dir):
    app.mount("/app", StaticFiles(directory=spa_dir, html=True), name="spa")
else:  # pragma: no cover - apenas em ambiente sem build do frontend
    logger.info("SPA não encontrada em %s (rode 'npm run build').", spa_dir)
