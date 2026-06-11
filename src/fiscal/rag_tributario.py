"""TaxRAGService — RAG sobre legislação tributária brasileira (namespace 'tributario').

Seeds a minimal corpus of well-known tax statutes. Real ingestion happens via
POST /api/v1/fiscal/rag/ingest.

CJ-001: resultados incluem citações de fonte; sem invenção de normas.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_NAMESPACE = "tributario"

_SEED_CORPUS: List[Dict[str, Any]] = [
    {
        "id": "lc_116_2003",
        "content": (
            "Lei Complementar 116/2003 — Dispõe sobre o ISS (Imposto Sobre Serviços "
            "de Qualquer Natureza) de competência dos Municípios e do Distrito Federal. "
            "Alíquota mínima: 2%; máxima: 5%. Lista de serviços tributáveis em anexo."
        ),
        "metadata": {
            "tipo": "lei_complementar",
            "numero": "LC 116/2003",
            "tributo": "ISS",
            "fonte": "Presidência da República",
        },
    },
    {
        "id": "lei_12546_2012",
        "content": (
            "Lei 12.546/2012 — Institui o REINTEGRA (Regime Especial de Reintegração de "
            "Valores Tributários). Prevê desoneração da folha de pagamento: substituição da "
            "contribuição previdenciária patronal (INSS) por alíquota sobre Receita Bruta (CPRB) "
            "para setores específicos da economia."
        ),
        "metadata": {
            "tipo": "lei_ordinaria",
            "numero": "Lei 12.546/2012",
            "tributo": "INSS/CPRB",
            "fonte": "Presidência da República",
        },
    },
    {
        "id": "decreto_3000_1999",
        "content": (
            "Decreto 3.000/1999 — Regulamento do Imposto de Renda (RIR/1999). "
            "Disciplina a tributação de pessoas físicas e jurídicas, rendimentos, ganhos de "
            "capital e isenções. Base para cálculo IRPJ pelo Lucro Real, Presumido e Arbitrado."
        ),
        "metadata": {
            "tipo": "decreto",
            "numero": "Decreto 3.000/1999",
            "tributo": "IRPJ/IRPF",
            "fonte": "Presidência da República",
        },
    },
    {
        "id": "in_rfb_1700_2017",
        "content": (
            "IN RFB 1.700/2017 — Dispõe sobre a determinação e o pagamento do IRPJ e da CSLL. "
            "Consolida regras de apuração pelo Lucro Real, Presumido e Arbitrado. "
            "Percentuais de presunção do Lucro Presumido: de 1,6% (revenda de combustível) "
            "a 32% (serviços em geral)."
        ),
        "metadata": {
            "tipo": "instrucao_normativa",
            "numero": "IN RFB 1.700/2017",
            "tributo": "IRPJ/CSLL",
            "fonte": "Receita Federal do Brasil",
        },
    },
    {
        "id": "lei_9430_1996",
        "content": (
            "Lei 9.430/1996 — Regula recolhimento por estimativa do IRPJ no Lucro Real. "
            "Permite suspensão/redução com base em balancetes mensais. "
            "Multa de 75% sobre diferenças; 150% em caso de fraude ou sonegação."
        ),
        "metadata": {
            "tipo": "lei_ordinaria",
            "numero": "Lei 9.430/1996",
            "tributo": "IRPJ",
            "fonte": "Presidência da República",
        },
    },
    {
        "id": "lc_123_2006_simples",
        "content": (
            "Lei Complementar 123/2006 — Institui o Estatuto Nacional da Microempresa e da "
            "Empresa de Pequeno Porte; cria o Simples Nacional. Alíquotas unificadas em faixas "
            "de receita bruta anual; abrange IRPJ, CSLL, PIS, COFINS, IPI, CPP, ISS e ICMS "
            "em guia única (DAS). Limite ME: R$ 360 mil/ano; EPP: R$ 4,8 milhões/ano."
        ),
        "metadata": {
            "tipo": "lei_complementar",
            "numero": "LC 123/2006",
            "tributo": "Simples Nacional",
            "fonte": "Presidência da República",
        },
    },
]


class TaxRAGService:
    """RAG service for Brazilian tax law using ChromaDB namespace 'tributario'."""

    def __init__(self, rag_tool=None) -> None:
        self._rag: Optional[Any] = rag_tool
        self._seeded = False

    @property
    def rag(self):
        if self._rag is None:
            from src.tools.rag_tool import RAGTool

            self._rag = RAGTool()
        return self._rag

    def _seed_corpus(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        try:
            self.rag.add_documents_to_namespace(_NAMESPACE, _SEED_CORPUS)
            logger.debug("Corpus tributário seedado: %d documentos.", len(_SEED_CORPUS))
        except Exception as exc:
            logger.warning("Falha ao seedar corpus tributário: %s", exc)

    def query(
        self,
        query: str,
        *,
        n_results: int = 3,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Returns top-n tax law excerpts relevant to the query with source metadata."""
        self._seed_corpus()
        try:
            return self.rag.query_with_filter(
                query,
                namespace=_NAMESPACE,
                n_results=n_results,
                min_score=min_score,
            )
        except Exception as exc:
            logger.warning("TaxRAG query falhou: %s", exc)
            return []

    def ingest(self, documents: List[Dict[str, Any]]) -> int:
        """Ingests custom tax documents. Returns number successfully ingested."""
        valid = [d for d in documents if d.get("content") or d.get("text")]
        if not valid:
            return 0
        try:
            self.rag.add_documents_to_namespace(_NAMESPACE, valid)
            return len(valid)
        except Exception as exc:
            logger.error("Falha ao ingerir documentos tributários: %s", exc)
            return 0


_tax_rag: Optional[TaxRAGService] = None


def get_tax_rag() -> TaxRAGService:
    """Singleton para TaxRAGService."""
    global _tax_rag
    if _tax_rag is None:
        _tax_rag = TaxRAGService()
    return _tax_rag
