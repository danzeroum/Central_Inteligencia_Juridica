"""Correlation-ID middleware.

Lê o header ``X-Request-ID`` recebido (ou gera um novo), disponibiliza-o no
contexto da requisição (para logs, ledger e tracing) e o devolve no header da
resposta, permitindo correlação ponta a ponta entre cliente, réplicas e
serviços downstream.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.utils.request_context import (
    REQUEST_ID_HEADER,
    generate_correlation_id,
    set_correlation_id,
    set_request_metadata,
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Estabelece o ``correlation_id`` e os metadados de auditoria por requisição."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        correlation_id = incoming or generate_correlation_id()
        set_correlation_id(correlation_id)

        # Auditoria: captura IP de origem (respeitando X-Forwarded-For atrás de
        # proxy/ingress) e User-Agent para registro na trilha de decisões.
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = (
            forwarded.split(",")[0].strip()
            if forwarded
            else (request.client.host if request.client else None)
        )
        set_request_metadata(client_ip, request.headers.get("user-agent"))

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = correlation_id
        return response


__all__ = ["RequestContextMiddleware"]
