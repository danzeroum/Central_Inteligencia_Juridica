"""Shared Redis connection factory.

CLOUD-READINESS: este módulo centraliza a criação do cliente Redis usado por
cache, rate limiter, decision ledger e fila HITL. Mantê-lo único garante que,
ao migrar de um Redis em container (Docker, hoje) para um serviço gerenciado
(ElastiCache/MemoryStore, amanhã), basta ajustar as variáveis de ambiente
``REDIS_URL`` / ``REDIS_HOST`` / ``REDIS_PORT`` / ``REDIS_DB`` / ``REDIS_PASSWORD``
em um só lugar — nenhum chamador precisa mudar.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

try:  # pragma: no cover - optional dependency guard
    import redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - redis not installed
    redis = None  # type: ignore
    RedisError = RuntimeError  # type: ignore

logger = logging.getLogger(__name__)


def create_redis_client(*, decode_responses: bool = False) -> Optional["redis.Redis"]:
    """Cria um cliente Redis a partir do ambiente, ou ``None`` se indisponível.

    Não levanta exceção em falha de configuração: retorna ``None`` para que os
    chamadores possam degradar para um backend in-memory (fallback de
    single-node) de forma transparente.
    """

    if redis is None:
        return None

    url = os.getenv("REDIS_URL")
    if url:
        try:
            return redis.from_url(url, decode_responses=decode_responses)
        except RedisError as exc:  # pragma: no cover - connection error path
            logger.error("Failed to connect to Redis via URL: %s", exc)
            return None

    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = os.getenv("REDIS_PASSWORD") or None

    try:
        return redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses,
        )
    except RedisError as exc:  # pragma: no cover - connection error path
        logger.error("Failed to initialise Redis client: %s", exc)
        return None


# Cliente compartilhado (lazy) para componentes de estado que se beneficiam de
# reaproveitar o mesmo pool de conexões: rate limiter, ledger e fila HITL.
_shared_client: Optional["redis.Redis"] = None
_shared_initialised: bool = False


def get_shared_redis_client(
    *, decode_responses: bool = False
) -> Optional["redis.Redis"]:
    """Retorna um cliente Redis compartilhado (criado sob demanda)."""

    global _shared_client, _shared_initialised
    if not _shared_initialised:
        _shared_client = create_redis_client(decode_responses=decode_responses)
        _shared_initialised = True
    return _shared_client


def reset_shared_redis_client() -> None:
    """Reseta o cliente compartilhado (útil em testes)."""

    global _shared_client, _shared_initialised
    _shared_client = None
    _shared_initialised = False


__all__ = [
    "create_redis_client",
    "get_shared_redis_client",
    "reset_shared_redis_client",
]
