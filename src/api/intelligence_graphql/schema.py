"""Schema GraphQL de inteligência jurídica (Strawberry).

Montado em /api/v1/intelligence/graphql.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

import strawberry
from strawberry.extensions import QueryDepthLimiter
from strawberry.fastapi import GraphQLRouter

from src.api.intelligence_graphql.context import IntelligenceContext, get_context
from src.api.intelligence_graphql.types import (
    AdapterResultType,
    ConsolidatedReportType,
    RelatedPartyType,
    RiskDimensionType,
    RiskFactorType,
    SourceHealthType,
)
from src.api.rbac import Principal
from src.integrations.models import ConsolidatedReport

logger = logging.getLogger(__name__)

_ENV_PROD = os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod")


def _report_to_gql(report: ConsolidatedReport) -> ConsolidatedReportType:
    results_list = [
        AdapterResultType(
            source=name,
            status=data.get("status", "skipped"),
            data_mode=data.get("data_mode", "mock"),
            from_cache=data.get("from_cache", False),
            latency_ms=data.get("latency_ms", 0.0),
            total_available=data.get("total_available", 0),
            error=data.get("error"),
            items=data.get("items", []),
        )
        for name, data in (report.results or {}).items()
    ]
    return ConsolidatedReportType(
        query_id=report.query_id,
        identifier_masked=report.identifier_masked,
        identifier_type=report.identifier_type.value,
        risk_score=report.risk_score,
        risk_dimensions=[
            RiskDimensionType(name=d.name, score=d.score)
            for d in report.risk_dimensions
        ],
        risk_factors=[
            RiskFactorType(
                code=f.code,
                description=f.description,
                weight=f.weight,
                source=f.source,
                dimension=f.dimension,
            )
            for f in report.risk_factors
        ],
        related_parties=[
            RelatedPartyType(
                nome=p.nome,
                vinculo=p.vinculo,
                tipo=p.tipo,
                fonte=p.fonte,
                resumo=p.resumo,
                total_ocorrencias=p.total_ocorrencias,
                homonimo_possivel=p.homonimo_possivel,
            )
            for p in report.related_parties
        ],
        recommendations=report.recommendations,
        summary=report.summary,
        hitl_status=report.hitl_status.value,
        results=results_list,
    )


def _get_orchestrator():
    """Retorna o orquestrador singleton com todas as dependências injetadas."""
    from src.integrations.orchestrator import get_intelligence_orchestrator

    return get_intelligence_orchestrator()


@strawberry.type
class Query:
    @strawberry.field
    async def intelligence(
        self,
        info: strawberry.types.Info[IntelligenceContext, None],
        identifier: str,
        sources: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0,
        expand_qsa: bool = False,
    ) -> ConsolidatedReportType:
        """Investigação jurídica 360° para um identificador (CPF/CNPJ/OAB/processo)."""
        principal: Principal = info.context.principal
        from src.api.auth import AuthManager

        if AuthManager.REQUIRED and not principal.has_permission("intelligence:query"):
            raise PermissionError("Permissão 'intelligence:query' necessária")

        orch = _get_orchestrator()
        report = await orch.investigate(
            identifier,
            sources=sources,
            principal_id=principal.user_id,
            limit=limit,
            offset=offset,
            expand_qsa=expand_qsa,
        )
        return _report_to_gql(report)

    @strawberry.field
    def intelligence_health(
        self,
        info: strawberry.types.Info[IntelligenceContext, None],
    ) -> List[SourceHealthType]:
        """Status de saúde de cada fonte de integração."""
        registry = get_registry()
        result = []
        from src.integrations.orchestrator import _source_circuit_breakers

        for name in registry.names():
            adapter = registry.get(name)
            if adapter:
                cb = _source_circuit_breakers.get(f"integration_{name}")
                result.append(
                    SourceHealthType(
                        source=name,
                        enabled=adapter.enabled,
                        mode=adapter.settings.mode,
                        zone=adapter.zone.value,
                        circuit_breaker=cb.state.value if cb else "closed",
                    )
                )
        return result


def get_registry():
    from src.integrations.registry import get_registry as _get

    return _get()


schema = strawberry.Schema(
    query=Query,
    extensions=[QueryDepthLimiter(max_depth=10)],
)


def create_graphql_router() -> GraphQLRouter:
    return GraphQLRouter(
        schema,
        context_getter=get_context,
        graphql_ide="graphiql" if not _ENV_PROD else None,
    )
