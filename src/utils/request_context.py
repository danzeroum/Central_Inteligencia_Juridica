"""Per-request correlation context shared across the application.

CLOUD-READINESS: o ``correlation_id`` viaja por toda a requisição via
``contextvars`` (seguro com asyncio e threads). Ele alimenta os logs
estruturados, a metadata do Decision Ledger e os spans de tracing, permitindo
correlacionar uma requisição através de múltiplas réplicas e serviços quando o
sistema escalar horizontalmente na nuvem.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Optional

# Header padrão de propagação entre serviços.
REQUEST_ID_HEADER = "X-Request-ID"

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def generate_correlation_id() -> str:
    """Gera um novo identificador de correlação."""

    return uuid.uuid4().hex


def set_correlation_id(value: str) -> None:
    """Define o identificador de correlação da requisição corrente."""

    _correlation_id.set(value)


def get_correlation_id() -> Optional[str]:
    """Retorna o identificador de correlação corrente, se houver."""

    return _correlation_id.get()


__all__ = [
    "REQUEST_ID_HEADER",
    "generate_correlation_id",
    "set_correlation_id",
    "get_correlation_id",
]
