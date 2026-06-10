"""Adaptador TSE — dados eleitorais (CKAN dados abertos).

coverage: basic — retorna candidaturas/filiações por CPF ou nome.
Endpoint: dadosabertos.tse.jus.br (CKAN API)
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict, List, Optional, Set

import httpx
from pydantic import BaseModel

from src.integrations.base import LegalDataAdapter
from src.integrations.models import (
    CandidaturaTSE,
    IdentifierQuery,
    IdentifierType,
    SourceZone,
)
from src.integrations.settings import SourceSettings

logger = logging.getLogger(__name__)

TSE_CKAN_BASE = "https://dadosabertos.tse.jus.br/api/3/action/datastore_search"
# Resource ID das candidaturas (TSE dados abertos — pode variar por eleição)
_CANDIDATURAS_RESOURCE = "a0e50aff-1e27-4218-a823-ed3c4b3e0c1a"


class TseAdapter(LegalDataAdapter):
    """Adaptador TSE Dados Abertos (candidaturas/filiações) — cobertura básica."""

    service_name: ClassVar[str] = "tse"
    zone: ClassVar[SourceZone] = SourceZone.PUBLICA
    data_type: ClassVar[str] = "eleitoral"
    supported_identifiers: ClassVar[Set[IdentifierType]] = {
        IdentifierType.CPF,
        IdentifierType.NOME,
    }
    item_model: ClassVar = CandidaturaTSE

    async def fetch_real(self, q: IdentifierQuery) -> List[BaseModel]:
        filters: Dict[str, Any] = {}
        if q.identifier_type == IdentifierType.CPF:
            import re
            cpf = re.sub(r"\D", "", q.identifier)
            filters["NR_CPF_CANDIDATO"] = cpf
        else:
            filters["NM_CANDIDATO"] = q.identifier.upper()

        params: Dict[str, Any] = {
            "resource_id": _CANDIDATURAS_RESOURCE,
            "limit": min(q.limit, 50),
            "offset": q.offset,
            "filters": str(filters).replace("'", '"'),
        }

        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            resp = await client.get(TSE_CKAN_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()

        items = []
        for rec in (data.get("result") or {}).get("records") or []:
            cpf_raw = rec.get("NR_CPF_CANDIDATO") or rec.get("cpf")
            # Mascara CPF antes de retornar
            if cpf_raw:
                import re
                d = re.sub(r"\D", "", str(cpf_raw))
                if len(d) == 11:
                    cpf_raw = f"***.***.{d[6:9]}-{d[9:11]}"
            items.append(
                CandidaturaTSE(
                    nome=rec.get("NM_CANDIDATO") or rec.get("nome"),
                    cpf=cpf_raw,
                    partido=rec.get("SG_PARTIDO") or rec.get("partido"),
                    cargo=rec.get("DS_CARGO") or rec.get("cargo"),
                    ano_eleicao=_safe_int(rec.get("ANO_ELEICAO") or rec.get("ano")),
                    uf=rec.get("SG_UF") or rec.get("uf"),
                    municipio=rec.get("NM_MUNICIPIO") or rec.get("municipio"),
                    situacao=rec.get("DS_SITUACAO_CANDIDATURA") or rec.get("situacao"),
                )
            )
        return items


def _safe_int(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None
