"""Construtor de queries ElasticSearch para a API Pública do CNJ DataJud.

A API Pública do DataJud (``api-publica.datajud.cnj.jus.br``) expõe um
ElasticSearch com Query DSL completa. Este builder fluente monta o payload
``bool``/``range``/``terms`` de forma legível e testável, sem acoplar a lógica
de query ao cliente HTTP.

Campos relevantes da base (metadados de capa — a API pública mascara nomes das
partes e textos de decisões, conforme LGPD):
``numeroProcesso``, ``classe.codigo``, ``assuntos.codigo``, ``grau``,
``dataAjuizamento``, ``dataHoraUltimaAtualizacao``,
``orgaoJulgador.codigoMunicipioIBGE``, ``movimentos.codigo``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


class DataJudQueryBuilder:
    """Builder fluente para o corpo ``_search`` do DataJud."""

    def __init__(self) -> None:
        self._must: List[Dict[str, Any]] = []
        self._must_not: List[Dict[str, Any]] = []
        self._filter: List[Dict[str, Any]] = []
        # Ordenação determinística é obrigatória para paginação via search_after.
        self._sort: List[Dict[str, Any]] = [{"@timestamp": {"order": "asc"}}]
        self._size: int = 10
        self._search_after: Optional[List[Any]] = None

    def with_numero_processo(self, numero: str) -> "DataJudQueryBuilder":
        self._must.append({"match": {"numeroProcesso": numero}})
        return self

    def with_assuntos(self, codigos: List[int]) -> "DataJudQueryBuilder":
        self._filter.append({"terms": {"assuntos.codigo": codigos}})
        return self

    def with_classe(self, codigo: int) -> "DataJudQueryBuilder":
        self._filter.append({"match": {"classe.codigo": codigo}})
        return self

    def with_municipio(self, codigo_ibge: int) -> "DataJudQueryBuilder":
        self._filter.append(
            {"match": {"orgaoJulgador.codigoMunicipioIBGE": codigo_ibge}}
        )
        return self

    def with_grau(self, grau: str) -> "DataJudQueryBuilder":
        # Graus do TPU: "G1", "G2", "JE", "TR", "ST", etc.
        self._filter.append({"match": {"grau": grau}})
        return self

    def ajuizado_entre(self, inicio: str, fim: str) -> "DataJudQueryBuilder":
        """Filtra por data de ajuizamento (datas no formato ``YYYY-MM-DD``)."""

        self._filter.append(
            {
                "range": {
                    "dataAjuizamento": {
                        "gte": f"{inicio}T00:00:00.000Z",
                        "lte": f"{fim}T23:59:59.999Z",
                    }
                }
            }
        )
        return self

    def atualizado_nas_ultimas_horas(self, horas: int) -> "DataJudQueryBuilder":
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=horas)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        self._filter.append({"range": {"dataHoraUltimaAtualizacao": {"gte": cutoff}}})
        return self

    def excluir_movimentos(self, codigos: List[int]) -> "DataJudQueryBuilder":
        """Exclui processos com determinados códigos de movimento (TPU)."""

        self._must_not.append({"terms": {"movimentos.codigo": codigos}})
        return self

    def pagina(
        self, size: int, after: Optional[List[Any]] = None
    ) -> "DataJudQueryBuilder":
        self._size = size
        self._search_after = after
        return self

    def ordenar_por(self, campo: str, ordem: str = "asc") -> "DataJudQueryBuilder":
        self._sort = [{campo: {"order": ordem}}]
        return self

    def build(self) -> Dict[str, Any]:
        query: Dict[str, Any] = {
            "size": self._size,
            "query": {
                "bool": {
                    "must": self._must,
                    "must_not": self._must_not,
                    "filter": self._filter,
                }
            },
            "sort": self._sort,
        }
        if self._search_after is not None:
            query["search_after"] = self._search_after
        return query


__all__ = ["DataJudQueryBuilder"]
