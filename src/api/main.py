"""FastAPI application exposing the SupervisorAgent service."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.api.auth import AuthManager
from src.api.rate_limiter import RateLimiter
from src.agents.supervisor_agent import SupervisorAgent
from src.utils.cache_manager import get_cache_manager

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Central de Inteligência Jurídica API",
    description="API para orquestrar agentes de IA em tarefas de consulta jurídica.",
    version="1.0.0",
)

current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

AUTH_REQUIRED = os.getenv("API_REQUIRE_AUTH", "false").lower() == "true"
AuthManager.configure(
    secret_key=os.getenv("API_AUTH_SECRET"),
    required=AUTH_REQUIRED,
)
rate_limiter = RateLimiter(requests_per_minute=int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "60")))
cache_manager = get_cache_manager()
supervisor_agent = SupervisorAgent()


async def enforce_rate_limit(request: Request) -> None:
    """Wrapper dependency to enforce rate limiting."""

    await rate_limiter(request)


class TaskRequest(BaseModel):
    """Representação do corpo de requisição para submissão de tarefas."""

    task_description: str = Field(
        ..., min_length=1, description="Descrição da tarefa a ser processada pelo agente."
    )

    @field_validator("task_description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("O campo 'task_description' não pode estar vazio.")
        return value.strip()


class SuccessfulTaskResponse(BaseModel):
    """Modelo de resposta em caso de sucesso ao processar uma tarefa."""

    model_config = ConfigDict(extra="allow")

    status: str
    supervisor_result: Dict[str, Any]
    tribunal_used: str
    timestamp: str | None = None


class ProblemDetail(BaseModel):
    """Estrutura padronizada de erros conforme RFC 7807."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str
    trace_id: str | None = Field(default=None, alias="traceId")


def _format_validation_errors(errors: List[Dict[str, Any]]) -> str:
    formatted_messages = []
    for error in errors:
        location = " -> ".join(
            str(item)
            for item in error.get("loc", [])
            if item not in {"body", "query", "request"}
        )
        message = error.get("msg", "Invalid input")
        formatted_messages.append(f"{location}: {message}" if location else message)
    return "; ".join(formatted_messages)


def _problem_detail(
    *,
    problem_type: str,
    title: str,
    status_code: int,
    detail: str | None,
    instance: str,
) -> ProblemDetail:
    trace_id = str(uuid4())
    return ProblemDetail(
        type=problem_type,
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
        trace_id=trace_id,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Transforma erros de validação em respostas RFC 7807 com status 400."""

    logger.warning("Erro de validação na requisição: %s", exc.errors())
    detail = _format_validation_errors(exc.errors())
    problem = _problem_detail(
        problem_type="https://api.buildtoflip.com/errors/invalid-input",
        title="Invalid Input",
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
        instance=str(request.url),
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=problem.model_dump(by_alias=True),
        media_type="application/problem+json",
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Captura exceções não tratadas e responde com um erro 500 padronizado."""

    logger.exception("Erro inesperado durante o processamento da requisição")
    problem = _problem_detail(
        problem_type="https://api.buildtoflip.com/errors/internal-server-error",
        title="Internal Server Error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
        instance=str(request.url),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=problem.model_dump(by_alias=True),
        media_type="application/problem+json",
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def read_root() -> HTMLResponse:
    """Serve a página principal da UI."""

    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read())
    return HTMLResponse(content="<h1>UI não encontrada.</h1>", status_code=404)


@app.post(
    "/api/v1/tasks",
    response_model=SuccessfulTaskResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Requisição inválida",
            "content": {
                "application/problem+json": {
                    "schema": ProblemDetail.model_json_schema(),
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Erro interno do servidor",
            "content": {
                "application/problem+json": {
                    "schema": ProblemDetail.model_json_schema(),
                }
            },
        },
    },
    summary="Processa uma nova tarefa jurídica",
    description="Recebe uma descrição de tarefa, delega para o SupervisorAgent e retorna o resultado estruturado.",
)
async def process_task(
    task_request: TaskRequest,
    user_id: str = Depends(AuthManager.verify_token),
    _: None = Depends(enforce_rate_limit),
) -> SuccessfulTaskResponse:
    """Processa uma tarefa jurídica utilizando o SupervisorAgent."""

    logger.info(
        "Recebida tarefa para processamento%s: %s",
        f" do usuário {user_id}" if AUTH_REQUIRED else "",
        task_request.task_description,
    )
    result = supervisor_agent.process_task(task_request.task_description)
    response = SuccessfulTaskResponse.model_validate(result)
    return response


@app.get("/health", tags=["Monitoring"], summary="Verifica a saúde da API")
async def health_check(
    verbose: bool = Query(
        False,
        description="Retorna informações detalhadas de saúde quando verdadeiro.",
    )
) -> Dict[str, Any]:
    """Endpoint de verificação de saúde com suporte a detalhes opcionais."""

    cache_status = cache_manager.health()
    agent_stats = supervisor_agent.get_agent_stats()
    overall_status = "ok" if cache_status.get("status") == "healthy" else "degraded"

    if not verbose:
        return {"status": overall_status}

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "cache": cache_status,
            "agents": agent_stats,
        },
    }


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Exposes Prometheus metrics for scraping."""

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
