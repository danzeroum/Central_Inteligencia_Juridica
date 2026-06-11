"""Fábricas de engine SQLAlchemy (async e sync).

- ``get_async_engine`` → asyncpg, usado pelo FastAPI (I/O não-bloqueante).
- ``get_sync_engine``  → psycopg2, usado pelo ledger e pelo Alembic (sync).

Ambas retornam ``None`` quando ``DATABASE_URL`` não está configurada,
permitindo que a aplicação suba sem Postgres (modo compatibilidade Onda 1).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def _database_url() -> Optional[str]:
    return os.getenv("DATABASE_URL") or None


def _to_async_url(url: str) -> str:
    """Normaliza para o driver asyncpg."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _to_sync_url(url: str) -> str:
    """Normaliza para o driver psycopg2 (sem sufixo de driver)."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "postgresql+asyncpg://" in url:
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


@lru_cache(maxsize=1)
def get_async_engine() -> Optional[AsyncEngine]:
    """Retorna o engine assíncrono (singleton). None se DATABASE_URL ausente."""
    url = _database_url()
    if not url:
        return None
    return create_async_engine(
        _to_async_url(url),
        echo=False,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_sync_engine() -> Optional[Engine]:
    """Retorna o engine síncrono (singleton). None se DATABASE_URL ausente."""
    url = _database_url()
    if not url:
        return None
    return create_engine(
        _to_sync_url(url),
        echo=False,
        pool_pre_ping=True,
    )
