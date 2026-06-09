from __future__ import annotations

import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import json as _json

from fastapi import (
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from src.agents.agente_legislativo import analisar_cenario_legislativo
from src.agents.architect_agent import ArchitectAgent
from src.agents.auditor_agent import AuditorAgent
from src.agents.designer_agent import DesignerAgent
from src.agents.developer_agent import DeveloperAgent
from src.agents.exploration_agent import ExplorationAgent
from src.agents.ops_agent import OpsAgent
from src.agents.recovery_agent import RecoveryAgent
from src.agents.supervisor_agent import SupervisorAgent
from src.api.auth import AuthManager
from src.api.auth_endpoints import router as auth_router
from src.api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from src.api.rbac import Principal, current_principal, require_permissions
from src.api.schemas.responses import (
    A2ABroadcastResponse,
    A2AHistoryResponse,
    A2AMessageResponse,
    A2AMessagesResponse,
    AgentDetailResponse,
    AgentListResponse,
    AgentSummary,
    AgentTrustResponse,
    AgentTrustUpdate,
    AgentsByCapabilityResponse,
    HistoryResponse,
)
from src.api.autonomy_endpoints import router as autonomy_router
from src.api.hitl_endpoints import router as hitl_router
from src.api.jurisprudencia_endpoints import router as jurisprudencia_router
from src.api.ledger_endpoints import router as ledger_router
from src.api.lgpd_endpoints import router as lgpd_router
from src.api.monitoring_endpoints import router as monitoring_router
from src.api.training_endpoints import router as training_router
from src.api.profile_endpoints import router as profile_router
from src.hitl.hitl_queue import get_hitl_queue
from src.hitl.progressive_autonomy import get_autonomy_manager
from src.orchestration.unified_orchestrator import UnifiedOrchestrator
from src.protocols.a2a_channel import get_a2a_channel
from src.protocols.agent_card import AgentCard, AgentRegistry
from src.services.camara_client import buscar_projetos_de_lei
from src.utils.input_sanitizer import InputSanitizer
from src.utils.logging_config import configure_logging
from src.utils.metrics_collector import MetricsCollector
from src.utils.request_context import get_correlation_id
from src.utils.tracing import configure_tracing

# CLOUD-READINESS: logging estruturado (JSON em produção) com correlation_id por
# requisição — pré-requisito para agregação de logs e tracing entre réplicas.
configure_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="Central Inteligência Jurídica")

static_dir = os.path.join(os.path.dirname(__file__), "static")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# SECURITY (SEC-001): autenticação JWT é EXIGIDA por padrão. Em ``ENVIRONMENT=test``
# ela é relaxada para que a suíte exercite os endpoints sem emitir tokens; o
# comportamento é sobrescrevível via ``AUTH_REQUIRED``. O ``AuthManager`` real
# (JWT, thread-safe) substitui o antigo stub que retornava sempre "anonymous".
AUTH_REQUIRED = _env_flag("AUTH_REQUIRED", default=ENVIRONMENT != "test")
AuthManager.configure(required=AUTH_REQUIRED)

# SECURITY (SEC-002 / H14): rate limiting real por IP, agora num módulo
# compartilhado para que os routers também o apliquem (sem import circular).
from src.api.rate_limit import enforce_rate_limit  # noqa: E402

# SECURITY (P0-5): identificadores de agente (A2A) seguem um allowlist estrito —
# alfanuméricos e ``_ . -`` com comprimento limitado — fechando o vetor de injeção
# de ``sender_id``/``receiver_id`` recebidos como entrada controlada pelo usuário.
_AGENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


def _validate_agent_id(agent_id: str, field: str) -> str:
    """Valida um identificador de agente A2A contra o allowlist estrito."""

    if not isinstance(agent_id, str) or not _AGENT_ID_PATTERN.match(agent_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Identificador de agente inválido em '{field}'",
        )
    return agent_id


