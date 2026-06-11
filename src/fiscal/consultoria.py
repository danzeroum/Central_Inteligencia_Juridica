"""ConsultoriaService — parecer tributário assistido por RAG (S-A.2).

Gera recomendações por perfil (regime, CNAE, porte) com citações verificáveis.
CJ-001: sem invenção de normas; parecer é auxiliar, não definitivo.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REGIME_LABELS: Dict[str, str] = {
    "simples_nacional": "Simples Nacional (LC 123/2006)",
    "lucro_presumido": "Lucro Presumido (IN RFB 1.700/2017 + Lei 9.430/1996)",
    "lucro_real": "Lucro Real (Decreto 3.000/1999 + IN RFB 1.700/2017)",
    "mei": "MEI — Microempreendedor Individual (LC 128/2008)",
}

_PORTE_LABELS: Dict[str, str] = {
    "mei": "MEI (até R$ 81 mil/ano)",
    "me": "Microempresa — ME (até R$ 360 mil/ano)",
    "epp": "Empresa de Pequeno Porte — EPP (até R$ 4,8 mi/ano)",
    "medio": "Médio Porte",
    "grande": "Grande Porte",
}

_GUARDRAIL = (
    "AVISO CJ-001: Este parecer é auxiliar e baseado exclusivamente em legislação "
    "indexada. Não substitui consultoria jurídica ou tributária profissional. "
    "Verifique a vigência das normas citadas antes de qualquer decisão."
)


class ConsultoriaService:
    """Generates preliminary tax advisories with RAG-sourced citations."""

    def __init__(self, tax_rag=None) -> None:
        self._tax_rag = tax_rag

    @property
    def tax_rag(self):
        if self._tax_rag is None:
            from src.fiscal.rag_tributario import get_tax_rag

            self._tax_rag = get_tax_rag()
        return self._tax_rag

    async def gerar_parecer(
        self,
        *,
        regime: str,
        cnae: str,
        porte: str,
        pergunta: str,
        n_citations: int = 3,
    ) -> Dict[str, Any]:
        """Returns a preliminary tax advisory with verifiable citations.

        CJ-001: citations sourced exclusively from indexed legislation.
        """
        regime_label = _REGIME_LABELS.get(regime.lower(), regime)
        porte_label = _PORTE_LABELS.get(porte.lower(), porte)

        query = f"{pergunta} {regime_label} CNAE {cnae} {porte_label}"
        citations: List[Dict[str, Any]] = self.tax_rag.query(
            query, n_results=n_citations
        )

        if citations:
            parts: List[str] = []
            for c in citations:
                meta = c.get("metadata", {})
                numero = meta.get("numero", "")
                tributo = meta.get("tributo", "")
                fonte = meta.get("fonte", "")
                header = f"[{numero}]" if numero else ""
                suffix_parts = []
                if tributo:
                    suffix_parts.append(tributo)
                if fonte:
                    suffix_parts.append(fonte)
                suffix = f" ({' — '.join(suffix_parts)})" if suffix_parts else ""
                excerpt = c.get("text", "")[:250]
                parts.append(f"{header} {excerpt}{suffix}".strip())

            recomendacao = (
                f"Para o perfil: regime={regime_label}, CNAE={cnae}, porte={porte_label}, "
                "identificamos as seguintes referências normativas relevantes:\n\n"
                + "\n\n".join(parts)
            )
        else:
            recomendacao = (
                f"Não foram encontradas normas indexadas para o perfil consultado "
                f"(regime={regime_label}, CNAE={cnae}, porte={porte_label}). "
                "Recomendamos consultar diretamente a Receita Federal do Brasil e a "
                "legislação tributária vigente para o seu setor de atividade."
            )

        return {
            "regime": regime_label,
            "cnae": cnae,
            "porte": porte_label,
            "pergunta": pergunta,
            "recomendacao": recomendacao,
            "citacoes": [
                {
                    "texto": c.get("text", ""),
                    "metadata": c.get("metadata", {}),
                    "score": round(c.get("score", 0.0), 4),
                }
                for c in citations
            ],
            "guardrail": _GUARDRAIL,
            "status": "preliminar",
            "module": "consultoria_tributaria",
        }


_consultoria_service: Optional[ConsultoriaService] = None


def get_consultoria_service() -> ConsultoriaService:
    """Singleton para ConsultoriaService."""
    global _consultoria_service
    if _consultoria_service is None:
        _consultoria_service = ConsultoriaService()
    return _consultoria_service
