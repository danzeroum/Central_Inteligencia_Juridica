"""Architect agent responsible for high-level reasoning with CoT.

Performs chain-of-thought analysis tailored for legal/tribunal context,
with optional plan creation and ADR generation for architectural tasks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.utils.input_sanitizer import InputSanitizer

logger = logging.getLogger(__name__)


class ArchitectAgent:
    """Performs lightweight chain-of-thought style reasoning for legal tribunals."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.sanitizer = InputSanitizer()
        self.reasoning_history: List[Dict[str, Any]] = []
        self.memory: Any = None
        self.agent_type = "architect"
        self.name = "Architect Agent"
        self.description = "Realiza raciocínio chain-of-thought determinístico para planejamento jurídico e geração de ADRs."
        self.capabilities = [
            "chain_of_thought",
            "planning",
            "adr_generation",
            "tribunal_routing",
        ]
        self.specialization = "architecture"
        self.tools = ["input_sanitizer", "reasoning_history"]
        self.version = "1.0.0"
        self.status = "active"

    def attach_memory(self, memory: Any) -> None:
        """Permite que orquestradores injetem um backend de memória.

        Mantém a paridade de interface com ``BaseAgent.attach_memory`` para que o
        ArchitectAgent possa ser orquestrado de forma uniforme com os demais
        agentes (corrige AttributeError no UnifiedOrchestrator).
        """

        self.memory = memory

    def reason_with_cot(self, task_description: str) -> Dict[str, Any]:
        """Generate a structured reasoning payload for the supervisor.

        NOTA DE PROJETO (H18): este "chain-of-thought" é uma heurística
        DETERMINÍSTICA baseada em correspondência de palavras-chave — não uma
        chamada a LLM. A escolha é intencional: garante reprodutibilidade e
        independência de serviço externo no roteamento. Um modo LLM real pode ser
        plugado no futuro via ``IntentClassifier`` (que já tem fallback heurístico),
        sem alterar o contrato deste método.
        """

        sanitized = self.sanitizer.sanitize_text(task_description)
        tokens = sanitized.lower().split()

        analysis_steps: List[str] = []
        analysis_steps.append("1. Interpretar a solicitacao juridica do usuario.")

        if not sanitized:
            conclusion = "Solicitacao vazia; manter modo padrao TJSP."
            self.logger.warning("ArchitectAgent recebeu tarefa vazia para CoT")
            return {
                "problem_analysis": "Tarefa vazia.",
                "chain_of_thought": analysis_steps,
                "recommendation": conclusion,
                "identified_tribunals": ["TJSP"],
                "confidence": 0.2,
            }

        analysis_steps.append(
            "2. Extrair entidades e tribunais mencionados explicitamente."
        )

        tribunal_map = {
            "tjsp": "TJSP",
            "sao": "TJSP",
            "paulo": "TJSP",
            "tjmg": "TJMG",
            "minas": "TJMG",
            "gerais": "TJMG",
            "tjrs": "TJRS",
            "gaucho": "TJRS",
            "ga\u00facho": "TJRS",
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

        # Passo 3: avaliação de multiplicidade (sempre presente, com texto
        # adaptado ao caso) — mantém a cadeia de raciocínio com numeração
        # consistente e contagem determinística de etapas.
        if any(
            keyword in tokens for keyword in ["tribunais", "comparar", "comparacao"]
        ):
            analysis_steps.append(
                "3. Solicitacao sugere multiplos tribunais ou comparacao de jurisprudencia."
            )
        else:
            analysis_steps.append(
                "3. Avaliar abrangencia: tarefa parece envolver jurisdicao unica."
            )

        unique_tribunals = list(dict.fromkeys(detected))
        if not unique_tribunals:
            if "federal" in tokens or "uniao" in tokens:
                unique_tribunals = ["STF"]
            else:
                unique_tribunals = ["TJSP"]

        analysis_steps.append(
            "4. Mapear tribunais identificados para os agentes especializados."
        )
        analysis_steps.append(
            "5. Construir recomendacao priorizando tribunais identificados e contexto do usuario."
        )

        recommendation = "Consultar tribunais: " + ", ".join(unique_tribunals)
        problem_analysis = (
            "A tarefa requer analise juridica envolvendo os tribunais "
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.reasoning_history.append(reasoning_payload)
        self.logger.info(
            "ArchitectAgent concluiu CoT com tribunais: %s", unique_tribunals
        )
        return reasoning_payload

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Interface assíncrona uniforme com os demais agentes.

        Adapta o raciocínio síncrono (``reason_with_cot``) ao contrato
        ``execute`` esperado pelo UnifiedOrchestrator e pelos testes de
        integração, expondo ``reasoning_steps`` e ``confidence``.
        """

        description = task.get("description", "")
        reasoning = self.reason_with_cot(description)
        return {
            "success": True,
            "agent": "architect",
            "reasoning": {
                "reasoning_steps": reasoning["chain_of_thought"],
                "recommendation": reasoning["recommendation"],
                "identified_tribunals": reasoning["identified_tribunals"],
                "problem_analysis": reasoning["problem_analysis"],
            },
            "confidence": reasoning["confidence"],
        }

    def create_plan(
        self, task: Dict[str, Any], reasoning: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Derive a lightweight architectural plan informed by the reasoning."""

        components = ["API Gateway", "Auth Service", "Business Logic", "Database"]
        if "cache" in reasoning.get("recommendation", "").lower():
            components.append("Caching Layer")

        return {
            "goal": task.get("description", ""),
            "architecture": "microservices",
            "components": components,
            "patterns": reasoning.get("applicable_patterns", []),
            "risks": ["Complexidade", "Custo operacional"],
            "mitigations": ["Documentacao", "Observabilidade"],
            "estimated_effort": "2 sprints",
        }

    def create_adr(self, decision: Dict[str, Any]) -> str:
        """Generate an Architecture Decision Record style note."""

        return (
            f"# ADR: {decision.get('title', 'Architecture Decision')}\n\n"
            "## Status\nAccepted\n\n"
            "## Context\n"
            f"{decision.get('problem_analysis', 'N/A')}\n\n"
            "## Decision\n"
            f"{decision.get('recommendation', 'N/A')}\n\n"
            "## Consequences\n"
            f"{decision.get('trade_offs', 'N/A')}\n"
        )
