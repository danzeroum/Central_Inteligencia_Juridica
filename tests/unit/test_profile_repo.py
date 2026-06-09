"""Testes unitários — ProfileRepository (CRUD + vínculo advogado-cliente)."""

from __future__ import annotations

import pytest

from src.profiles.repository import ProfileRepository
from src.profiles.schemas import ClienteProfile, GenericUserProfile


@pytest.fixture
def repo():
    r = ProfileRepository()
    # Forçar uso do backend em memória
    r._store._client = None
    r._store._memory = {}
    return r


@pytest.mark.asyncio
async def test_save_and_get_user(repo):
    p = GenericUserProfile(user_id="u1", name="Dra. Becker")
    await repo.save(p)
    retrieved = await repo.get("u1")
    assert retrieved is not None
    assert retrieved.name == "Dra. Becker"


@pytest.mark.asyncio
async def test_delete_user_lgpd(repo):
    p = GenericUserProfile(user_id="u2", name="Dr. Melo")
    await repo.save(p)
    deleted = await repo.delete("u2")
    assert deleted is True
    assert await repo.get("u2") is None


@pytest.mark.asyncio
async def test_save_and_list_clientes(repo):
    c1 = ClienteProfile(cliente_id="c1", advogado_id="adv1", nome="Empresa Alpha")
    c2 = ClienteProfile(cliente_id="c2", advogado_id="adv1", nome="Empresa Beta")
    await repo.save_client(c1)
    await repo.save_client(c2)

    clientes = await repo.list_clients("adv1")
    nomes = {c.nome for c in clientes}
    assert "Empresa Alpha" in nomes
    assert "Empresa Beta" in nomes


@pytest.mark.asyncio
async def test_get_specific_client(repo):
    c = ClienteProfile(cliente_id="c3", advogado_id="adv2", nome="Pessoa Física")
    await repo.save_client(c)
    retrieved = await repo.get_client("adv2", "c3")
    assert retrieved is not None
    assert retrieved.nome == "Pessoa Física"


@pytest.mark.asyncio
async def test_client_isolation_between_advogados(repo):
    c1 = ClienteProfile(cliente_id="cx", advogado_id="adv_a", nome="A")
    c2 = ClienteProfile(cliente_id="cx", advogado_id="adv_b", nome="B")
    await repo.save_client(c1)
    await repo.save_client(c2)

    r_a = await repo.get_client("adv_a", "cx")
    r_b = await repo.get_client("adv_b", "cx")
    assert r_a.nome == "A"
    assert r_b.nome == "B"


@pytest.mark.asyncio
async def test_update_profile(repo):
    p = GenericUserProfile(user_id="u3", name="Antes")
    await repo.save(p)
    updated = await repo.update("u3", {"name": "Depois"})
    assert updated.name == "Depois"
