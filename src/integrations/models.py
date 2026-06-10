"""Modelos normalizados da camada de integrações jurídicas (Onda 1).

Todos os adaptadores produzem e consomem estes tipos — nunca estruturas ad-hoc.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field


class IdentifierType(str, Enum):
    CPF = "CPF"
    CNPJ = "CNPJ"
    OAB = "OAB"
    NUMERO_PROCESSO = "NUMERO_PROCESSO"
    NOME = "NOME"


class DataMode(str, Enum):
    REAL = "real"
    MOCK = "mock"


class AdapterStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceZone(str, Enum):
    PUBLICA = "publica"
    CREDENCIADA = "credenciada"
    RESTRITA = "restrita"


class HitlStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------


class IdentifierQuery(BaseModel):
    identifier: str
    identifier_type: IdentifierType
    limit: int = 20
    offset: int = 0
    extra: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Itens normalizados
# ---------------------------------------------------------------------------


class ProcessoNormalizado(BaseModel):
    numero_processo: str
    tribunal: str
    grau: Optional[str] = None
    data_ajuizamento: Optional[str] = None
    assuntos: List[Dict[str, Any]] = Field(default_factory=list)
    movimentos: List[Dict[str, Any]] = Field(default_factory=list)
    partes: List[Dict[str, Any]] = Field(default_factory=list)
    classe: Optional[str] = None
    orgao_julgador: Optional[str] = None


class Publicacao(BaseModel):
    numero_processo: Optional[str] = None
    data_disponibilizacao: Optional[str] = None
    texto: Optional[str] = None
    tribunal: Optional[str] = None
    tipo: Optional[str] = None
    destinatario: Optional[str] = None


class SocioQSA(BaseModel):
    nome: str
    qualificacao: Optional[str] = None
    tipo: Optional[str] = None  # PF | PJ
    identificador_mascarado: Optional[str] = None
    data_entrada: Optional[str] = None


class EmpresaCadastro(BaseModel):
    cnpj: str
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    situacao_cadastral: Optional[str] = None
    data_abertura: Optional[str] = None
    capital_social: Optional[float] = None
    porte: Optional[str] = None
    cnae_principal: Optional[Dict[str, Any]] = None
    cnaes_secundarios: List[Dict[str, Any]] = Field(default_factory=list)
    opcao_simples: Optional[bool] = None
    opcao_mei: Optional[bool] = None
    uf: Optional[str] = None
    municipio: Optional[str] = None
    natureza_juridica: Optional[Dict[str, Any]] = None
    qsa: List[SocioQSA] = Field(default_factory=list)


class CandidaturaTSE(BaseModel):
    nome: Optional[str] = None
    cpf: Optional[str] = None
    partido: Optional[str] = None
    cargo: Optional[str] = None
    ano_eleicao: Optional[int] = None
    uf: Optional[str] = None
    municipio: Optional[str] = None
    situacao: Optional[str] = None


class Protesto(BaseModel):
    cartorio: Optional[str] = None
    data_protesto: Optional[str] = None
    valor: Optional[float] = None
    credor: Optional[str] = None
    tipo: Optional[str] = None
    situacao: Optional[str] = None


class PendenciaCadin(BaseModel):
    orgao: Optional[str] = None
    tipo_pendencia: Optional[str] = None
    valor: Optional[float] = None
    data_inscricao: Optional[str] = None
    situacao: Optional[str] = None


class Imovel(BaseModel):
    matricula: Optional[str] = None
    cartorio: Optional[str] = None
    tipo_imovel: Optional[str] = None
    municipio: Optional[str] = None
    area: Optional[float] = None
    data_registro: Optional[str] = None
    proprietario: Optional[str] = None
    uf: Optional[str] = None


# ---------------------------------------------------------------------------
# Resultado do adaptador (genérico)
# ---------------------------------------------------------------------------

ItemT = TypeVar("ItemT", bound=BaseModel)


class AdapterResult(BaseModel, Generic[ItemT]):
    source: str
    status: AdapterStatus
    data_mode: DataMode = DataMode.REAL
    items: List[Any] = Field(default_factory=list)
    total_available: int = 0
    error: Optional[str] = None
    latency_ms: float = 0.0
    from_cache: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Risk Engine
# ---------------------------------------------------------------------------


class RiskFactor(BaseModel):
    code: str
    description: str
    weight: int
    source: str
    dimension: str


class RiskDimension(BaseModel):
    name: str
    score: float = Field(ge=0, le=100)


class RelatedPartyFinding(BaseModel):
    nome: str
    vinculo: str = "socio"
    tipo: Optional[str] = None  # PF | PJ
    fonte: str
    resumo: Optional[str] = None
    total_ocorrencias: int = 0
    homonimo_possivel: bool = False


# ---------------------------------------------------------------------------
# Relatório consolidado
# ---------------------------------------------------------------------------


class ConsolidatedReport(BaseModel):
    query_id: str
    identifier_masked: str
    identifier_type: IdentifierType
    results: Dict[str, Any] = Field(default_factory=dict)
    risk_score: float = Field(ge=0, le=100, default=0.0)
    risk_dimensions: List[RiskDimension] = Field(default_factory=list)
    risk_factors: List[RiskFactor] = Field(default_factory=list)
    related_parties: List[RelatedPartyFinding] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    hitl_status: HitlStatus = HitlStatus.NOT_REQUIRED
    metadata: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "IdentifierType",
    "DataMode",
    "AdapterStatus",
    "SourceZone",
    "HitlStatus",
    "IdentifierQuery",
    "ProcessoNormalizado",
    "Publicacao",
    "SocioQSA",
    "EmpresaCadastro",
    "CandidaturaTSE",
    "Protesto",
    "PendenciaCadin",
    "Imovel",
    "AdapterResult",
    "RiskFactor",
    "RiskDimension",
    "RelatedPartyFinding",
    "ConsolidatedReport",
]
