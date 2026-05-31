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
from typing import Dict, Optional

# Header padrão de propagação entre serviços.
REQUEST_ID_HEADER = "X-Request-ID"

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_client_ip: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)
_user_agent: ContextVar[Optional[str]] = ContextVar("user_agent", default=None)


def generate_correlation_id() -> str:
    """Gera um novo identificador de correlação."""

    return uuid.uuid4().hex


def set_correlation_id(value: str) -> None:
    """Define o identificador de correlação da requisição corrente."""

    _correlation_id.set(value)


def get_correlation_id() -> Optional[str]:
    """Retorna o identificador de correlação corrente, se houver."""

    return _correlation_id.get()


def set_request_metadata(client_ip: Optional[str], user_agent: Optional[str]) -> None:
    """Registra IP de origem e User-Agent da requisição corrente (auditoria)."""

    _client_ip.set(client_ip)
    _user_agent.set(user_agent)


def get_client_ip() -> Optional[str]:
    return _client_ip.get()


def get_user_agent() -> Optional[str]:
    return _user_agent.get()


def get_audit_context() -> Dict[str, Optional[str]]:
    """Contexto de auditoria (correlation_id, IP, User-Agent) para o ledger.

    SECURITY/BACEN: a trilha de decisões passa a registrar IP de origem e
    User-Agent, além do identificador de correlação — atendendo à rastreabilidade
    exigida para operações sensíveis (quem, de onde, com qual cliente).
    """

    return {
        "correlation_id": get_correlation_id(),
        "client_ip": get_client_ip(),
        "user_agent": get_user_agent(),
    }


__all__ = [
    "REQUEST_ID_HEADER",
    "generate_correlation_id",
    "set_correlation_id",
    "get_correlation_id",
    "set_request_metadata",
    "get_client_ip",
    "get_user_agent",
    "get_audit_context",
]
