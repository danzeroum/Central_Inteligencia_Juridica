"""Serviço de alto nível sobre o DataJud + registro de ferramentas MCP.

Combina o :class:`DataJudQueryBuilder` com o :class:`DataJudClient` para expor
operações de valor analítico (jurimetria, monitoramento), que os agentes podem
invocar via ``MCPToolRegistry``. A camada de texto integral (ementa/acórdão) é
intencionalmente separada: a API pública do DataJud entrega apenas metadados de
capa (LGPD), o texto vem de outra fonte (RAG sobre diários/PJe).
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from src.services.datajud_client import DataJudClient
from src.services.datajud_query_builder import DataJudQueryBuilder
from src.services.datajud_schemas import DataJudSearchResult

ClientFactory = Callable[[str], DataJudClient]


class DataJudService:
    """Operações de busca/jurimetria sobre o DataJud."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        client_factory: Optional[ClientFactory] = None,
    ) -> None:
        self._api_key = api_key
        self._client_factory = client_factory or (
            lambda alias: DataJudClient(alias, api_key=api_key)
        )

    def _client(self, alias: str) -> DataJudClient:
        return self._client_factory(alias)

    async def buscar_processo(self, alias: str, numero: str) -> DataJudSearchResult:
        query = DataJudQueryBuilder().with_numero_processo(numero).pagina(1).build()
        return await self._client(alias).search(query)

    async def buscar_por_assunto(
        self,
        alias: str,
        codigos_assunto: List[int],
        *,
        grau: Optional[str] = None,
        size: int = 10,
    ) -> DataJudSearchResult:
        builder = DataJudQueryBuilder().with_assuntos(codigos_assunto).pagina(size)
        if grau:
            builder.with_grau(grau)
        return await self._client(alias).search(builder.build())

    async def buscar_por_tema(
        self,
        alias: str,
        tema: str,
        *,
        grau: Optional[str] = None,
        size: int = 5,
    ) -> DataJudSearchResult:
        builder = (
            DataJudQueryBuilder()
            .with_texto(tema)
            .ordenar_por("_score", "desc")
            .pagina(size)
        )
        if grau:
            builder.with_grau(grau)
        return await self._client(alias).search(builder.build())

    async def monitorar_atualizacoes(
        self, alias: str, *, horas: int = 24, size: int = 20
    ) -> DataJudSearchResult:
        query = (
            DataJudQueryBuilder()
            .atualizado_nas_ultimas_horas(horas)
            .pagina(size)
            .build()
        )
        return await self._client(alias).search(query)


def register_datajud_tools(
    registry: Any, service: Optional[DataJudService] = None
) -> DataJudService:
    """Registra as ferramentas DataJud num ``MCPToolRegistry``.

    Retorna o serviço usado, para que o chamador possa reutilizá-lo. As tools são
    *coroutines* — o chamador deve aguardá-las (``await registry.execute(...)``).
    """

    service = service or DataJudService()

    @registry.register_tool("datajud_buscar_processo")
    async def _buscar_processo(alias: str, numero: str) -> DataJudSearchResult:
        return await service.buscar_processo(alias, numero)

    @registry.register_tool("datajud_buscar_por_assunto")
    async def _buscar_por_assunto(
        alias: str, codigos_assunto: List[int], grau: Optional[str] = None
    ) -> DataJudSearchResult:
        return await service.buscar_por_assunto(alias, codigos_assunto, grau=grau)

    @registry.register_tool("datajud_monitorar_atualizacoes")
    async def _monitorar(alias: str, horas: int = 24) -> DataJudSearchResult:
        return await service.monitorar_atualizacoes(alias, horas=horas)

    return service


__all__ = ["DataJudService", "register_datajud_tools"]
