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
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Estabelece o ``correlation_id`` por requisição."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        correlation_id = incoming or generate_correlation_id()
        set_correlation_id(correlation_id)

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = correlation_id
        return response


__all__ = ["RequestContextMiddleware"]
