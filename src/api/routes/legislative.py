"""Rotas de consulta de proposições legislativas e análises de IA."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from src.agents.agente_legislativo import analisar_cenario_legislativo
from src.api.rate_limit import enforce_rate_limit
from src.api.rbac import Principal, current_principal
from src.services.camara_client import buscar_projetos_de_lei

router = APIRouter()


async def _consultar_projetos(
    termo_busca: str, pagina: int = 1, itens: int = 15
) -> Dict[str, Any]:
    """Lógica compartilhada de consulta de proposições (legado + canônico)."""

    termo_busca = termo_busca.strip()
    if not termo_busca:
        raise HTTPException(status_code=400, detail="Parametro 'q' e obrigatorio.")

    resultado = buscar_projetos_de_lei(termo_busca, pagina=pagina, itens=itens)
    if "error" in resultado:
        raise HTTPException(status_code=502, detail=resultado["error"])
    return resultado


async def _analisar_legislacao(tema: str) -> Dict[str, Any]:
    """Lógica compartilhada de análise legislativa (legado + canônico)."""

    tema_legislativo = tema.strip()
    if not tema_legislativo:
        raise HTTPException(status_code=400, detail="Parametro 'tema' e obrigatorio.")

    resultado_analise = analisar_cenario_legislativo(tema_legislativo)
    return {"tema_analisado": tema_legislativo, "analise_ia": resultado_analise}


@router.get("/consultar-projetos-lei/", tags=["Consultas"], deprecated=True)
async def consultar_projetos_endpoint(
    q: str = Query(..., description="Termo de busca para proposições legislativas"),
    _principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
):
    """(Deprecated) Use ``GET /api/v1/proposicoes-legislativas``."""

    return await _consultar_projetos(q)


@router.get(
    "/api/v1/proposicoes-legislativas",
    tags=["Consultas"],
    summary="Pesquisa proposições legislativas",
)
async def pesquisar_proposicoes(
    q: str = Query(
        ...,
        min_length=2,
        max_length=200,
        description="Termo de busca para proposições legislativas",
    ),
    pagina: int = Query(1, ge=1, description="Número da página (começa em 1)"),
    itens: int = Query(15, ge=1, le=100, description="Itens por página (máx. 100)"),
    _principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Consulta proposições legislativas na API da Câmara dos Deputados."""

    return await _consultar_projetos(q, pagina=pagina, itens=itens)


@router.post("/analise-legislativa/", tags=["Análises de IA"], deprecated=True)
async def analisar_legislacao_endpoint(
    tema: str = Body(
        ..., embed=True, description="Tema legislativo para análise de IA"
    ),
    _principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
):
    """(Deprecated) Use ``POST /api/v1/analises-legislativas``."""

    return await _analisar_legislacao(tema)


@router.post(
    "/api/v1/analises-legislativas",
    tags=["Análises de IA"],
    status_code=status.HTTP_201_CREATED,
    summary="Cria análise de IA sobre tema legislativo",
)
async def criar_analise_legislativa(
    tema: str = Body(
        ...,
        embed=True,
        min_length=3,
        max_length=500,
        description="Tema legislativo para análise de IA",
    ),
    _principal: Principal = Depends(current_principal),
    _: None = Depends(enforce_rate_limit),
) -> Dict[str, Any]:
    """Cria uma análise de IA sobre um tema legislativo."""

    return await _analisar_legislacao(tema)
