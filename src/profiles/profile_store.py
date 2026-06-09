"""ProfileStore — persiste perfis de usuário no Redis (multitenancy, LGPD)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.profiles.schemas import GenericUserProfile
from src.utils.redis_client import get_shared_redis_client

logger = logging.getLogger(__name__)

_TTL_SECONDS = 86400 * 30  # 30 dias
_PREFIX = "cij:profile:"


class ProfileStore:
    """CRUD de perfis sobre Redis. Degrada graciosamente quando Redis indisponível."""

    def __init__(self) -> None:
        self._client = get_shared_redis_client(decode_responses=True)
        if self._client is None:
            logger.warning(
                "ProfileStore: Redis indisponível, usando armazenamento em memória."
            )
        self._memory: Dict[str, str] = {}

    def _key(self, user_id: str) -> str:
        return f"{_PREFIX}{user_id}"

    def _set(self, key: str, value: str) -> None:
        if self._client is not None:
            try:
                self._client.setex(key, _TTL_SECONDS, value)
                return
            except Exception as exc:
                logger.warning("Redis set falhou: %s. Usando memória.", exc)
        self._memory[key] = value

    def _get(self, key: str) -> Optional[str]:
        if self._client is not None:
            try:
                return self._client.get(key)  # type: ignore[return-value]
            except Exception as exc:
                logger.warning("Redis get falhou: %s. Usando memória.", exc)
        return self._memory.get(key)

    def _delete(self, key: str) -> None:
        if self._client is not None:
            try:
                self._client.delete(key)
                return
            except Exception as exc:
                logger.warning("Redis delete falhou: %s. Usando memória.", exc)
        self._memory.pop(key, None)

    async def get_profile(self, user_id: str) -> Optional[GenericUserProfile]:
        raw = self._get(self._key(user_id))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return GenericUserProfile(**data)
        except Exception as exc:
            logger.error("Erro ao deserializar perfil de %s: %s", user_id, exc)
            return None

    async def save_profile(self, profile: GenericUserProfile) -> None:
        profile.updated_at = datetime.utcnow()
        self._set(self._key(profile.user_id), profile.model_dump_json())

    async def update_profile(
        self, user_id: str, updates: Dict[str, Any]
    ) -> Optional[GenericUserProfile]:
        profile = await self.get_profile(user_id)
        if profile is None:
            return None
        data = profile.model_dump()
        data.update(updates)
        data["updated_at"] = datetime.utcnow().isoformat()
        updated = GenericUserProfile(**data)
        await self.save_profile(updated)
        return updated

    async def delete_profile(self, user_id: str) -> bool:
        """LGPD Art. 18 — direito ao esquecimento."""
        key = self._key(user_id)
        raw = self._get(key)
        if raw is None:
            return False
        self._delete(key)
        logger.info("Perfil do usuário %s excluído (LGPD Art. 18).", user_id)
        return True

    async def migrate_profile(self, user_id: str) -> Optional[GenericUserProfile]:
        """Migra perfil para versão mais recente se necessário."""
        from src.profiles.migrations import ProfileMigrator

        profile = await self.get_profile(user_id)
        if profile is None:
            return None
        migrated = ProfileMigrator.migrate(profile)
        if migrated.profile_version != profile.profile_version:
            await self.save_profile(migrated)
        return migrated


__all__ = ["ProfileStore"]
