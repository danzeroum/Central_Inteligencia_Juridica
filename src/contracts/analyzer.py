"""Analisador de contratos (Frente F.3).

Recebe o TEXTO do contrato (extração de PDF é fora do escopo deste repo) e o
varre cláusula a cláusula contra o catálogo de risco externalizado, produzindo
um relatório estruturado com score e nível de risco. A detecção é determinística
por padrão; um ``detector`` (LLM) pode ser injetado como hook opcional.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, List, Optional

from src.contracts.rules import ContractRuleSet, get_contract_rules
from src.contracts.schemas import Achado, ContractAnalysisResult

logger = logging.getLogger(__name__)

# Peso por severidade para compor o score de risco.
SEVERITY_WEIGHT = {"alta": 5, "media": 3, "baixa": 1}

# Hook opcional: recebe (texto, clausulas) e devolve a lista de achados.
DetectorContrato = Callable[[str, List[str]], List[Achado]]

_SPLIT_RE = re.compile(r"\n\s*\n+")


def _dividir_clausulas(texto: str) -> List[str]:
    """Divide o contrato em cláusulas (parágrafos; fallback por linha)."""

    partes = [p.strip() for p in _SPLIT_RE.split(texto) if p.strip()]
    if len(partes) <= 1:
        partes = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    return partes


def _nivel_risco(achados: List[Achado]) -> str:
    severidades = {a.severidade for a in achados}
    if "alta" in severidades:
        return "alto"
    if "media" in severidades:
        return "medio"
    if "baixa" in severidades:
        return "baixo"
    return "sem_apontamentos"


class ContractAnalyzer:
    """Analisa o texto de um contrato e produz um relatório de risco."""

    def __init__(self, ruleset: Optional[ContractRuleSet] = None) -> None:
        self._rules = ruleset or get_contract_rules()

    def analisar(
        self,
        texto: str,
        *,
        detector: Optional[DetectorContrato] = None,
    ) -> ContractAnalysisResult:
        clausulas = _dividir_clausulas(texto)

        if detector is not None:
            achados = list(detector(texto, clausulas))
        else:
            achados = self._detectar_por_regras(clausulas)

        score = sum(SEVERITY_WEIGHT.get(a.severidade, 0) for a in achados)
        return ContractAnalysisResult(
            total_clausulas=len(clausulas),
            achados=achados,
            score_risco=score,
            nivel_risco=_nivel_risco(achados),
            requires_human_review=True,
        )

    def _detectar_por_regras(self, clausulas: List[str]) -> List[Achado]:
        achados: List[Achado] = []
        for indice, clausula in enumerate(clausulas):
            for rule in self._rules:
                if rule.matches(clausula):
                    achados.append(
                        Achado(
                            clausula_indice=indice,
                            trecho=clausula[:200],
                            categoria=rule.categoria,
                            base_legal=rule.base_legal,
                            severidade=rule.severidade,
                            recomendacao=rule.recomendacao,
                        )
                    )
        return achados


def register_contract_tools(
    registry: Any, analyzer: Optional[ContractAnalyzer] = None
) -> ContractAnalyzer:
    """Registra a ferramenta de análise de contratos num ``MCPToolRegistry``."""

    analyzer = analyzer or ContractAnalyzer()

    @registry.register_tool("analisar_contrato")
    def _analisar(texto: str) -> ContractAnalysisResult:
        return analyzer.analisar(texto)

    return analyzer


__all__ = ["ContractAnalyzer", "register_contract_tools", "SEVERITY_WEIGHT"]