def _enforce_agent_identity(sender_id: str, principal: Principal) -> None:
    """SECURITY (IAM-002): amarra o ``sender_id`` à identidade autenticada.

    Impede que um cliente personifique outro agente. Um principal com a permissão
    ``agents:manage`` (ex.: admin/serviço) pode atuar em nome de qualquer agente.
    Quando a autenticação está desligada (dev/testes), não há identidade a
    vincular e a checagem é ignorada — mesmo contrato do acesso anônimo.
    """

    if principal.is_anonymous or principal.has_permission("agents:manage"):
        return
    if sender_id != principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="sender_id não corresponde à identidade autenticada",
        )


# CORS — permite o dev server do Vite (localhost:5173) durante o desenvolvimento.
# Em produção a SPA é servida pela mesma origem (StaticFiles), tornando isto inócuo.
# SECURITY (H15/M01): com ``allow_credentials=True``, métodos/headers ``*`` são
# excessivamente permissivos. Agora são listas EXPLÍCITAS e configuráveis por
# variável de ambiente (defaults = comportamento atual), evitando expor verbos
# como TRACE e aceitar qualquer header arbitrário.
def _csv_env(name: str, default: str) -> List[str]:
    return [
        item.strip() for item in os.getenv(name, default).split(",") if item.strip()
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_csv_env(
        "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ),
    allow_credentials=True,
    allow_methods=_csv_env("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE,OPTIONS"),
    allow_headers=_csv_env("CORS_ALLOW_HEADERS", "Authorization,Content-Type"),
)

# SECURITY: cabeçalhos de segurança (nosniff, X-Frame-Options, CSP, HSTS via
# ENABLE_HSTS quando há TLS à frente). Middlewares Starlette executam na ordem
# inversa de registro, então registramos o de contexto por último para que o
# correlation_id já esteja definido quando os demais (e os handlers) rodarem.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

# CLOUD-READINESS: tracing distribuído OTLP — no-op a menos que
# OTEL_EXPORTER_OTLP_ENDPOINT esteja definido (Jaeger/Tempo local hoje, backend
# gerenciado na nuvem amanhã, sem mudar código).
configure_tracing(app)


app.include_router(auth_router)
app.include_router(hitl_router)
app.include_router(training_router)
app.include_router(ledger_router)
app.include_router(lgpd_router)
app.include_router(autonomy_router)
app.include_router(monitoring_router)
app.include_router(jurisprudencia_router)
app.include_router(profile_router)


# SECURITY (SEC-004 / CWE-209): handler global de exceções não tratadas. Em vez
# de deixar o stack trace vazar na resposta, devolve um ProblemDetail opaco com
# uma referência (correlation_id) para correlação no suporte; o detalhe completo
# fica apenas no log do servidor.
@app.exception_handler(Exception)
async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    correlation_id = get_correlation_id() or uuid.uuid4().hex
    logger.error(
        "Erro não tratado [%s] em %s %s: %s",
        correlation_id,
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": 500,
            "title": "Internal Server Error",
            "detail": f"Erro interno. Referência para suporte: {correlation_id}",
        },
    )


# SECURITY (H09): o InputSanitizer — antes implementado mas nunca usado na borda
# da API — agora higieniza o texto livre das requisições (remoção de scripts/
# tags e truncamento), complementando os limites declarativos do Pydantic.
_input_sanitizer = InputSanitizer(max_length=5000)

# SECURITY (M05/M10): teto para o tamanho serializado de payloads A2A e para o
# número de destinatários de um broadcast, evitando abuso/DoS via payloads enormes.
_MAX_A2A_PAYLOAD_BYTES = 64 * 1024
_MAX_BROADCAST_RECEIVERS = 50


def _validate_payload_size(payload: Dict[str, Any]) -> Dict[str, Any]:
    if len(_json.dumps(payload, default=str)) > _MAX_A2A_PAYLOAD_BYTES:
        raise ValueError("payload excede o tamanho máximo permitido")
    return payload


# API-07 (Frente B): paginação cursor-based sobre o histórico persistido no
# DecisionLedger. O cursor é um offset opaco (base64) na lista reverso-cronológica
# de entradas ``TASK_COMPLETED`` — durável entre restarts (e compartilhado entre
# réplicas quando ``LEDGER_BACKEND=redis``).
def _encode_cursor(offset: int) -> str:
    import base64

    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")


