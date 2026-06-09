"""Migrações de versão de perfil (v1→v2, etc.). Nunca deleta histórico."""

from __future__ import annotations

import logging
from typing import Dict

from src.profiles.schemas import GenericUserProfile

logger = logging.getLogger(__name__)

_CURRENT_VERSION = 1

_MIGRATIONS: Dict[int, callable] = {}  # type: ignore[type-arg]


def _migration(from_version: int):
    def decorator(fn):
        _MIGRATIONS[from_version] = fn
        return fn

    return decorator


class ProfileMigrator:
    """Aplica migrações encadeadas até atingir a versão atual."""

    @staticmethod
    def migrate(profile: GenericUserProfile) -> GenericUserProfile:
        version = profile.profile_version
        while version in _MIGRATIONS:
            logger.info(
                "Migrando perfil %s: v%d → v%d",
                profile.user_id,
                version,
                version + 1,
            )
            data = profile.model_dump()
            data = _MIGRATIONS[version](data)
            profile = GenericUserProfile(**data)
            version = profile.profile_version
        return profile


@_migration(1)
def _v1_to_v2(data: dict) -> dict:
    """Exemplo de migração v1→v2: normaliza 'areas_atuacao' para 'especialidades'."""
    if "areas_atuacao" in data and "especialidades" not in data:
        data["especialidades"] = data.pop("areas_atuacao")
    data["profile_version"] = 2
    return data


__all__ = ["ProfileMigrator"]
