"""Architect agent responsible for high-level reasoning with CoT."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.utils.input_sanitizer import InputSanitizer


class ArchitectAgent:
    """Performs lightweight chain-of-thought style reasoning."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.sanitizer = InputSanitizer()

    def reason_with_cot(self, task_description: str) -> Dict[str, Any]:
        """Generate a structured reasoning payload for the supervisor."""

        sanitized = self.sanitizer.sanitize_text(task_description)
        tokens = sanitized.lower().split()

        analysis_steps: List[str] = []
        analysis_steps.append("1. Interpretar a solicitação jurídica do usuário.")

        if not sanitized:
            conclusion = "Solicitação vazia; manter modo padrão TJSP."
            self.logger.warning("ArchitectAgent recebeu tarefa vazia para CoT")
            return {
                "problem_analysis": "Tarefa vazia.",
                "chain_of_thought": analysis_steps,
                "recommendation": conclusion,
                "identified_tribunals": ["TJSP"],
                "confidence": 0.2,
            }

        analysis_steps.append(
            "2. Extrair entidades e tribunais mencionados explicitamente." \
        )

        tribunal_map = {
            "tjsp": "TJSP",
            "são": "TJSP",
            "sao": "TJSP",
            "paulo": "TJSP",
            "tjmg": "TJMG",
            "minas": "TJMG",
            "gerais": "TJMG",
            "tjrs": "TJRS",
            "gaucho": "TJRS",
            "gaúcho": "TJRS",
            "sul": "TJRS",
            "tjrj": "TJRJ",
            "fluminense": "TJRJ",
            "rj": "TJRJ",
            "stf": "STF",
            "supremo": "STF",
            "federal": "STF",
        }

        detected: List[str] = []
        for token in tokens:
            tribunal = tribunal_map.get(token)
            if tribunal:
                detected.append(tribunal)

        if "tribunais" in tokens or "comparar" in tokens or "comparação" in tokens:
            analysis_steps.append(
                "3. Solicitação sugere múltiplos tribunais ou comparação de jurisprudência."
            )

        unique_tribunals = list(dict.fromkeys(detected))
        if not unique_tribunals:
            if "federal" in tokens or "união" in tokens:
                unique_tribunals = ["STF"]
            else:
                unique_tribunals = ["TJSP"]

        analysis_steps.append(
            "4. Construir recomendação priorizando tribunais identificados e contexto do usuário."
        )

        recommendation = (
            "Consultar tribunais: " + ", ".join(unique_tribunals)
        )

        problem_analysis = (
            "A tarefa requer análise jurídica envolvendo os tribunais "
            + ", ".join(unique_tribunals)
            + "."
        )

        confidence = 0.6 + 0.1 * min(len(unique_tribunals), 3)

        reasoning_payload = {
            "problem_analysis": problem_analysis,
            "chain_of_thought": analysis_steps,
            "recommendation": recommendation,
            "identified_tribunals": unique_tribunals,
            "confidence": min(1.0, confidence),
        }

        self.logger.info(
            "ArchitectAgent concluiu CoT com tribunais: %s", unique_tribunals
        )
        return reasoning_payload

