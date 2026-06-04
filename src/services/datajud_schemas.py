"""Schemas Pydantic para as respostas da API Pública do DataJud (CNJ).

A validação é deliberadamente tolerante (``extra="allow"``): a base do DataJud
evolui e cada tribunal pode trazer campos adicionais. Validamos os campos de capa
mais úteis sem rejeitar payloads que tragam atributos extras.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DataJudProcesso(BaseModel):
    """Metadados de capa de um processo (um ``_source`` do ElasticSearch)."""

    model_config = ConfigDict(extra="allow")

    numeroProcesso: Optional[str] = None
    tribunal: Optional[str] = None
    grau: Optional[str] = None
    dataAjuizamento: Optional[str] = None
    dataHoraUltimaAtualizacao: Optional[str] = None
    classe: Optional[Dict[str, Any]] = None
    orgaoJulgador: Optional[Dict[str, Any]] = None
    assuntos: List[Dict[str, Any]] = Field(default_factory=list)
    movimentos: List[Dict[str, Any]] = Field(default_factory=list)


class DataJudSearchResult(BaseModel):
    """Resultado normalizado de uma busca ``_search`` no DataJud.

    ``source`` segue o padrão do ADR-008: ``real_api`` quando os dados vêm da API
    oficial, ``simulated`` quando houve fallback gracioso (sem chave, erro de rede
    ou circuit breaker aberto).
    """

    total: int = 0
    processos: List[DataJudProcesso] = Field(default_factory=list)
    source: str = "real_api"
    fallback: bool = False
    alias: Optional[str] = None
    reason: Optional[str] = None
    circuit_breaker: Optional[Dict[str, Any]] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "total": 1,
                "processos": [
                    {
                        "numeroProcesso": "00008323520184013202",
                        "tribunal": "TRF1",
                        "grau": "G1",
                        "dataAjuizamento": "2018-05-14T00:00:00.000Z",
                        "assuntos": [{"codigo": 2086, "nome": "Rescisão do Contrato"}],
                    }
                ],
                "source": "real_api",
                "fallback": False,
                "alias": "trf1",
            }
        }
    }


__all__ = ["DataJudProcesso", "DataJudSearchResult"]
