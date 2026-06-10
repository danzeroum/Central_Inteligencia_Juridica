"""Base abstrata para todos os adaptadores de integração jurídica.

Padrão template method: `query()` nunca levanta exceção — captura tudo e
retorna `AdapterResult(status=failed)`. Subclasses implementam `fetch_real()`.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Type

import httpx
from pydantic import BaseModel

from src.integrations.models import (
    AdapterResult,
    AdapterStatus,
    DataMode,
    IdentifierQuery,
    IdentifierType,
    SourceZone,
)
from src.integrations.settings import SourceSettings

logger = logging.getLogger(__name__)

MOCK_DATA_DIR = Path(__file__).resolve().parent / "mock_data"


class LegalDataAdapter(ABC):
    """Template base para adaptadores de dados jurídicos."""

    service_name: ClassVar[str] = ""
    zone: ClassVar[SourceZone] = SourceZone.PUBLICA
    data_type: ClassVar[str] = ""
    supported_identifiers: ClassVar[Set[IdentifierType]] = set()
    item_model: ClassVar[Optional[Type[BaseModel]]] = None

    def __init__(
        self,
        settings: SourceSettings,
        http_client: Optional[httpx.AsyncClient] = None,
        credentials: Optional[Any] = None,
    ) -> None:
        self.settings = settings
        self._http_client = http_client
        self._credentials = credentials

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    def supports(self, identifier_type: IdentifierType) -> bool:
        return identifier_type in self.supported_identifiers

    async def query(self, q: IdentifierQuery) -> AdapterResult:
        """Executa a consulta capturando toda exceção (nunca propaga)."""
        start = time.monotonic()
        try:
            if self.settings.is_mock():
                items = self.fetch_mock(q)
                latency = (time.monotonic() - start) * 1000
                return AdapterResult(
                    source=self.service_name,
                    status=AdapterStatus.SUCCESS,
                    data_mode=DataMode.MOCK,
                    items=items,
                    total_available=len(items),
                    latency_ms=latency,
                    metadata={"data_mode": "mock"},
                )
            items = await self.fetch_real(q)
            latency = (time.monotonic() - start) * 1000
            return AdapterResult(
                source=self.service_name,
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.REAL,
                items=items,
                total_available=len(items),
                latency_ms=latency,
            )
        except NotImplementedError:
            latency = (time.monotonic() - start) * 1000
            logger.warning(
                "Adapter %s: fetch_real não implementado (modo real forçado); retornando mock.",
                self.service_name,
            )
            items = self.fetch_mock(q)
            return AdapterResult(
                source=self.service_name,
                status=AdapterStatus.FAILED,
                data_mode=DataMode.MOCK,
                items=items,
                total_available=len(items),
                error="real_mode_unavailable",
                latency_ms=latency,
                metadata={"data_mode": "mock", "fallback": True},
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            logger.exception(
                "Adapter %s falhou para %s: %s", self.service_name, q.identifier, exc
            )
            return AdapterResult(
                source=self.service_name,
                status=AdapterStatus.FAILED,
                data_mode=DataMode.MOCK if self.settings.is_mock() else DataMode.REAL,
                error=str(exc),
                latency_ms=latency,
            )

    @abstractmethod
    async def fetch_real(self, q: IdentifierQuery) -> List[BaseModel]:
        """Implementação real da consulta. Pode levantar exceções."""
        ...

    def fetch_mock(self, q: IdentifierQuery) -> List[BaseModel]:
        """Retorna dados mock do arquivo JSON correspondente."""
        mock_file = MOCK_DATA_DIR / f"{self.service_name}.json"
        if not mock_file.exists():
            logger.warning("Mock data não encontrado: %s", mock_file)
            return []
        try:
            raw = json.loads(mock_file.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else raw.get("items", [])
            if self.item_model:
                return [self.item_model.model_validate(item) for item in items]
            return items
        except Exception as exc:
            logger.warning("Erro ao carregar mock de %s: %s", self.service_name, exc)
            return []

    async def health(self) -> Dict[str, Any]:
        return {
            "source": self.service_name,
            "enabled": self.enabled,
            "mode": self.settings.mode,
            "zone": self.zone.value,
            "data_type": self.data_type,
        }


__all__ = ["LegalDataAdapter", "MOCK_DATA_DIR"]
