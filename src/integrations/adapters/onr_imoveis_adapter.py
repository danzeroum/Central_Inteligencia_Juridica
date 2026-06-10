"""Adaptador ONR / SREI — imóveis.

Onda 1: mock (exige cadastro no ONR).
"""

from __future__ import annotations

from typing import ClassVar, List, Set

from pydantic import BaseModel

from src.integrations.base import LegalDataAdapter
from src.integrations.models import (
    IdentifierQuery,
    IdentifierType,
    Imovel,
    SourceZone,
)

_MOCK_IMOVEIS = [
    Imovel(
        matricula="123456",
        cartorio="1º Registro de Imóveis de São Paulo",
        tipo_imovel="Apartamento",
        municipio="São Paulo",
        area=85.5,
        data_registro="2018-04-10",
        proprietario="[REDACTED]",
        uf="SP",
    )
]


class OnrImoveisAdapter(LegalDataAdapter):
    """Adaptador ONR/SREI (imóveis) — mock por feature flag na Onda 1."""

    service_name: ClassVar[str] = "onr_imoveis"
    zone: ClassVar[SourceZone] = SourceZone.RESTRITA
    data_type: ClassVar[str] = "imovel"
    supported_identifiers: ClassVar[Set[IdentifierType]] = {
        IdentifierType.CPF,
        IdentifierType.CNPJ,
    }
    item_model: ClassVar = Imovel

    async def fetch_real(self, q: IdentifierQuery) -> List[BaseModel]:
        raise NotImplementedError(
            "ONR/SREI exige cadastro — disponível como worker separado na Onda 2."
        )

    def fetch_mock(self, q: IdentifierQuery) -> List[BaseModel]:
        return list(_MOCK_IMOVEIS)
