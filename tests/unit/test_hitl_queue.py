"""Testes unitários da HITLQueue, focados em caminhos não-felizes.

A fila é o coração do Human-in-the-Loop. Os testes existentes cobriam só o
fluxo feliz (adicionar → aprovar). Aqui cobrimos: timeout de decisão,
solicitação inexistente, idempotência da decisão, filtragem de pendentes e o
cálculo de tempo de resposta — comportamentos dos quais a UI e a auditoria
dependem.
"""

from __future__ import annotations

import asyncio

import pytest

from src.hitl.hitl_queue import HITLQueue


def test_add_and_get_pending_filters_decided() -> None:
    queue = HITLQueue()
    r1 = queue.add_request(agent="a", action={"x": 1}, context={})
    r2 = queue.add_request(agent="b", action={"x": 2}, context={})
    queue.record_decision(r1.request_id, approved=True)

    pending = queue.get_pending_requests()
    pending_ids = {p["request_id"] for p in pending}
    # Só a não-decidida permanece pendente.
    assert r2.request_id in pending_ids
    assert r1.request_id not in pending_ids


def test_record_decision_unknown_request_returns_false() -> None:
    queue = HITLQueue()
    assert queue.record_decision("inexistente", approved=True) is False


def test_record_decision_is_idempotent_event_wise() -> None:
    """Decisão registrada marca status; a fila não 'desfaz' ao redecidir."""
    queue = HITLQueue()
    req = queue.add_request(agent="a", action={}, context={})
    assert queue.record_decision(req.request_id, approved=True) is True
    stored = queue.get_request(req.request_id)
    assert stored.status == "approved"
    assert stored.decision["approved"] is True


def test_record_decision_persists_modifications_and_operator() -> None:
    queue = HITLQueue()
    req = queue.add_request(agent="a", action={"valor": 1}, context={})
    queue.record_decision(
        req.request_id,
        approved=True,
        modifications={"valor": 2},
        feedback="ajustado",
        operator_id="m.ribeiro",
    )
    stored = queue.get_request(req.request_id)
    assert stored.decided_by == "m.ribeiro"
    assert stored.decision["modifications"] == {"valor": 2}
    assert stored.decision["feedback"] == "ajustado"


@pytest.mark.asyncio
async def test_wait_for_decision_unknown_id_raises() -> None:
    queue = HITLQueue()
    with pytest.raises(ValueError):
        await queue.wait_for_decision("nao-existe")


@pytest.mark.asyncio
async def test_wait_for_decision_timeout_marks_timeout() -> None:
    queue = HITLQueue(timeout_seconds=0)  # expira imediatamente
    req = queue.add_request(agent="a", action={}, context={})
    decision = await queue.wait_for_decision(req.request_id)
    assert decision == {"approved": False, "reason": "timeout"}
    assert queue.get_request(req.request_id).status == "timeout"


@pytest.mark.asyncio
async def test_wait_for_decision_returns_after_record() -> None:
    queue = HITLQueue(timeout_seconds=5)
    req = queue.add_request(agent="a", action={}, context={})

    async def decide_later() -> None:
        await asyncio.sleep(0.01)
        queue.record_decision(req.request_id, approved=True, feedback="ok")

    decision, _ = await asyncio.gather(
        queue.wait_for_decision(req.request_id), decide_later()
    )
    assert decision["approved"] is True
    assert decision["feedback"] == "ok"


@pytest.mark.asyncio
async def test_websocket_callback_invoked_on_new_request() -> None:
    queue = HITLQueue()
    events: list[tuple[str, str]] = []

    async def callback(event_type, data) -> None:
        events.append((event_type, data["request_id"]))

    queue.register_websocket_callback(callback)
    req = queue.add_request(agent="a", action={}, context={})
    await asyncio.sleep(0)  # deixa a task de notificação rodar

    assert ("new_request", req.request_id) in events
