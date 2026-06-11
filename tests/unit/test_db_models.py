"""Testes unitários da camada src/db — estrutura de modelos e engine.

Valida declarações ORM, mapeamento de colunas e comportamento do engine
sem precisar de um PostgreSQL rodando (usa SQLite em memória para os modelos
portáveis; o PostgresLedgerStore fica nos testes de integração).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from src.db.base import Base
from src.db.models import FiscalAudit, LedgerEntry, License, Module, Tenant


@pytest.fixture(scope="module")
def sqlite_engine():
    """Engine SQLite em memória para validar schema dos modelos."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine):
    with Session(sqlite_engine) as session:
        yield session
        session.rollback()


# ─── Testes de schema ───────────────────────────────────────────────────────


def test_all_tables_created(sqlite_engine):
    insp = inspect(sqlite_engine)
    tables = insp.get_table_names()
    assert "tenant" in tables
    assert "module" in tables
    assert "license" in tables
    assert "ledger_entry" in tables
    assert "fiscal_audit" in tables


def test_tenant_columns(sqlite_engine):
    insp = inspect(sqlite_engine)
    cols = {c["name"] for c in insp.get_columns("tenant")}
    assert {
        "id",
        "name",
        "document_masked",
        "is_active",
        "created_at",
        "updated_at",
    } <= cols


def test_ledger_entry_columns(sqlite_engine):
    insp = inspect(sqlite_engine)
    cols = {c["name"] for c in insp.get_columns("ledger_entry")}
    assert {
        "id",
        "agent_type",
        "decision_type",
        "metadata",
        "timestamp",
        "timestamp_readable",
    } <= cols


def test_fiscal_audit_columns(sqlite_engine):
    insp = inspect(sqlite_engine)
    cols = {c["name"] for c in insp.get_columns("fiscal_audit")}
    assert {
        "id",
        "tenant_id",
        "operation",
        "entity_type",
        "entity_ref",
        "status",
        "details",
        "created_at",
    } <= cols


# ─── Testes de CRUD básico ──────────────────────────────────────────────────


def test_tenant_insert_and_read(db_session):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Escritório Exemplo",
        document_masked="**.***.***/****-**",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.flush()

    result = db_session.get(Tenant, tenant.id)
    assert result is not None
    assert result.name == "Escritório Exemplo"
    assert result.document_masked == "**.***.***/****-**"


def test_module_insert(db_session):
    mod = Module(
        id="inteligencia_juridica",
        version="1.0.0",
        name="Inteligência Jurídica",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(mod)
    db_session.flush()

    result = db_session.get(Module, "inteligencia_juridica")
    assert result is not None
    assert result.version == "1.0.0"


def test_ledger_entry_insert(db_session):
    entry = LedgerEntry(
        id="decision_000001",
        agent_type="supervisor",
        decision_type="TASK_DELEGATED",
        metadata_={"task": "consulta_juridica"},
        timestamp=datetime.now(timezone.utc),
        timestamp_readable="2026-06-11 10:00:00",
    )
    db_session.add(entry)
    db_session.flush()

    result = db_session.get(LedgerEntry, "decision_000001")
    assert result is not None
    assert result.agent_type == "supervisor"
    assert result.metadata_["task"] == "consulta_juridica"


def test_fiscal_audit_insert(db_session):
    audit = FiscalAudit(
        id=uuid.uuid4(),
        tenant_id=None,
        operation="import",
        entity_type="efd_icms",
        entity_ref="corr-123",
        status="completed",
        details={"rows": 1000},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(audit)
    db_session.flush()

    result = db_session.get(FiscalAudit, audit.id)
    assert result is not None
    assert result.operation == "import"
    assert result.details["rows"] == 1000


# ─── Testes do engine factory ───────────────────────────────────────────────


def test_get_async_engine_returns_none_without_url():
    """Sem DATABASE_URL, get_async_engine retorna None (modo compat Onda 1)."""
    from src.db import engine as _engine_mod

    # Limpa cache entre testes
    _engine_mod.get_async_engine.cache_clear()
    _engine_mod.get_sync_engine.cache_clear()

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("DATABASE_URL", None)
        result = _engine_mod.get_async_engine()
    assert result is None

    _engine_mod.get_async_engine.cache_clear()
    _engine_mod.get_sync_engine.cache_clear()


def test_get_sync_engine_returns_none_without_url():
    from src.db import engine as _engine_mod

    _engine_mod.get_async_engine.cache_clear()
    _engine_mod.get_sync_engine.cache_clear()

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("DATABASE_URL", None)
        result = _engine_mod.get_sync_engine()
    assert result is None

    _engine_mod.get_async_engine.cache_clear()
    _engine_mod.get_sync_engine.cache_clear()


def test_async_url_normalization():
    from src.db.engine import _to_async_url

    assert (
        _to_async_url("postgresql://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"
    )
    assert _to_async_url("postgres://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"
    assert (
        _to_async_url("postgresql+asyncpg://u:p@host/db")
        == "postgresql+asyncpg://u:p@host/db"
    )


def test_sync_url_normalization():
    from src.db.engine import _to_sync_url

    assert (
        _to_sync_url("postgresql+asyncpg://u:p@host/db") == "postgresql://u:p@host/db"
    )
    assert _to_sync_url("postgres://u:p@host/db") == "postgresql://u:p@host/db"
    assert _to_sync_url("postgresql://u:p@host/db") == "postgresql://u:p@host/db"
