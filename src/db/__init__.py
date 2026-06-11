"""Camada de persistência relacional (Onda 2 — Bloco 0).

Expõe o essencial para os módulos consumidores sem forçar
a importação de todos os modelos de uma vez.
"""

from src.db.base import Base
from src.db.engine import get_async_engine, get_sync_engine
from src.db.models import FiscalAudit, LedgerEntry, License, Module, Tenant
from src.db.session import get_async_session, get_db, get_sync_session

__all__ = [
    "Base",
    "FiscalAudit",
    "LedgerEntry",
    "License",
    "Module",
    "Tenant",
    "get_async_engine",
    "get_sync_engine",
    "get_async_session",
    "get_db",
    "get_sync_session",
]