def _decode_cursor(cursor: Optional[str]) -> int:
    if not cursor:
        return 0
    import base64

    try:
        offset = int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii"))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="cursor inválido"
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="cursor inválido"
        )
    return offset


class TaskRequest(BaseModel):
    # SECURITY (H07/M07): limite de tamanho impede payloads gigantes (DoS).
    task_description: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Descrição da tarefa jurídica",
    )
    # Campos opcionais para personalização — retrocompatíveis com clientes existentes
    profile_id: Optional[str] = Field(None, description="ID do perfil do usuário")
    cliente_id: Optional[str] = Field(
        None, description="ID do cliente para ajuste de linguagem"
    )
    output_language: Optional[str] = Field(
        None, description="Idioma de saída (ex: pt-BR)"
    )

    @field_validator("task_description")
    @classmethod
    def _sanitize_description(cls, value: str) -> str:
        return _input_sanitizer.sanitize_text(value)


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

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": 400,
                "title": "Bad Request",
                "detail": "Parâmetro inválido.",
            }
        }
    }


class A2AMessageRequest(BaseModel):
    """Payload para envio de mensagens A2A."""

    # API-03: ``sender_id`` é o campo CANÔNICO de identidade do emissor e vive no
    # corpo da requisição (não mais como query param, que vazava identidade em
    # logs de proxy/servidor). Permanece opcional para retrocompatibilidade com o
    # query param ``sender_id``, hoje *deprecated* — ver ``send_a2a_message``.
    sender_id: Optional[str] = Field(
        None, description="Identificador do agente emissor (preferir no corpo)"
    )
    receiver_id: str = Field(..., description="Identificador do agente de destino")
    message_type: str = Field(
        ..., min_length=1, max_length=128, description="Tipo da mensagem a ser enviada"
    )
    payload: Dict[str, Any] = Field(..., description="Dados da mensagem")
    priority: int = Field(1, ge=1, le=3, description="Prioridade da mensagem (1-3)")
    requires_response: bool = Field(
        False, description="Se é necessário aguardar resposta"
    )

    @field_validator("payload")
    @classmethod
    def _check_payload(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _validate_payload_size(value)


class A2ABroadcastRequest(BaseModel):
    """Payload para broadcast de mensagens A2A."""

    sender_id: str = Field(..., description="Agente emissor da mensagem")
    receiver_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=_MAX_BROADCAST_RECEIVERS,
        description="Lista de agentes destinatários",
    )
    message_type: str = Field(
        ..., min_length=1, max_length=128, description="Tipo da mensagem a ser enviada"
    )
    payload: Dict[str, Any] = Field(..., description="Conteúdo da mensagem")
    priority: int = Field(1, ge=1, le=3, description="Prioridade da mensagem (1-3)")

    @field_validator("payload")
    @classmethod
    def _check_payload(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _validate_payload_size(value)


supervisor_agent = SupervisorAgent()
unified_orchestrator = UnifiedOrchestrator(supervisor_agent=supervisor_agent)
logger.info("UnifiedOrchestrator inicializado para endpoint avançado")
a2a_channel = get_a2a_channel()

# Specialized agents (instantiated once at startup for registry)
_specialized_agents = [
    ArchitectAgent(),
    AuditorAgent(),
    DesignerAgent(),
    DeveloperAgent(),
    ExplorationAgent(),
    OpsAgent(),
    RecoveryAgent(),
]

# Functional services represented as static agent cards (not directly invocable)
_functional_agent_cards = [
    AgentCard(
        agent_id="agente_jurisprudencia",
        agent_type="QueueWorker",
        name="Agente Jurisprudência",
        description="Worker Redis que processa análises de jurisprudência de forma assíncrona.",
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
        description="Serviço stateless de análise legislativa via Câmara dos Deputados + LLM.",
        capabilities=["legislative_analysis", "bills_search"],
        tools=["camara_api", "llm"],
        specialization="legislativo",
        endpoint="/api/v1/legislativo/analisar",
        status="active",
    ),
]

# Initialize MCP Agent Registry
agent_registry = AgentRegistry()


def initialize_agent_registry() -> None:
    """Populate agent registry with all known agents."""

    agent_registry.agents.clear()

    # Supervisor
    supervisor_card = AgentCard.from_supervisor_agent(supervisor_agent)
    agent_registry.register(supervisor_card)

    # Ensure all tribunals are instantiated upfront (not just active delegates)
    all_tribunal_codes = list(supervisor_agent.tribunal_identifier._tribunals.keys())
    for code in all_tribunal_codes:
        supervisor_agent._get_or_create_tribunal_agent(code)

    for tribunal_agent in supervisor_agent.active_delegates.values():
        tribunal_card = AgentCard.from_tribunal_agent(tribunal_agent)
        agent_registry.register(tribunal_card)

    # Specialized BaseAgent subclasses
    for agent in _specialized_agents:
        card = AgentCard.from_base_agent(agent)
        agent_registry.register(card)

    # Functional services (static cards)
    for card in _functional_agent_cards:
        agent_registry.register(card)


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
async def get_agent_capabilities(
    _principal: Principal = Depends(current_principal),
) -> Dict[str, Any]:
    """Endpoint MCP para discovery de capacidades dos agentes."""

    initialize_agent_registry()
    return agent_registry.to_mcp_format()


@app.get(
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


@app.post(
    "/api/v1/a2a/send",
    tags=["A2A"],
    summary="Envia mensagem entre agentes",
    description=(
        "Permite enviar mensagem direta de um agente para outro. O ``sender_id`` "
        "deve vir no corpo (``A2AMessageRequest.sender_id``). O query param "
        "``sender_id`` é aceito apenas por retrocompatibilidade e está *deprecated*."
    ),
    response_model=A2AMessageResponse,
    responses={
        400: {"model": ProblemDetail},
        403: {"model": ProblemDetail},
    },
)
async def send_a2a_message(
    message: A2AMessageRequest,
    sender_id: Optional[str] = Query(
        None,
        deprecated=True,
        description="DEPRECATED — informe ``sender_id`` no corpo da requisição.",
    ),
    principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
) -> A2AMessageResponse:
    """Envia mensagem entre agentes utilizando o canal A2A."""

    # API-03: corpo é a fonte canônica; query param permanece como fallback
    # *deprecated*. Sem nenhum dos dois, é erro de requisição.
    effective_sender = message.sender_id or sender_id
    if not effective_sender:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sender_id é obrigatório (informe no corpo da requisição)",
        )

    _validate_agent_id(effective_sender, "sender_id")
    _validate_agent_id(message.receiver_id, "receiver_id")
    _enforce_agent_identity(effective_sender, principal)

    message_id = await a2a_channel.send_message(
        sender_id=effective_sender,
        receiver_id=message.receiver_id,
        message_type=message.message_type,
        payload=message.payload,
        priority=message.priority,
        requires_response=message.requires_response,
    )

    return A2AMessageResponse(
        status="sent",
        message_id=message_id,
        sender=effective_sender,
        receiver=message.receiver_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/api/v1/a2a/messages/{agent_id}",
    tags=["A2A"],
    summary="Recebe mensagens pendentes de um agente",
    description="Retorna lista de mensagens A2A pendentes para um agente.",
    response_model=A2AMessagesResponse,
)
async def get_agent_messages(
    agent_id: str,
    limit: int = Query(10, ge=1, le=100),
    _principal: Principal = Depends(current_principal),
) -> A2AMessagesResponse:
    """Recupera mensagens pendentes para um agente específico."""

    _validate_agent_id(agent_id, "agent_id")
    messages = await a2a_channel.receive_messages(agent_id, limit)

    return A2AMessagesResponse(
        agent_id=agent_id,
        message_count=len(messages),
        messages=[msg.to_dict() for msg in messages],
    )


@app.get(
    "/api/v1/a2a/history/{agent_id}",
    tags=["A2A"],
    summary="Histórico de mensagens A2A",
    description="Retorna histórico de mensagens enviadas/recebidas por um agente.",
    response_model=A2AHistoryResponse,
)
async def get_a2a_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    _principal: Principal = Depends(current_principal),
) -> A2AHistoryResponse:
    """Retorna histórico de mensagens para o agente informado."""

    _validate_agent_id(agent_id, "agent_id")
    history = a2a_channel.get_message_history(agent_id, limit)

    return A2AHistoryResponse(
        agent_id=agent_id,
        total_messages=len(history),
        messages=[msg.to_dict() for msg in history],
    )


