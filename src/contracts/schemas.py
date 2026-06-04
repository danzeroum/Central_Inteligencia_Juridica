"""Schemas Pydantic da análise de contratos (Frente F.3)."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

# Reaproveita o disclaimer da OAB já definido na geração de peças (Frente F.2):
# todo output jurídico carrega a mesma salvaguarda profissional.
from src.documents.schemas import DISCLAIMER_OAB


class Achado(BaseModel):
    """Uma cláusula sinalizada como de risco."""

    clausula_indice: int
    trecho: str
    categoria: str
    base_legal: str
    severidade: str  # alta | media | baixa
    recomendacao: str


class ContractAnalysisResult(BaseModel):
    """Relatório estruturado de risco de um contrato."""

    total_clausulas: int
    achados: List[Achado] = Field(default_factory=list)
    score_risco: int = 0
    nivel_risco: str = "sem_apontamentos"  # alto | medio | baixo | sem_apontamentos
    # Invariante: análise jurídica SEMPRE passa por revisão humana.
    requires_human_review: bool = True
    disclaimer: str = DISCLAIMER_OAB

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_clausulas": 3,
                "achados": [
                    {
                        "clausula_indice": 1,
                        "trecho": "A CONTRATADA não se responsabiliza por...",
                        "categoria": "Exoneração/limitação de responsabilidade",
                        "base_legal": "CDC art. 51, I; CC art. 424",
                        "severidade": "alta",
                        "recomendacao": "Cláusula pode ser nula em relação de consumo.",
                    }
                ],
                "score_risco": 5,
                "nivel_risco": "alto",
                "requires_human_review": True,
                "disclaimer": DISCLAIMER_OAB,
            }
        }
    }


__all__ = ["Achado", "ContractAnalysisResult"]
