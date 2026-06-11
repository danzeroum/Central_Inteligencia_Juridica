"""Testes de integração — PostgresLedgerStore.

Requer DATABASE_URL configurada apontando para um PostgreSQL real com a
migração 0001 aplicada. Marcados com ``@pytest.mark.integration`` e
ignorados automaticamente quando DATABASE_URL não está disponível.

Execução manual:
    DATABASE_URL=postgresql://cij:senha@localhost:5432/cij_test \
    pytest tests/integration/test_postgres_ledger.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def require_database_url():
    """Pula todos os testes se DATABASE_URL não estiver configurada."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip(
            "DATABASE_URL não configurada — pulando testes de integração Postgres"
        )


@pytest.fixture(scope="module")
def pg_engine():
    """Engine síncrono real para o módulo de testes."""
    from src.db.engine import get_sync_engine

    engine = get_sync_engine()
    if engine is None:
        pytest.skip("ENGINE POSTGRES indisponível")
    return engine


@pytest.fixture(scope="module", autouse=True)
def apply_migrations(pg_engine):
    """Aplica migrações Alembic antes dos testes e reverte depois."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(pg_engine.url))
    command.upgrade(cfg, "head")
    yield
    command.downgrade(cfg, "base")


@pytest.fixture
def clean_ledger_table(pg_engine):
    """Limpa a tabela ledger_entry antes de cada teste."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(pg_engine) as s:
        s.execute(text("DELETE FROM ledger_entry"))
        s.commit()
    yield
    with Session(pg_engine) as s:
        s.execute(text("DELETE FROM ledger_entry"))
        s.commit()


@pytest.fixture
def store():
    from src.db.engine import get_sync_engine
    from src.utils.ledger import PostgresLedgerStore

    # Garante que o engine está disponível
    assert get_sync_engine() is not None
    return PostgresLedgerStore()


def _make_entry(n: int = 0) -> dict:
    from datetime import datetime, timezone

    return {
        "id": f"decision_{n:06d}",
        "agent_type": "test_agent",
        "decision_type": "TEST_DECISION",
        "metadata": {"index": n, "tag": "integration"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "timestamp_readable": "2026-06-11 10:00:00",
    }


def test_append_and_load_all(store, clean_ledger_table):
    entry = _make_entry(0)
    store.append(entry)

    rows = store.load_all()
    assert len(rows) == 1
    assert rows[0]["id"] == "decision_000000"
    assert rows[0]["agent_type"] == "test_agent"
    assert rows[0]["metadata"]["index"] == 0


def test_load_all_empty(store, clean_ledger_table):
    assert store.load_all() == []


def test_append_multiple_preserves_order(store, clean_ledger_table):
    for i in range(3):
        store.append(_make_entry(i))

    rows = store.load_all()
    assert len(rows) == 3
    ids = [r["id"] for r in rows]
    assert ids == ["decision_000000", "decision_000001", "decision_000002"]


def test_replace_all(store, clean_ledger_table):
    for i in range(3):
        store.append(_make_entry(i))

    new_entries = [_make_entry(10), _make_entry(11)]
    store.replace_all(new_entries)

    rows = store.load_all()
    assert len(rows) == 2
    assert rows[0]["id"] == "decision_000010"
    assert rows[1]["id"] == "decision_000011"


def test_replace_all_empty_clears_table(store, clean_ledger_table):
    store.append(_make_entry(0))
    store.replace_all([])
    assert store.load_all() == []


def test_store_is_shared():
    from src.utils.ledger import PostgresLedgerStore

    assert PostgresLedgerStore.shared is True


def test_decision_ledger_integration_with_postgres(clean_ledger_table):
    """Valida o fluxo completo via DecisionLedger com backend postgres."""
    import os
    from unittest.mock import patch

    from src.db.engine import get_async_engine, get_sync_engine

    get_async_engine.cache_clear()
    get_sync_engine.cache_clear()

    with patch.dict(os.environ, {"LEDGER_BACKEND": "postgres"}):
        from src.utils.ledger import DecisionLedger

        ledger = DecisionLedger()
        entry_id = ledger.log_decision(
            "integration_agent",
            "INTEGRATION_TEST",
            {"source": "test_postgres_ledger"},
        )

    assert entry_id.startswith("decision_")
    rows = ledger.get_entries(agent_type="integration_agent")
    assert len(rows) >= 1
    assert rows[0]["decision_type"] == "INTEGRATION_TEST"
