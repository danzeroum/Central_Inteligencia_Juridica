"""Tipos Strawberry para o schema GraphQL de inteligência jurídica.

Tipos definidos manualmente (não usando ponte experimental pydantic↔strawberry).
"""

from __future__ import annotations

from typing import List, Optional

import strawberry


@strawberry.type
class RiskDimensionType:
    name: str
    score: float


@strawberry.type
class RiskFactorType:
    code: str
    description: str
    weight: int
    source: str
    dimension: str


@strawberry.type
class RelatedPartyType:
    nome: str
    vinculo: str
    tipo: Optional[str]
    fonte: str
    resumo: Optional[str]
    total_ocorrencias: int
    homonimo_possivel: bool


@strawberry.type
class AdapterResultType:
    source: str
    status: str
    data_mode: str
    from_cache: bool
    latency_ms: float
    total_available: int
    error: Optional[str]


@strawberry.type
class ConsolidatedReportType:
    query_id: str
    identifier_masked: str
    identifier_type: str
    risk_score: float
    risk_dimensions: List[RiskDimensionType]
    risk_factors: List[RiskFactorType]
    related_parties: List[RelatedPartyType]
    recommendations: List[str]
    summary: Optional[str]
    hitl_status: str
    results: List[AdapterResultType]


@strawberry.type
class SourceHealthType:
    source: str
    enabled: bool
    mode: str
    zone: str
