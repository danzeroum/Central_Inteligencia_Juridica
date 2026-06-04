"""Schemas Pydantic da geração de peças (Frente F.2)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

# Ajuste de risco (Plano §7.2): disclaimer OBRIGATÓRIO no output, por exigência do
# Estatuto da OAB (Lei 8.906/94, art. 1º). Evita caracterizar exercício ilegal da
# advocacia pela plataforma.
DISCLAIMER_OAB = (
    "Este documento é um RASCUNHO gerado por IA e não substitui a revisão de "
    "advogado(a) habilitado(a) na OAB (Lei 8.906/94, art. 1º)."
)


class PostcheckResult(BaseModel):
    """Resultado da verificação pós-geração de uma peça."""

    ok: bool
    findings: List[str] = Field(default_factory=list)
    base_legal: Optional[str] = None


class PecaResult(BaseModel):
    """Peça processual gerada (sempre rascunho sujeito a revisão humana)."""

    tipo: str
    nome: str
    base_legal: str
    conteudo: str
    postcheck: PostcheckResult
    # Invariante: peça jurídica SEMPRE passa por HITL antes de qualquer entrega.
    requires_human_review: bool = True
    disclaimer: str = DISCLAIMER_OAB
    hitl_request_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "tipo": "peticao_inicial",
                "nome": "Petição Inicial",
                "base_legal": "CPC art. 319",
                "conteudo": "EXCELENTÍSSIMO(A) ...",
                "postcheck": {"ok": True, "findings": [], "base_legal": "CPC art. 319"},
                "requires_human_review": True,
                "disclaimer": DISCLAIMER_OAB,
                "hitl_request_id": None,
            }
        }
    }


__all__ = ["PostcheckResult", "PecaResult", "DISCLAIMER_OAB"]
