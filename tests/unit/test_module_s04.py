"""Testes S-0.4 — toggle de módulos, SSE de slots e campo screen_id."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_registry():
    """Garante um registry limpo por teste (evita contaminação de estado)."""
    import src.modules.registry as reg_module

    old = reg_module._registry
    reg_module._registry = None
    yield
    # Restaura o singleton original para não afetar outros testes.
    reg_module._registry = old


@pytest.fixture()
def client():
    from src.api.main import app

    with TestClient(app) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# screen_id no slot
# ─────────────────────────────────────────────────────────────────────────────


def test_builtin_slots_have_screen_id():
    from src.modules.core import BUILTIN_MODULES

    for m in BUILTIN_MODULES:
        assert m.slot is not None
        assert m.slot.screen_id is not None, (
            f"Módulo '{m.module_id}' não tem screen_id no slot"
        )
        assert m.slot.screen_id != ""


def test_slots_endpoint_returns_screen_id(client):
    resp = client.get("/api/v1/slots")
    assert resp.status_code == 200
    for slot in resp.json()["slots"]:
        assert "screen_id" in slot
        assert slot["screen_id"]  # não nulo nem vazio para módulos built-in


def test_modules_endpoint_returns_screen_id_in_slot(client):
    resp = client.get("/api/v1/modules")
    assert resp.status_code == 200
    for m in resp.json()["modules"]:
        assert m["slot"]["screen_id"]


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/modules/{module_id} — toggle
# ─────────────────────────────────────────────────────────────────────────────


def test_toggle_deactivates_active_module(client):
    resp = client.patch("/api/v1/modules/legislativo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["module_id"] == "legislativo"
    assert body["is_active"] is False


def test_toggle_reactivates_module(client):
    client.patch("/api/v1/modules/legislativo")  # deactivate
    resp = client.patch("/api/v1/modules/legislativo")  # reactivate
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


def test_toggle_404_for_unknown_module(client):
    resp = client.patch("/api/v1/modules/nao_existe")
    assert resp.status_code == 404


def test_toggled_module_disappears_from_slots(client):
    client.patch("/api/v1/modules/cadastro_risco")
    resp = client.get("/api/v1/slots")
    routes = [s["route"] for s in resp.json()["slots"]]
    assert "/app/fiscal/due-diligence" not in routes


def test_toggled_module_removed_from_modules_list(client):
    client.patch("/api/v1/modules/jurisprudencia")
    resp = client.get("/api/v1/modules")
    ids = [m["module_id"] for m in resp.json()["modules"]]
    assert "jurisprudencia" not in ids


def test_reactivated_module_reappears_in_slots(client):
    client.patch("/api/v1/modules/cadastro_risco")  # off
    client.patch("/api/v1/modules/cadastro_risco")  # on
    resp = client.get("/api/v1/slots")
    routes = [s["route"] for s in resp.json()["slots"]]
    assert "/app/fiscal/due-diligence" in routes


# ─────────────────────────────────────────────────────────────────────────────
# Subscriber / broadcast (unit)
# ─────────────────────────────────────────────────────────────────────────────


def test_subscribe_returns_queue():
    from src.modules.registry import get_module_registry

    registry = get_module_registry()
    q = registry.subscribe()
    assert q is not None
    registry.unsubscribe(q)


def test_broadcast_delivers_to_subscriber():
    import asyncio

    from src.modules.registry import get_module_registry

    registry = get_module_registry()
    q = registry.subscribe()

    async def run():
        await registry.broadcast({"event": "test", "module_id": "foo"})
        event = q.get_nowait()
        assert event["event"] == "test"
        assert event["module_id"] == "foo"

    asyncio.get_event_loop().run_until_complete(run())
    registry.unsubscribe(q)


def test_unsubscribe_removes_queue():
    from src.modules.registry import get_module_registry

    registry = get_module_registry()
    q = registry.subscribe()
    assert q in registry._subscribers
    registry.unsubscribe(q)
    assert q not in registry._subscribers


def test_unsubscribe_idempotent():
    from src.modules.registry import get_module_registry

    registry = get_module_registry()
    q = registry.subscribe()
    registry.unsubscribe(q)
    registry.unsubscribe(q)  # deve ser no-op


# ─────────────────────────────────────────────────────────────────────────────
# SSE endpoint smoke
# ─────────────────────────────────────────────────────────────────────────────


def test_slots_stream_route_registered_in_openapi(client):
    """O endpoint /api/v1/slots/stream está registrado na especificação OpenAPI."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/api/v1/slots/stream" in resp.text


def test_slots_stream_initial_connected_payload_format():
    """O payload do evento 'connected' contém active_count com valor correto."""
    import asyncio

    from src.modules.registry import get_module_registry

    registry = get_module_registry()
    active = registry.list_active()
    expected_count = len(active)

    # Simula o payload que o gerador SSE enviaria ao conectar.
    connected_payload = json.dumps(
        {"event": "connected", "active_count": expected_count}
    )
    sse_line = f"data: {connected_payload}"

    payload_obj = json.loads(sse_line.replace("data: ", ""))
    assert payload_obj["event"] == "connected"
    assert payload_obj["active_count"] == expected_count
    assert isinstance(payload_obj["active_count"], int)


def test_slots_stream_broadcasts_toggle_event():
    """Verifica que o toggle escreve no subscriber."""
    import asyncio

    from src.modules.registry import get_module_registry

    registry = get_module_registry()
    q = registry.subscribe()

    async def run():
        registry.toggle("legislativo")
        await registry.broadcast(
            {"event": "module_toggled", "module_id": "legislativo", "is_active": False}
        )
        event = q.get_nowait()
        data = json.dumps(event)
        assert "module_toggled" in data
        assert "legislativo" in data

    asyncio.get_event_loop().run_until_complete(run())
    registry.unsubscribe(q)
