"""In-memory rate limiting utilities for the public API."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, DefaultDict

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


__all__ = ["RateLimiter"]
