"""Adaptador Cadin — pendências cadastrais.

Onda 1: mock (exige login gov.br).
"""

from __future__ import annotations

from typing import ClassVar, List, Set

from pydantic import BaseModel

from src.integrations.base import LegalDataAdapter
from src.integrations.models import (
    IdentifierQuery,
    IdentifierType,
    PendenciaCadin,
    SourceZone,
)

_MOCK_CADIN = [
    PendenciaCadin(
        orgao="Secretaria da Fazenda",
        tipo_pendencia="Débito Fiscal",
        valor=5000.00,
        data_inscricao="2022-06-01",
        situacao="ATIVO",
    )
]


class CadinAdapter(LegalDataAdapter):
    """Adaptador Cadin — mock por feature flag na Onda 1."""

    service_name: ClassVar[str] = "cadin"
    zone: ClassVar[SourceZone] = SourceZone.RESTRITA
    data_type: ClassVar[str] = "cadin"
    supported_identifiers: ClassVar[Set[IdentifierType]] = {
        IdentifierType.CPF,
        IdentifierType.CNPJ,
    }
    item_model: ClassVar = PendenciaCadin

    async def fetch_real(self, q: IdentifierQuery) -> List[BaseModel]:
        raise NotImplementedError(
            "Cadin exige login gov.br — disponível como worker separado na Onda 2."
        )

    def fetch_mock(self, q: IdentifierQuery) -> List[BaseModel]:
        return list(_MOCK_CADIN)
