"""Registro de adaptadores de integração.

Centraliza instâncias de adaptadores com lookup por nome e capability.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

import httpx

from src.integrations.base import LegalDataAdapter
from src.integrations.models import IdentifierType
from src.integrations.settings import SourceSettings, get_source_settings

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registro central de adaptadores de integração."""

    def __init__(self) -> None:
        self._adapters: Dict[str, LegalDataAdapter] = {}

    def register(
        self,
        adapter_cls: Type[LegalDataAdapter],
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        credentials: Optional[object] = None,
        settings_override: Optional[SourceSettings] = None,
    ) -> LegalDataAdapter:
        """Registra um adaptador, carregando settings do YAML/env."""
        name = adapter_cls.service_name
        if not name:
            raise ValueError(f"Adapter {adapter_cls} sem service_name")

        settings = settings_override or get_source_settings(name)
        if settings is None:
            logger.warning(
                "Nenhuma configuração para '%s'; usando defaults.", name
            )
            settings = SourceSettings(name=name)

        instance = adapter_cls(settings, http_client=http_client, credentials=credentials)
        self._adapters[name] = instance
        logger.debug("Adapter '%s' registrado (mode=%s)", name, settings.mode)
        return instance

    def get(self, name: str) -> Optional[LegalDataAdapter]:
        return self._adapters.get(name)

    def all_enabled(self) -> List[LegalDataAdapter]:
        return [a for a in self._adapters.values() if a.enabled]

    def for_identifier(self, identifier_type: IdentifierType) -> List[LegalDataAdapter]:
        """Retorna todos os adaptadores habilitados que suportam o tipo."""
        return [
            a
            for a in self.all_enabled()
            if a.supports(identifier_type)
        ]

    def names(self) -> List[str]:
        return list(self._adapters.keys())

    def health(self) -> Dict[str, object]:
        return {name: a.settings.mode for name, a in self._adapters.items()}


# Instância global
_registry: Optional[AdapterRegistry] = None


def get_registry() -> AdapterRegistry:
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
    return _registry


__all__ = ["AdapterRegistry", "get_registry"]
