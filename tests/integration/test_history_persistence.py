"""Frente B (API-07): histórico durável no DecisionLedger + paginação cursor.

Garante que ``GET /api/v1/history`` lê do ledger (e não mais de uma lista em
memória que se perde no restart), que a paginação cursor-based funciona ponta a
ponta, e que as entradas sobrevivem a um "restart" (nova instância lendo o mesmo
arquivo).
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api import main as main_module  # noqa: E402
from src.api.main import app, _decode_cursor, _encode_cursor  # noqa: E402
from src.utils.ledger import DecisionLedger  # noqa: E402

client = TestClient(app)


@pytest.fixture
def temp_ledger(tmp_path, monkeypatch):
    """Substitui o ledger do supervisor por um isolado em arquivo temporário."""

    ledger = DecisionLedger(log_file=str(tmp_path / "ledger.json"))
    monkeypatch.setattr(main_module.supervisor_agent, "ledger", ledger)
    return ledger


def _seed(ledger: DecisionLedger, count: int) -> None:
    for i in range(count):
        ledger.log_decision(
            agent_type="SupervisorAgent",
            decision_type="TASK_COMPLETED",
            metadata={
                "task": f"consulta {i}",
                "operation": "consulta_processual",
                "tribunals": ["TJSP"],
            },
        )


def test_history_reads_from_ledger(temp_ledger):
    _seed(temp_ledger, 3)
    body = client.get("/api/v1/history").json()

    assert body["total"] == 3
    assert body["count"] == 3
    # Mais recente primeiro.
    assert body["history"][0]["task"] == "consulta 2"
    assert body["history"][0]["operation"] == "consulta_processual"
    assert body["history"][0]["tribunals"] == ["TJSP"]
    assert body["history"][0]["status"] == "concluida"


def test_history_cursor_pagination(temp_ledger):
    _seed(temp_ledger, 5)

    p1 = client.get("/api/v1/history", params={"limit": 2}).json()
    assert p1["count"] == 2 and p1["total"] == 5
    assert p1["cursor"] is not None

    p2 = client.get(
        "/api/v1/history", params={"limit": 2, "cursor": p1["cursor"]}
    ).json()
    assert p2["count"] == 2

    # Páginas não se sobrepõem.
    tasks1 = {h["task"] for h in p1["history"]}
    tasks2 = {h["task"] for h in p2["history"]}
    assert tasks1.isdisjoint(tasks2)

    p3 = client.get(
        "/api/v1/history", params={"limit": 2, "cursor": p2["cursor"]}
    ).json()
    assert p3["count"] == 1
    assert p3["cursor"] is None  # última página


def test_history_invalid_cursor_is_400(temp_ledger):
    resp = client.get("/api/v1/history", params={"cursor": "!!!nao-base64!!!"})
    assert resp.status_code == 400


def test_history_survives_restart(tmp_path):
    """Durabilidade: uma segunda instância lê o que a primeira gravou."""

    path = str(tmp_path / "durable.json")
    led1 = DecisionLedger(log_file=path)
    led1.log_decision(
        agent_type="SupervisorAgent",
        decision_type="TASK_COMPLETED",
        metadata={"task": "persistida", "operation": "x", "tribunals": []},
    )

    # Simula restart do processo: nova instância carrega do mesmo arquivo.
    led2 = DecisionLedger(log_file=path)
    entries = led2.get_entries(decision_type="TASK_COMPLETED")
    assert any(e["metadata"]["task"] == "persistida" for e in entries)


def test_cursor_roundtrip():
    assert _decode_cursor(_encode_cursor(7)) == 7
    assert _decode_cursor(None) == 0
