"""Adaptador CRC / CENPROT — protestos cartoriais.

Onda 1: operação em modo mock (captcha bloqueia acesso programático).
fetch_real levanta NotImplementedError → base.py intercepta e retorna FAILED
com error="real_mode_unavailable" quando forçado a real.
Troca mock→real = só configuração INTEGRATIONS_CRC_PROTESTOS_MODE=real.
"""

from __future__ import annotations

from typing import ClassVar, List, Set

from pydantic import BaseModel

from src.integrations.base import LegalDataAdapter
from src.integrations.models import (
    IdentifierQuery,
    IdentifierType,
    Protesto,
    SourceZone,
)

_MOCK_PROTESTOS = [
    Protesto(
        cartorio="1º Tabelionato de Protestos de São Paulo",
        data_protesto="2023-03-15",
        valor=15000.00,
        credor="Banco Teste S.A.",
        tipo="Duplicata",
        situacao="PROTESTADO",
    )
]


class CrcProtestosAdapter(LegalDataAdapter):
    """Adaptador CRC/CENPROT (protestos) — mock por feature flag na Onda 1."""

    service_name: ClassVar[str] = "crc_protestos"
    zone: ClassVar[SourceZone] = SourceZone.RESTRITA
    data_type: ClassVar[str] = "protesto"
    supported_identifiers: ClassVar[Set[IdentifierType]] = {
        IdentifierType.CPF,
        IdentifierType.CNPJ,
    }
    item_model: ClassVar = Protesto

    async def fetch_real(self, q: IdentifierQuery) -> List[BaseModel]:
        raise NotImplementedError(
            "CRC/CENPROT exige captcha — disponível como worker separado na Onda 2."
        )

    def fetch_mock(self, q: IdentifierQuery) -> List[BaseModel]:
        return list(_MOCK_PROTESTOS)
