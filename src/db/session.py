"""Fábricas de sessão SQLAlchemy (async e sync).

Uso típico:
  # FastAPI dependency (async)
  @router.get("/foo")
  async def handler(db: AsyncSession = Depends(get_db)):
      ...

  # Código sync (ledger, scripts)
  with get_sync_session() as session:
      session.add(obj)
      session.commit()
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from src.db.engine import get_async_engine, get_sync_engine


def _async_factory() -> Optional[async_sessionmaker[AsyncSession]]:
    engine = get_async_engine()
    return async_sessionmaker(engine, expire_on_commit=False) if engine else None


def _sync_factory() -> Optional[sessionmaker[Session]]:
    engine = get_sync_engine()
    return sessionmaker(engine) if engine else None


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager para sessão assíncrona. Lança RuntimeError se DATABASE_URL ausente."""
    factory = _async_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL não configurada — sessão async indisponível.")
    async with factory() as session:
        try:
            yield session
        finally:
            # DT-11: SQLAlchemy 2 autobegin abre transação implícita mesmo em leituras.
            # Sem rollback explícito, o Postgres loga "unexpected EOF on client connection
            # with an open transaction" ao fechar a conexão de pool.
            if session.in_transaction():
                await session.rollback()


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Context manager para sessão síncrona. Lança RuntimeError se DATABASE_URL ausente."""
    factory = _sync_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL não configurada — sessão sync indisponível.")
    with factory() as session:
        yield session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependência FastAPI: injeta AsyncSession por request."""
    async with get_async_session() as session:
        yield session
