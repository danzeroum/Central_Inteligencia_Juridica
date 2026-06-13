"""Testes unitários — ModuleRegistry, ModuleManifest, license_gate e AgentInterface."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# ModuleManifest
# ---------------------------------------------------------------------------


def test_manifest_defaults():
    from src.modules.manifest import ModuleManifest

    m = ModuleManifest(module_id="test", name="Test Module")
    assert m.version == "1.0.0"
    assert m.is_active is True
    assert m.capabilities == []
    assert m.endpoints == []


def test_manifest_to_dict_roundtrip():
    from src.modules.manifest import ModuleManifest

    m = ModuleManifest(
        module_id="foo",
        name="Foo",
        version="3.0.0",
        capabilities=["a", "b"],
        is_active=False,
    )
    d = m.to_dict()
    assert d["module_id"] == "foo"
    assert d["version"] == "3.0.0"
    assert d["capabilities"] == ["a", "b"]
    assert d["is_active"] is False


# ---------------------------------------------------------------------------
# ModuleRegistry
# ---------------------------------------------------------------------------


def test_registry_register_and_get():
    from src.modules.manifest import ModuleManifest
    from src.modules.registry import ModuleRegistry

    reg = ModuleRegistry()
    m = ModuleManifest(module_id="x", name="X")
    reg.register(m)
    assert reg.get("x") == m
    assert reg.get("missing") is None


def test_registry_list_active_filters_inactive():
    from src.modules.manifest import ModuleManifest
    from src.modules.registry import ModuleRegistry

    reg = ModuleRegistry()
    reg.register(ModuleManifest(module_id="active", name="A", is_active=True))
    reg.register(ModuleManifest(module_id="inactive", name="B", is_active=False))

    active = reg.list_active()
    all_modules = reg.list_all()

    assert len(active) == 1
    assert active[0].module_id == "active"
    assert len(all_modules) == 2


def test_registry_deactivate():
    from src.modules.manifest import ModuleManifest
    from src.modules.registry import ModuleRegistry

    reg = ModuleRegistry()
    reg.register(ModuleManifest(module_id="m", name="M"))
    assert reg.deactivate("m") is True
    assert reg.get("m").is_active is False
    assert reg.deactivate("nonexistent") is False


def test_registry_overwrite_on_re_register():
    from src.modules.manifest import ModuleManifest
    from src.modules.registry import ModuleRegistry

    reg = ModuleRegistry()
    reg.register(ModuleManifest(module_id="m", name="Old", version="1.0.0"))
    reg.register(ModuleManifest(module_id="m", name="New", version="2.0.0"))
    assert reg.get("m").version == "2.0.0"


# ---------------------------------------------------------------------------
# Built-in modules + singleton
# ---------------------------------------------------------------------------


def test_builtin_modules_count():
    from src.modules.core import BUILTIN_MODULES

    assert len(BUILTIN_MODULES) >= 3
    ids = {m.module_id for m in BUILTIN_MODULES}
    assert "juridico_core" in ids
    assert "legislativo" in ids
    assert "jurisprudencia" in ids
    # Bloco A (Onda 2)
    assert "cadastro_risco" in ids
    assert "consultoria_tributaria" in ids


def test_get_module_registry_singleton_has_builtins():
    """get_module_registry() retorna o singleton com os built-ins pré-carregados."""
    import importlib
    import src.modules.registry as reg_module

    reg_module._registry = None  # reset singleton for this test
    registry = reg_module.get_module_registry()
    active = registry.list_active()
    assert len(active) >= 3
    module_ids = {m.module_id for m in active}
    assert "juridico_core" in module_ids


# ---------------------------------------------------------------------------
# AgentInterface Protocol
# ---------------------------------------------------------------------------


def test_agent_interface_is_runtime_checkable():
    from src.protocols.agent_interface import AgentInterface

    class FakeAgent:
        agent_id = "fake_001"
        agent_type = "FakeAgent"
        tools = []

        async def execute(self, task):
            return {}

    assert isinstance(FakeAgent(), AgentInterface)


def test_base_agent_subclass_satisfies_interface():
    """Agentes que estendem BaseAgent satisfazem o protocolo sem herança explícita."""
    from src.agents.architect_agent import ArchitectAgent
    from src.protocols.agent_interface import AgentInterface

    agent = ArchitectAgent()
    assert isinstance(agent, AgentInterface)


def test_object_missing_execute_does_not_satisfy():
    from src.protocols.agent_interface import AgentInterface

    class NotAnAgent:
        agent_id = "x"
        agent_type = "X"
        tools = []
        # no execute()

    assert not isinstance(NotAnAgent(), AgentInterface)


# ---------------------------------------------------------------------------
# License gate — comportamento em ENVIRONMENT=test / sem DATABASE_URL
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_client():
    from src.api.main import app

    with TestClient(app) as c:
        yield c


def test_modules_list_endpoint_returns_builtins(api_client):
    resp = api_client.get("/api/v1/modules")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 3
    ids = {m["module_id"] for m in body["modules"]}
    assert "juridico_core" in ids
    assert "legislativo" in ids
    assert "jurisprudencia" in ids


def test_modules_detail_endpoint(api_client):
    resp = api_client.get("/api/v1/modules/juridico_core")
    assert resp.status_code == 200
    body = resp.json()
    assert body["module_id"] == "juridico_core"
    assert "SupervisorAgent" in body["agent_types"]


def test_modules_detail_404_on_unknown(api_client):
    resp = api_client.get("/api/v1/modules/does_not_exist")
    assert resp.status_code == 404


def test_license_gate_allows_in_test_env(api_client):
    """Em ENVIRONMENT=test sem DATABASE_URL, o módulo list não deve ser bloqueado."""
    import os

    # Garante que o ambiente de teste não tem DATABASE_URL configurado
    assert not os.getenv("DATABASE_URL"), "DATABASE_URL não deve estar set em testes"

    # O endpoint de módulos deve responder 200 sem nenhum token
    resp = api_client.get("/api/v1/modules/juridico_core")
    assert resp.status_code == 200
