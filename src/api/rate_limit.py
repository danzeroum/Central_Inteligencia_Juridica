"""Dependência de rate limiting COMPARTILHADA (H14).

Extraída de ``main.py`` para um módulo próprio para que os routers
(training/autonomy/ledger) possam aplicá-la sem criar import circular
(``main`` importa os routers; os routers importariam ``main``). O limiter é um
singleton de processo, configurável por ``RATE_LIMIT_PER_MINUTE``.
"""

from __future__ import annotations

import os

from fastapi import Request

from src.api.rate_limiter import RateLimiter

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

# Em teste o limite é alto para não introduzir flakiness (suíte compartilha IP).
_DEFAULT_RATE_LIMIT = 100_000 if ENVIRONMENT == "test" else 60
RATE_LIMIT_PER_MINUTE = int(
    os.getenv("RATE_LIMIT_PER_MINUTE", str(_DEFAULT_RATE_LIMIT))
)

limiter = RateLimiter(requests_per_minute=RATE_LIMIT_PER_MINUTE)


async def enforce_rate_limit(request: Request) -> None:
    """Dependência FastAPI que aplica o rate limiting por IP."""

    await limiter(request)


__all__ = ["enforce_rate_limit", "limiter", "RATE_LIMIT_PER_MINUTE"]