@app.post(
    "/api/v1/a2a/broadcast",
    tags=["A2A"],
    summary="Broadcast para múltiplos agentes",
    description="Envia mensagem para múltiplos agentes simultaneamente.",
    response_model=A2ABroadcastResponse,
)
async def broadcast_a2a_message(
    request: A2ABroadcastRequest,
    principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
) -> A2ABroadcastResponse:
    """Realiza broadcast de mensagens para múltiplos agentes."""

    _validate_agent_id(request.sender_id, "sender_id")
    for receiver_id in request.receiver_ids:
        _validate_agent_id(receiver_id, "receiver_id")
    _enforce_agent_identity(request.sender_id, principal)

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

    return A2ABroadcastResponse(
        status="broadcasted",
        sender=request.sender_id,
        receivers=request.receiver_ids,
        message_ids=message_ids,
        total_sent=len(message_ids),
    )


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


@app.patch(
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


@app.get(
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


# API-01: rota legada não-versionada. Mantida (exceção consciente do ADR-003/D12)
# porém marcada como *deprecated* — a forma canônica é ``POST /api/v1/tasks``.
@app.post(
    "/tasks",
    response_model=SuccessfulTaskResponse,
    deprecated=True,
    summary="(Deprecated) Processa tarefa — use POST /api/v1/tasks",
)
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
        # SECURITY (SEC-004 / CWE-209): não devolver ``str(exc)`` ao cliente.
        # O detalhe completo (com stack trace) fica apenas no log do servidor;
        # o cliente recebe uma referência opaca para correlação com o suporte.
        correlation_id = uuid.uuid4().hex
        logger.error(
            "❌ ADVANCED MODE: erro no processamento [%s]: %s",
            correlation_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Erro interno ao processar a tarefa avançada. "
                f"Referência para suporte: {correlation_id}"
            ),
        )


# API-06: ``compare`` executa DOIS pipelines (2× custo de LLM) — é ferramenta de
# avaliação/diagnóstico, não fluxo de produção. Exige a permissão ``tasks:compare``
# (concedida apenas ao papel admin), evitando abuso de custo por usuários comuns.
@app.post(
    "/api/v1/tasks/compare",
    tags=["Advanced AI Agent"],
    summary="Compara processamento simples vs avançado (restrito a admin)",
    description="Executa a mesma tarefa nos dois modos e retorna comparação",
    responses={403: {"model": ProblemDetail}},
)
async def compare_modes(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _principal: Principal = Depends(require_permissions("tasks:compare")),
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


async def _consultar_projetos(
    termo_busca: str, pagina: int = 1, itens: int = 15
) -> Dict[str, Any]:
    """Lógica compartilhada de consulta de proposições (legado + canônico)."""

    termo_busca = termo_busca.strip()
    if not termo_busca:
        raise HTTPException(status_code=400, detail="Parametro 'q' e obrigatorio.")

    resultado = buscar_projetos_de_lei(termo_busca, pagina=pagina, itens=itens)
    if "error" in resultado:
        raise HTTPException(status_code=502, detail=resultado["error"])
    return resultado


async def _analisar_legislacao(tema: str) -> Dict[str, Any]:
    """Lógica compartilhada de análise legislativa (legado + canônico)."""

    tema_legislativo = tema.strip()
    if not tema_legislativo:
        raise HTTPException(status_code=400, detail="Parametro 'tema' e obrigatorio.")

    resultado_analise = analisar_cenario_legislativo(tema_legislativo)
    return {"tema_analisado": tema_legislativo, "analise_ia": resultado_analise}


# API-02: rotas legadas (verbo na URL + barra final) — exceção consciente do
# ADR-003/D12, mantidas para não quebrar a SPA. Os aliases canônicos abaixo usam
# substantivos no plural, sem barra final, e são a forma recomendada.
@app.get("/consultar-projetos-lei/", tags=["Consultas"], deprecated=True)
async def consultar_projetos_endpoint(
    q: str = Query(..., description="Termo de busca para proposições legislativas"),
    _principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
):
    """(Deprecated) Use ``GET /api/v1/proposicoes-legislativas``."""

    return await _consultar_projetos(q)


@app.get(
    "/api/v1/proposicoes-legislativas",
    tags=["Consultas"],
    summary="Pesquisa proposições legislativas",
)
async def pesquisar_proposicoes(
    q: str = Query(
        ...,
        min_length=2,
        max_length=200,
        description="Termo de busca para proposições legislativas",
    ),
    pagina: int = Query(1, ge=1, description="Número da página (começa em 1)"),
    itens: int = Query(15, ge=1, le=100, description="Itens por página (máx. 100)"),
    _principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Consulta proposições legislativas na API da Câmara dos Deputados."""

    return await _consultar_projetos(q, pagina=pagina, itens=itens)


@app.post("/analise-legislativa/", tags=["Análises de IA"], deprecated=True)
async def analisar_legislacao_endpoint(
    tema: str = Body(
        ..., embed=True, description="Tema legislativo para análise de IA"
    ),
    _principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
):
    """(Deprecated) Use ``POST /api/v1/analises-legislativas``."""

    return await _analisar_legislacao(tema)


@app.post(
    "/api/v1/analises-legislativas",
    tags=["Análises de IA"],
    status_code=status.HTTP_201_CREATED,
    summary="Cria análise de IA sobre tema legislativo",
)
async def criar_analise_legislativa(
    tema: str = Body(
        ...,
        embed=True,
        min_length=3,
        max_length=500,
        description="Tema legislativo para análise de IA",
    ),
    _principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Cria uma análise de IA sobre um tema legislativo."""

    return await _analisar_legislacao(tema)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expõe as métricas Prometheus do registry padrão (observabilidade).

    A dependência ``prometheus-client`` já era usada por circuit breakers e
    coletores de métricas, mas nenhum endpoint as expunha para scraping. Este
    endpoint fecha essa lacuna (formato text/plain ``# HELP/# TYPE``).
    """

    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    response_model=HistoryResponse,
)
async def list_history(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(
        None, description="Cursor opaco para a próxima página (vindo de uma resposta)"
    ),
    _principal: Principal = Depends(current_principal),
) -> HistoryResponse:
    """Lista as consultas processadas pelo Supervisor.

    Consultas cuja ação derivada entrou em revisão humana e ainda está pendente
    são marcadas com status ``em_revisao_humana``; as demais, ``concluida``.

    Frente B (API-07): a fonte é o ``DecisionLedger`` (entradas
    ``TASK_COMPLETED``), que é durável — sobrevive a restarts e, com
    ``LEDGER_BACKEND=redis``, é compartilhado entre réplicas. ``total`` reflete
    todo o histórico; ``count`` é a página; ``cursor`` aponta para a próxima
    página (``None`` quando não há mais).
    """

    pending_actions = {
        req.get("action", {}).get("task")
        for req in get_hitl_queue().get_pending_requests()
    }

    # Entradas em ordem cronológica → invertidas para mais-recente-primeiro.
    entries = supervisor_agent.ledger.get_entries(decision_type="TASK_COMPLETED")
    entries.reverse()
    total = len(entries)

    offset = _decode_cursor(cursor)
    page = entries[offset : offset + limit]

    history = []
    for entry in page:
        metadata = entry.get("metadata", {}) or {}
        task = metadata.get("task", "")
        in_review = task in pending_actions
        history.append(
            {
                "task": task,
                "operation": metadata.get("operation", "generic"),
                "tribunals": metadata.get("tribunals", []),
                "timestamp": entry.get("timestamp"),
                "status": "em_revisao_humana" if in_review else "concluida",
            }
        )

    next_offset = offset + len(page)
    next_cursor = _encode_cursor(next_offset) if next_offset < total else None

    return HistoryResponse(
        count=len(history),
        total=total,
        cursor=next_cursor,
        history=history,
    )


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
