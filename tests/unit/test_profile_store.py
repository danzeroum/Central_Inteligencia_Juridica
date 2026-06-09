"""Testes unitários — ProfileStore (Redis mock)."""

from __future__ import annotations

import pytest

from src.profiles.profile_store import ProfileStore
from src.profiles.schemas import AreaJuridica, GenericUserProfile


@pytest.fixture
def store():
    s = ProfileStore()
    # Garante uso do backend em memória
    s._client = None
    s._memory = {}
    return s


@pytest.mark.asyncio
async def test_save_and_get_profile(store):
    p = GenericUserProfile(user_id="user1", name="Ana")
    await store.save_profile(p)
    retrieved = await store.get_profile("user1")
    assert retrieved is not None
    assert retrieved.user_id == "user1"
    assert retrieved.name == "Ana"


@pytest.mark.asyncio
async def test_get_nonexistent_profile(store):
    result = await store.get_profile("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_update_profile(store):
    p = GenericUserProfile(user_id="user2", name="Bob")
    await store.save_profile(p)
    updated = await store.update_profile("user2", {"name": "Bob Atualizado"})
    assert updated is not None
    assert updated.name == "Bob Atualizado"


@pytest.mark.asyncio
async def test_update_nonexistent_profile(store):
    result = await store.update_profile("ghost", {"name": "X"})
    assert result is None


@pytest.mark.asyncio
async def test_delete_profile_lgpd(store):
    p = GenericUserProfile(user_id="user3", name="Carlos")
    await store.save_profile(p)
    deleted = await store.delete_profile("user3")
    assert deleted is True
    retrieved = await store.get_profile("user3")
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_nonexistent_profile(store):
    result = await store.delete_profile("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_multitenancy_isolation(store):
    p1 = GenericUserProfile(user_id="tenant1", name="T1")
    p2 = GenericUserProfile(user_id="tenant2", name="T2")
    await store.save_profile(p1)
    await store.save_profile(p2)

    r1 = await store.get_profile("tenant1")
    r2 = await store.get_profile("tenant2")
    assert r1.name == "T1"
    assert r2.name == "T2"
    assert r1.user_id != r2.user_id


@pytest.mark.asyncio
async def test_save_profile_with_especialidades(store):
    p = GenericUserProfile(
        user_id="adv1",
        name="Dra. Silva",
        especialidades=[AreaJuridica.TRABALHISTA],
    )
    await store.save_profile(p)
    retrieved = await store.get_profile("adv1")
    assert retrieved is not None
    assert AreaJuridica.TRABALHISTA in retrieved.especialidades
