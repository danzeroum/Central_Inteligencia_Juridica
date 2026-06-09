"""Módulo de perfis de usuário — CIJ v1.1.0."""

from __future__ import annotations

from src.profiles.repository import ProfileRepository
from src.profiles.profile_store import ProfileStore
from src.profiles.schemas import (
    AreaJuridica,
    ClienteProfile,
    GenericUserProfile,
    LegalAreaProfile,
    Role,
)

__all__ = [
    "GenericUserProfile",
    "ClienteProfile",
    "LegalAreaProfile",
    "AreaJuridica",
    "Role",
    "ProfileRepository",
    "ProfileStore",
]
