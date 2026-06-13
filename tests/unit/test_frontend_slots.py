"""Testes unitários — FrontendSlot, slots endpoint e integração com ModuleRegistry."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# FrontendSlot dataclass
# ---------------------------------------------------------------------------


def test_slot_defaults():
    from src.modules.slots import FrontendSlot

    s = FrontendSlot(label="Foo", icon="star", route="/app/foo")
    assert s.order == 0
    assert s.enabled is True


def test_slot_to_dict():
    from src.modules.slots import FrontendSlot

    s = FrontendSlot(label="Bar", icon="home", route="/app/bar", order=5, enabled=False)
    d = s.to_dict()
    assert d == {
        "label": "Bar",
        "icon": "home",
        "route": "/app/bar",
        "order": 5,
        "enabled": False,
        "screen_id": None,
    }


# ---------------------------------------------------------------------------
# ModuleManifest com slot
# ---------------------------------------------------------------------------


def test_manifest_with_slot_to_dict():
    from src.modules.manifest import ModuleManifest
    from src.modules.slots import FrontendSlot

    m = ModuleManifest(
        module_id="test",
        name="Test",
        slot=FrontendSlot(label="Test Menu", icon="test", route="/app/test", order=10),
    )
    d = m.to_dict()
    assert d["slot"] == {
        "label": "Test Menu",
        "icon": "test",
        "route": "/app/test",
        "order": 10,
        "enabled": True,
        "screen_id": None,
    }


def test_manifest_without_slot_to_dict():
    from src.modules.manifest import ModuleManifest

    m = ModuleManifest(module_id="no_slot", name="No Slot Module")
    d = m.to_dict()
    assert d["slot"] is None


# ---------------------------------------------------------------------------
# Built-in modules têm slots definidos
# ---------------------------------------------------------------------------


def test_builtin_modules_have_slots():
    from src.modules.core import BUILTIN_MODULES

    for m in BUILTIN_MODULES:
        assert m.slot is not None, f"Módulo '{m.module_id}' não tem slot definido"
        assert m.slot.label
        assert m.slot.route.startswith("/app/")


def test_builtin_slots_have_distinct_orders():
    from src.modules.core import BUILTIN_MODULES

    orders = [m.slot.order for m in BUILTIN_MODULES if m.slot]
    assert len(orders) == len(set(orders)), "Dois módulos têm o mesmo order de slot"


# ---------------------------------------------------------------------------
# Slots endpoint
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_client():
    from src.api.main import app

    with TestClient(app) as c:
        yield c


def test_slots_endpoint_returns_200(api_client):
    resp = api_client.get("/api/v1/slots")
    assert resp.status_code == 200


def test_slots_endpoint_returns_builtin_slots(api_client):
    """Verifica que o endpoint retorna pelo menos os slots dos módulos built-in."""
    from src.modules.core import BUILTIN_MODULES

    expected = sum(1 for m in BUILTIN_MODULES if m.is_active and m.slot is not None)
    resp = api_client.get("/api/v1/slots")
    body = resp.json()
    assert body["total"] == expected
    assert len(body["slots"]) == expected


def test_slots_are_ordered_by_order_field(api_client):
    resp = api_client.get("/api/v1/slots")
    slots = resp.json()["slots"]
    orders = [s["order"] for s in slots]
    assert orders == sorted(orders), "Slots não estão ordenados pelo campo 'order'"


def test_slots_schema_fields(api_client):
    resp = api_client.get("/api/v1/slots")
    slot = resp.json()["slots"][0]
    assert "label" in slot
    assert "icon" in slot
    assert "route" in slot
    assert "order" in slot
    assert "enabled" in slot
    assert slot["route"].startswith("/app/")


def test_disabled_slot_excluded_from_response():
    """Módulo com slot desativado não aparece no endpoint /api/v1/slots."""
    import src.modules.registry as reg_module
    from src.modules.manifest import ModuleManifest
    from src.modules.slots import FrontendSlot

    old_registry = reg_module._registry
    try:
        reg_module._registry = None
        registry = reg_module.get_module_registry()
        registry.register(
            ModuleManifest(
                module_id="disabled_slot_module",
                name="Disabled Slot",
                slot=FrontendSlot(
                    label="Disabled", icon="block", route="/app/disabled", enabled=False
                ),
            )
        )

        from src.api.main import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/slots")
            routes = [s["route"] for s in resp.json()["slots"]]
            assert "/app/disabled" not in routes
    finally:
        reg_module._registry = old_registry


def test_modules_endpoint_includes_slot_field(api_client):
    """GET /api/v1/modules retorna campo 'slot' em cada módulo."""
    resp = api_client.get("/api/v1/modules")
    for module in resp.json()["modules"]:
        assert "slot" in module
        slot = module["slot"]
        assert slot is not None
        assert "label" in slot
        assert "route" in slot
