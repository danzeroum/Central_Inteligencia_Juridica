<<<<<<< HEAD
"""Architect agent implementing Chain-of-Thought reasoning."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
import logging

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """Senior system architect capable of Chain-of-Thought analysis."""

    def __init__(self) -> None:
        super().__init__("architect")
        self.reasoning_history: List[Dict[str, Any]] = []
        self.tools = ["analyze_architecture", "generate_adr"]

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_input(task):
            raise ValueError("Invalid architectural task payload")

        description = task.get("description", "")
        reasoning = self.reason_with_cot(description)
        plan = await self.create_plan(task, reasoning)
        adr = self.create_adr({
            "title": task.get("title", description[:60] or "Architecture Decision"),
            "problem_analysis": reasoning.get("problem_analysis", description),
            "recommendation": reasoning.get("recommendation", plan.get("architecture")),
            "trade_offs": reasoning.get("trade_offs", {}),
        })

        decision = {
            "task": task,
            "reasoning": reasoning,
            "plan": plan,
            "adr": adr,
            "confidence": reasoning.get("confidence", 0.0),
        }
        self.log_decision(decision)

        return {
            "success": True,
            "agent": self.agent_type,
            "reasoning": reasoning,
            "plan": plan,
            "adr": adr,
            "confidence": reasoning.get("confidence", 0.0),
        }

    def reason_with_cot(self, problem: str) -> Dict[str, Any]:
        """Produce a detailed, step-by-step architectural reasoning chain."""

        steps = [
            {
                "step": 1,
                "prompt": "Identify the core problem",
                "result": problem.strip() or "Problema não especificado",
            },
            {
                "step": 2,
                "prompt": "List the technical constraints",
                "result": ["P95 < 800ms", "Escalabilidade", "Compatibilidade retroativa"],
            },
            {
                "step": 3,
                "prompt": "Evaluate applicable design patterns",
                "result": ["Repository", "Factory", "Observer"],
            },
            {
                "step": 4,
                "prompt": "Analyse trade-offs",
                "result": {
                    "Repository": "Simplifica persistência mas adiciona camada extra",
                    "Observer": "Permite reatividade porém aumenta complexidade",
                },
            },
            {
                "step": 5,
                "prompt": "Select the optimal solution",
                "result": "Utilizar micro-serviços com camada de API Gateway e cache",
            },
        ]

        response = {
            "problem_analysis": steps[0]["result"],
            "constraints": steps[1]["result"],
            "applicable_patterns": steps[2]["result"],
            "trade_offs": steps[3]["result"],
            "recommendation": steps[4]["result"],
            "confidence": 0.85,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reasoning_steps": steps,
        }
        self.reasoning_history.append(response)
        return response

    async def create_plan(self, task: Dict[str, Any], reasoning: Dict[str, Any]) -> Dict[str, Any]:
        """Derive a lightweight architectural plan informed by the reasoning."""

        components = [
            "API Gateway",
            "Auth Service",
            "Business Logic",
            "Database",
        ]
        if "cache" in reasoning.get("recommendation", "").lower():
            components.append("Caching Layer")

        return {
            "goal": task.get("description", ""),
            "architecture": "microservices",
            "components": components,
            "patterns": reasoning.get("applicable_patterns", []),
            "risks": ["Complexidade", "Custo operacional"],
            "mitigations": ["Documentação", "Observabilidade"],
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
=======
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

>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
