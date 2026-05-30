"""In-memory rate limiting utilities for the public API."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import DefaultDict, Deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Simple IP-based rate limiter with a one-minute sliding window."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        self.requests_per_minute = requests_per_minute
        self._requests: DefaultDict[str, Deque[datetime]] = defaultdict(deque)

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "anonymous"
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=1)

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


__all__ = ["RateLimiter"]
