"""Endpoint HTTP de jurisprudência/processos via CNJ DataJud (Frente F.1).

Fecha o loop da Frente F.1 (dívida do ADR-013): expõe a camada DataJud à SPA.
Sem ``DATAJUD_API_KEY``, o serviço degrada para mock (``source='simulated'``),
então o endpoint nunca quebra — dev/CI não dependem de rede externa.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.rate_limit import enforce_rate_limit
from src.api.rbac import Principal, current_principal
from src.services.datajud_schemas import DataJudSearchResult
from src.services.datajud_service import DataJudService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/jurisprudencia", tags=["Jurisprudência"])

# Aliases do DataJud são ``api_publica_<alias>`` (ex.: tjsp, trf1, stj, tst).
# Validar evita injeção de path na URL do ElasticSearch.
_ALIAS_RE = re.compile(r"^[a-z0-9]{2,20}$")

# Instância de módulo (patchável em testes). Lê DATAJUD_API_KEY por chamada.
datajud_service = DataJudService()


@router.get(
    "",
    response_model=DataJudSearchResult,
    summary="Busca processos/jurisprudência no CNJ DataJud",
    description=(
        "Consulta o CNJ DataJud por número de processo (``q``) ou por código(s) "
        "de assunto TPU (``assunto``). Requer ``tribunal`` (alias do DataJud). "
        "Sem chave configurada, retorna dados simulados (``source='simulated'``)."
    ),
)
async def buscar_jurisprudencia(
    tribunal: str = Query(
        ..., description="Alias do tribunal no DataJud (ex.: tjsp, trf1, stj)"
    ),
    q: Optional[str] = Query(None, description="Número do processo a consultar"),
    tema: Optional[str] = Query(
        None, max_length=200, description="Tema ou palavras-chave (busca por texto)"
    ),
    assunto: Optional[List[int]] = Query(
        None, description="Código(s) de assunto TPU (repetível)"
    ),
    grau: Optional[str] = Query(None, description="Grau (G1, G2, JE, TR, ST)"),
    size: int = Query(10, ge=1, le=50, description="Máximo de resultados"),
    _principal: Principal = Depends(current_principal),
    _rl: None = Depends(enforce_rate_limit),
) -> DataJudSearchResult:
    """Roteia a consulta para a camada DataJud (processo, tema ou assunto TPU)."""

    alias = (tribunal or "").strip().lower()
    if not _ALIAS_RE.match(alias):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tribunal inválido: use o alias do DataJud (ex.: tjsp, trf1, stj)",
        )

    if q and q.strip():
        return await datajud_service.buscar_processo(alias, q.strip())
    if tema and tema.strip():
        return await datajud_service.buscar_por_tema(
            alias, tema.strip(), grau=grau, size=size
        )
    if assunto:
        return await datajud_service.buscar_por_assunto(
            alias, assunto, grau=grau, size=size
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Informe 'q' (processo), 'tema' (palavras-chave) ou 'assunto' (código TPU).",
    )


__all__ = ["router", "datajud_service"]
