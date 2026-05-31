"""Testes dos metadados de auditoria (correlation_id, IP, User-Agent) no ledger.

Garante que decisões sensíveis registram a origem da requisição — rastreabilidade
exigida para operações privilegiadas (quem, de onde, com qual cliente).
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402
from src.utils.request_context import get_audit_context  # noqa: E402

client = TestClient(app)


def test_audit_context_keys_present() -> None:
    ctx = get_audit_context()
    assert set(ctx) == {"correlation_id", "client_ip", "user_agent"}


def test_hitl_decision_records_origin_metadata() -> None:
    from src.hitl.hitl_queue import get_hitl_queue
    from src.utils.ledger import get_ledger

    queue = get_hitl_queue()
    queue.clear()
    req = queue.add_request(agent="a", action={"x": 1}, context={})

    resp = client.post(
        "/api/v1/hitl/decisions",
        json={"request_id": req.request_id, "approved": True},
        headers={
            "User-Agent": "pytest-agent/1.0",
            "X-Forwarded-For": "203.0.113.7, 10.0.0.1",
            "X-Request-ID": "trace-abc",
        },
    )
    assert resp.status_code == 200

    entries = get_ledger().get_entries(decision_type="HITL_DECISION")
    match = next(
        e for e in entries if e["metadata"].get("request_id") == req.request_id
    )
    meta = match["metadata"]
    assert meta["correlation_id"] == "trace-abc"
    # X-Forwarded-For: usa o primeiro IP (cliente real atrás do proxy).
    assert meta["client_ip"] == "203.0.113.7"
    assert meta["user_agent"] == "pytest-agent/1.0"
    queue.clear()
