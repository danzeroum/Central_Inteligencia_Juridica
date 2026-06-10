"""Adaptador DJEN / Comunica PJe — publicações do Diário da Justiça Eletrônico.

Endpoint: GET comunicaapi.pje.jus.br/api/v1/comunicacao
Suporta: NUMERO_PROCESSO, NOME, OAB
"""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar, Dict, List, Optional, Set

import httpx
from pydantic import BaseModel

from src.integrations.base import LegalDataAdapter
from src.integrations.models import (
    IdentifierQuery,
    IdentifierType,
    Publicacao,
    SourceZone,
)
from src.integrations.settings import SourceSettings

logger = logging.getLogger(__name__)

DJEN_BASE_URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"

# Padrão simples para remoção de CPF/CNPJ em texto (redact_pii)
_PII_PATTERN = re.compile(
    r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"
)


def _redact_pii(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    return _PII_PATTERN.sub("[REDACTED]", text)


class DjenAdapter(LegalDataAdapter):
    """Adaptador para o Comunicações PJe (DJEN nacional)."""

    service_name: ClassVar[str] = "djen"
    zone: ClassVar[SourceZone] = SourceZone.PUBLICA
    data_type: ClassVar[str] = "publicacao_dje"
    supported_identifiers: ClassVar[Set[IdentifierType]] = {
        IdentifierType.NUMERO_PROCESSO,
        IdentifierType.NOME,
        IdentifierType.OAB,
    }
    item_model: ClassVar = Publicacao

    async def fetch_real(self, q: IdentifierQuery) -> List[BaseModel]:
        params: Dict[str, Any] = {
            "pagina": (q.offset // q.limit) + 1 if q.limit > 0 else 1,
            "itensPorPagina": min(q.limit, 50),
        }

        if q.identifier_type == IdentifierType.NUMERO_PROCESSO:
            params["numeroProcesso"] = q.identifier
        elif q.identifier_type == IdentifierType.OAB:
            params["numeroOab"] = q.identifier
        else:
            params["nomeDestinatario"] = q.identifier

        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            resp = await client.get(DJEN_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items = []
        for entry in data.get("items") or data.get("content") or []:
            items.append(
                Publicacao(
                    numero_processo=entry.get("numeroProcesso"),
                    data_disponibilizacao=entry.get("dataDisponibilizacao")
                    or entry.get("data"),
                    texto=_redact_pii(entry.get("texto") or entry.get("conteudo")),
                    tribunal=entry.get("siglaOrgao") or entry.get("tribunal"),
                    tipo=entry.get("tipoDocumento") or entry.get("tipo"),
                    destinatario=entry.get("nomeDestinatario"),
                )
            )
        return items
