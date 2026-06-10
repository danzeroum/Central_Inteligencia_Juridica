"""Adaptador DataJud — delega ao DataJudClient existente.

Suporta apenas NUMERO_PROCESSO (API CNJ não permite busca por CPF/CNPJ diretamente
no Elasticsearch público sem credencial especial).
"""

from __future__ import annotations

import logging
import os
from typing import Any, ClassVar, List, Optional, Set

from pydantic import BaseModel

from src.integrations.base import LegalDataAdapter
from src.integrations.models import (
    AdapterStatus,
    DataMode,
    IdentifierQuery,
    IdentifierType,
    ProcessoNormalizado,
    SourceZone,
)
from src.integrations.settings import SourceSettings
from src.services.datajud_query_builder import DataJudQueryBuilder

logger = logging.getLogger(__name__)

# Alias padrão quando não informado no contexto da query
_DEFAULT_ALIAS = os.getenv("DATAJUD_DEFAULT_ALIAS", "tjsp")


class DataJudAdapter(LegalDataAdapter):
    """Adaptador para a API pública do CNJ DataJud."""

    service_name: ClassVar[str] = "datajud"
    zone: ClassVar[SourceZone] = SourceZone.PUBLICA
    data_type: ClassVar[str] = "processo_por_numero"
    supported_identifiers: ClassVar[Set[IdentifierType]] = {
        IdentifierType.NUMERO_PROCESSO
    }
    item_model: ClassVar = ProcessoNormalizado

    async def fetch_real(self, q: IdentifierQuery) -> List[BaseModel]:
        from src.services.datajud_client import DataJudClient

        alias = q.extra.get("tribunal_alias", _DEFAULT_ALIAS)
        client = DataJudClient(alias=alias, timeout=self.settings.timeout_seconds)

        query_builder = DataJudQueryBuilder()
        query = query_builder.with_numero_processo(q.identifier).build()

        result = await client.search(query)

        if result.source == "simulated" or result.fallback:
            # DataJudClient em modo mock → marca data_mode adequadamente
            logger.info(
                "DataJud retornou mock (alias=%s, motivo=%s)", alias, result.reason
            )
            # Propaga fallback via metadata
            self._last_fallback = True
            self._last_fallback_reason = getattr(result, "reason", "unknown")
        else:
            self._last_fallback = False
            self._last_fallback_reason = None

        return [
            ProcessoNormalizado(
                numero_processo=p.numeroProcesso or "",
                tribunal=p.tribunal or alias.upper(),
                grau=p.grau,
                data_ajuizamento=p.dataAjuizamento,
                assuntos=p.assuntos or [],
                movimentos=p.movimentos or [],
            )
            for p in result.processos
        ]

    async def query(self, q: IdentifierQuery):
        """Sobrescreve para mapear fallback do DataJudClient → data_mode=mock."""
        import time

        start = time.monotonic()
        try:
            items = await self.fetch_real(q)
            latency = (time.monotonic() - start) * 1000
            is_mock = getattr(self, "_last_fallback", False)
            return __import__(
                "src.integrations.models", fromlist=["AdapterResult"]
            ).AdapterResult(
                source=self.service_name,
                status=AdapterStatus.SUCCESS,
                data_mode=DataMode.MOCK if is_mock else DataMode.REAL,
                items=items,
                total_available=len(items),
                latency_ms=latency,
                metadata={
                    "fallback": is_mock,
                    "fallback_reason": getattr(self, "_last_fallback_reason", None),
                },
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            logger.exception("DataJudAdapter falhou: %s", exc)
            from src.integrations.models import AdapterResult

            return AdapterResult(
                source=self.service_name,
                status=AdapterStatus.FAILED,
                data_mode=DataMode.REAL,
                error=str(exc),
                latency_ms=latency,
            )
