"""ProfileRepository — fachada combinando ProfileStore + ProfileMigrator."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from src.profiles.migrations import ProfileMigrator
from src.profiles.profile_store import ProfileStore
from src.profiles.schemas import ClienteProfile, GenericUserProfile

logger = logging.getLogger(__name__)

_CLIENTE_PREFIX = "cij:cliente:"


class ProfileRepository:
    """Fachada para operações de perfil de usuário e clientes."""

    def __init__(self) -> None:
        self._store = ProfileStore()

    async def get(self, user_id: str) -> Optional[GenericUserProfile]:
        profile = await self._store.get_profile(user_id)
        if profile is not None:
            profile = ProfileMigrator.migrate(profile)
        return profile

    async def save(self, profile: GenericUserProfile) -> None:
        await self._store.save_profile(profile)

    async def update(self, user_id: str, updates: Dict) -> Optional[GenericUserProfile]:
        return await self._store.update_profile(user_id, updates)

    async def delete(self, user_id: str) -> bool:
        """LGPD Art. 18."""
        return await self._store.delete_profile(user_id)

    # --- Cliente sub-resource ---

    async def get_client(
        self, advogado_id: str, cliente_id: str
    ) -> Optional[ClienteProfile]:
        key = f"{_CLIENTE_PREFIX}{advogado_id}:{cliente_id}"
        raw = self._store._get(key)
        if raw is None:
            return None
        try:
            import json

            return ClienteProfile(**json.loads(raw))
        except Exception as exc:
            logger.error("Erro ao deserializar cliente %s: %s", cliente_id, exc)
            return None

    async def save_client(self, cliente: ClienteProfile) -> None:
        key = f"{_CLIENTE_PREFIX}{cliente.advogado_id}:{cliente.cliente_id}"
        self._store._set(key, cliente.model_dump_json())

    async def list_clients(self, advogado_id: str) -> List[ClienteProfile]:
        prefix = f"{_CLIENTE_PREFIX}{advogado_id}:"
        results: List[ClienteProfile] = []
        if self._store._client is not None:
            try:
                import json

                keys = self._store._client.keys(f"{prefix}*")
                for key in keys:
                    raw = self._store._client.get(key)
                    if raw:
                        try:
                            results.append(ClienteProfile(**json.loads(raw)))
                        except Exception:
                            pass
                return results
            except Exception as exc:
                logger.warning("Redis keys falhou: %s", exc)
        # fallback: in-memory
        import json

        for key, raw in self._store._memory.items():
            if key.startswith(prefix):
                try:
                    results.append(ClienteProfile(**json.loads(raw)))
                except Exception:
                    pass
        return results


__all__ = ["ProfileRepository"]
