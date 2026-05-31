"""Rate limiting utilities for the public API.

CLOUD-READINESS: por padrão usa um backend in-memory (janela deslizante por IP),
adequado a um único processo (Docker single-node). Quando ``RATE_LIMIT_BACKEND=redis``
e um cliente Redis está disponível, o estado é compartilhado entre todas as
réplicas — sem isto, rodar N réplicas multiplicaria o limite efetivo por N. A
seleção é por ambiente; os chamadores não mudam.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import DefaultDict, Deque, Optional

from fastapi import HTTPException, Request, status

try:  # pragma: no cover - optional dependency guard
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - redis not installed
    RedisError = RuntimeError  # type: ignore

from src.utils.redis_client import get_shared_redis_client

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60


class RateLimiter:
    """IP-based rate limiter with a one-minute sliding window.

    Backend selecionável: ``memory`` (padrão) ou ``redis`` (compartilhado entre
    réplicas). Em ``redis``, falhas de conexão degradam graciosamente para o
    backend in-memory, evitando bloquear todo o tráfego se o Redis cair.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        *,
        backend: Optional[str] = None,
        redis_client=None,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        # Backend in-memory (sempre presente — também é o fallback do Redis).
        self._requests: DefaultDict[str, Deque[datetime]] = defaultdict(deque)

        resolved = (
            (backend or os.getenv("RATE_LIMIT_BACKEND") or "memory").strip().lower()
        )
        self._redis = None
        if resolved == "redis":
            self._redis = redis_client or get_shared_redis_client(decode_responses=True)
            if self._redis is None:
                logger.warning(
                    "RATE_LIMIT_BACKEND=redis mas nenhum cliente Redis disponível; "
                    "usando backend in-memory (não compartilhado entre réplicas)."
                )
        self.backend = "redis" if self._redis is not None else "memory"

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "anonymous"

        if self._redis is not None:
            try:
                self._check_redis(client_ip)
                return
            except HTTPException:
                raise
            except RedisError as exc:  # pragma: no cover - caminho de falha
                logger.error("Rate limiter Redis falhou (%s); usando memória.", exc)

        self._check_memory(client_ip)

    # ------------------------------------------------------------------
    # Backend in-memory (single-process)
    # ------------------------------------------------------------------
    def _check_memory(self, client_ip: str) -> None:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=_WINDOW_SECONDS)

        timestamps = self._requests[client_ip]
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        timestamps.append(now)

        # SECURITY: evita vazamento de memória. Sem isto, ``_requests`` cresce
        # indefinidamente — uma entrada por IP, mesmo após a janela expirar. A
        # cada chamada descartamos IPs cuja janela ficou totalmente vazia.
        self._evict_stale(window_start)

    def _evict_stale(self, window_start: datetime) -> None:
        """Remove IPs sem timestamps válidos dentro da janela atual."""

        stale = [
            ip for ip, ts in self._requests.items() if not ts or ts[-1] < window_start
        ]
        for ip in stale:
            del self._requests[ip]

    # ------------------------------------------------------------------
    # Backend Redis (compartilhado entre réplicas)
    # ------------------------------------------------------------------
    def _check_redis(self, client_ip: str) -> None:
        client = self._redis
        if client is None:  # pragma: no cover - guarda defensiva (mypy)
            return self._check_memory(client_ip)
        key = f"ratelimit:{client_ip}"
        now = time.time()
        window_start = now - _WINDOW_SECONDS

        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        _, count = pipe.execute()

        if int(count) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        # Membro único evita colisão de scores idênticos dentro da mesma janela.
        member = f"{now}:{uuid.uuid4().hex}"
        add_pipe = client.pipeline()
        add_pipe.zadd(key, {member: now})
        add_pipe.expire(key, _WINDOW_SECONDS)
        add_pipe.execute()


__all__ = ["RateLimiter"]
