"""Schemas Pydantic da API (contratos de request/response).

Centraliza os ``response_model`` declarados para os endpoints, fechando a lacuna
do anti-pattern API-05 (GETs retornando ``Dict[str, Any]`` opaco, sem schema no
OpenAPI). Cumpre o ADR-003, que exige "OpenAPI com exemplos (request/response +
erros ``application/problem+json``)".
"""

from src.api.schemas.responses import (
    AgentSummary,
    AgentListResponse,
    AgentCapabilityMatch,
    AgentsByCapabilityResponse,
    A2AMessageResponse,
    A2AMessagesResponse,
    A2AHistoryResponse,
    A2ABroadcastResponse,
    HistoryRecord,
    HistoryResponse,
)

__all__ = [
    "AgentSummary",
    "AgentListResponse",
    "AgentCapabilityMatch",
    "AgentsByCapabilityResponse",
    "A2AMessageResponse",
    "A2AMessagesResponse",
    "A2AHistoryResponse",
    "A2ABroadcastResponse",
    "HistoryRecord",
    "HistoryResponse",
]
