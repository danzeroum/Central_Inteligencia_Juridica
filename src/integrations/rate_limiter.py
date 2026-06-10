"""Rate limiter assíncrono (sliding window) por fonte de integração."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional


class AsyncRateLimiter:
    """Sliding window rate limiter por chave (fonte)."""

    def __init__(self, *, default_rpm: int = 30) -> None:
        self._default_rpm = default_rpm
        self._limits: Dict[str, int] = {}
        self._windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._locks: Dict[str, asyncio.Lock] = {}

    def configure(self, source: str, rpm: int) -> None:
        self._limits[source] = rpm

    async def acquire(self, source: str) -> None:
        """Aguarda até que o limite por minuto seja respeitado."""
        limit = self._limits.get(source, self._default_rpm)
        if source not in self._locks:
            self._locks[source] = asyncio.Lock()
        async with self._locks[source]:
            window = self._windows[source]
            now = time.monotonic()
            # Remove entradas mais antigas que 60s
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= limit:
                # Calcula tempo de espera
                oldest = window[0]
                wait = 60 - (now - oldest)
                if wait > 0:
                    await asyncio.sleep(wait)
                # Re-limpa após espera
                now = time.monotonic()
                while window and window[0] <= now - 60:
                    window.popleft()
            window.append(time.monotonic())

    def reset(self, source: Optional[str] = None) -> None:
        if source:
            self._windows[source].clear()
        else:
            self._windows.clear()


_limiter: Optional[AsyncRateLimiter] = None


def get_rate_limiter() -> AsyncRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = AsyncRateLimiter()
    return _limiter


__all__ = ["AsyncRateLimiter", "get_rate_limiter"]
