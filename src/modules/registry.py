"""ModuleRegistry — discovery, registro e sincronização de módulos com o banco."""

from __future__ import annotations

import asyncio
import copy
import logging
import os
from typing import Dict, List, Optional

from src.modules.manifest import ModuleManifest

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Registro central de módulos ativos na plataforma."""

    def __init__(self) -> None:
        self._modules: Dict[str, ModuleManifest] = {}
        self._subscribers: List[asyncio.Queue] = []

    def register(self, manifest: ModuleManifest) -> None:
        """Registra ou sobrescreve um módulo no registry (cópia do manifesto)."""
        self._modules[manifest.module_id] = copy.copy(manifest)
        logger.debug("Módulo registrado: %s v%s", manifest.module_id, manifest.version)

    def get(self, module_id: str) -> Optional[ModuleManifest]:
        """Retorna o manifesto de um módulo ou ``None`` se não encontrado."""
        return self._modules.get(module_id)

    def list_all(self) -> List[ModuleManifest]:
        """Retorna todos os módulos registrados (ativos e inativos)."""
        return list(self._modules.values())

    def list_active(self) -> List[ModuleManifest]:
        """Retorna apenas os módulos com ``is_active=True``."""
        return [m for m in self._modules.values() if m.is_active]

    def deactivate(self, module_id: str) -> bool:
        """Desativa um módulo sem removê-lo do registry. Retorna ``False`` se não existe."""
        manifest = self._modules.get(module_id)
        if manifest is None:
            return False
        manifest.is_active = False
        return True

    def toggle(self, module_id: str) -> Optional[ModuleManifest]:
        """Alterna o estado is_active de um módulo. Retorna o manifesto ou ``None``."""
        manifest = self._modules.get(module_id)
        if manifest is None:
            return None
        manifest.is_active = not manifest.is_active
        logger.info(
            "Módulo '%s' %s.",
            module_id,
            "ativado" if manifest.is_active else "desativado",
        )
        return manifest

    def subscribe(self) -> asyncio.Queue:
        """Registra um subscriber SSE e retorna sua fila de eventos."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove um subscriber SSE."""
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    async def broadcast(self, event: dict) -> None:
        """Notifica todos os subscribers SSE com o evento fornecido."""
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def sync_to_db(self) -> None:
        """Faz upsert dos módulos ativos na tabela ``Module`` do banco.

        No-op quando ``DATABASE_URL`` não está configurado (compatibilidade Onda 1).
        """
        if not os.getenv("DATABASE_URL"):
            return

        try:
            from datetime import datetime, timezone

            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy.orm import Session

            from src.db.engine import get_sync_engine
            from src.db.models import Module as ModuleRow

            engine = get_sync_engine()
            if engine is None:
                return

            with Session(engine) as session:
                for manifest in self.list_active():
                    stmt = pg_insert(ModuleRow).values(
                        id=manifest.module_id,
                        name=manifest.name,
                        version=manifest.version,
                        is_active=manifest.is_active,
                        created_at=datetime.now(timezone.utc),
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "name": stmt.excluded.name,
                            "version": stmt.excluded.version,
                        },
                    )
                    session.execute(stmt)
                session.commit()
        except Exception as exc:
            logger.warning("sync_to_db falhou (não-crítico): %s", exc)


_registry: Optional[ModuleRegistry] = None


def get_module_registry() -> ModuleRegistry:
    """Singleton — cria e popula o registry na primeira chamada."""
    global _registry
    if _registry is None:
        from src.modules.core import BUILTIN_MODULES

        _registry = ModuleRegistry()
        for manifest in BUILTIN_MODULES:
            _registry.register(manifest)
        logger.info(
            "ModuleRegistry inicializado com %d módulos built-in.", len(BUILTIN_MODULES)
        )
    return _registry
