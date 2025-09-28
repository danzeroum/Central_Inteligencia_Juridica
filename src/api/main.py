"""FastAPI application exposing the SupervisorAgent service."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.agents.supervisor_agent import SupervisorAgent

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Central de Inteligência Jurídica API",
    description="API para orquestrar agentes de IA em tarefas de consulta jurídica.",
    version="1.0.0",
)

supervisor_agent = SupervisorAgent()


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
        location = " -> ".join(str(item) for item in error.get("loc", []) if item not in {"body"})
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
async def process_task(task_request: TaskRequest) -> SuccessfulTaskResponse:
    """Processa uma tarefa jurídica utilizando o SupervisorAgent."""

    logger.info("Recebida tarefa para processamento: %s", task_request.task_description)
    result = supervisor_agent.process_task(task_request.task_description)
    response = SuccessfulTaskResponse.model_validate(result)
    return response


@app.get("/health", tags=["Monitoring"], summary="Verifica a saúde da API")
async def health_check() -> Dict[str, str]:
    """Endpoint simples de verificação de saúde."""

    return {"status": "ok"}
