"""Testes unitários — ProfileMigrator."""

from __future__ import annotations

from src.profiles.migrations import ProfileMigrator
from src.profiles.schemas import AreaJuridica, GenericUserProfile


def test_migrate_v1_profile_unchanged():
    p = GenericUserProfile(user_id="u1", name="X", profile_version=1)
    migrated = ProfileMigrator.migrate(p)
    # v1 → v2 migration exists; result should be v2
    assert migrated.profile_version == 2


def test_migrate_v1_to_v2_preserves_data():
    p = GenericUserProfile(
        user_id="u1",
        name="Advogado Teste",
        profile_version=1,
        especialidades=[AreaJuridica.CIVIL],
    )
    migrated = ProfileMigrator.migrate(p)
    assert migrated.name == "Advogado Teste"
    assert migrated.user_id == "u1"


def test_migrate_already_current_version():
    p = GenericUserProfile(user_id="u1", name="X", profile_version=99)
    migrated = ProfileMigrator.migrate(p)
    # No migration for v99 — unchanged
    assert migrated.profile_version == 99


def test_migrate_normalizes_areas_atuacao():
    """Migração v1→v2 deve converter 'areas_atuacao' para 'especialidades'."""
    data = {
        "user_id": "u1",
        "name": "X",
        "profile_version": 1,
        "especialidades": [],
        "areas_atuacao": ["trabalhista"],
    }
    from src.profiles.migrations import _v1_to_v2

    result = _v1_to_v2(data)
    assert result["profile_version"] == 2
