"""Modelos Pydantic de entrada (requests) da API.

Separados de ``src/api/schemas/responses.py`` para manter o módulo focado e
evitar import circular (os validators referenciam InputSanitizer).
"""

from __future__ import annotations

import json as _json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from src.utils.input_sanitizer import InputSanitizer

_input_sanitizer = InputSanitizer(max_length=5000)

# SECURITY (M05/M10): teto para payloads A2A e número de destinatários de broadcast.
_MAX_A2A_PAYLOAD_BYTES = 64 * 1024
_MAX_BROADCAST_RECEIVERS = 50


def _validate_payload_size(payload: Dict[str, Any]) -> Dict[str, Any]:
    if len(_json.dumps(payload, default=str)) > _MAX_A2A_PAYLOAD_BYTES:
        raise ValueError("payload excede o tamanho máximo permitido")
    return payload


class TaskRequest(BaseModel):
    # SECURITY (H07/M07): limite de tamanho impede payloads gigantes (DoS).
    task_description: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Descrição da tarefa jurídica",
    )
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


# ---------------------------------------------------------------------------
# Jobs (S-0.5)
# ---------------------------------------------------------------------------

_ALLOWED_TASKS = frozenset({"analyze_document", "process_sped_file"})


class JobRequest(BaseModel):
    """Payload para submissão de job assíncrono."""

    task: str = Field(
        ...,
        description=f"Nome da tarefa. Permitidos: {sorted(_ALLOWED_TASKS)}",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Parâmetros da tarefa"
    )
    priority: int = Field(1, ge=1, le=3, description="Prioridade (1=baixa, 3=alta)")

    @field_validator("task")
    @classmethod
    def _validate_task_name(cls, value: str) -> str:
        if value not in _ALLOWED_TASKS:
            raise ValueError(
                f"Tarefa '{value}' não permitida. Permitidas: {sorted(_ALLOWED_TASKS)}"
            )
        return value
