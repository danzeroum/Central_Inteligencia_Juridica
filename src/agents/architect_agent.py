"""Architect agent responsible for high-level reasoning with CoT.

Performs chain-of-thought analysis tailored for legal/tribunal context,
with optional plan creation and ADR generation for architectural tasks.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from src.utils.input_sanitizer import InputSanitizer

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class ArchitectAgent:
    """Performs lightweight chain-of-thought style reasoning for legal tribunals."""

    def __init__(
        self,
        llm_fn: Optional[Callable[[str], str]] = None,
        use_llm: Optional[bool] = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.sanitizer = InputSanitizer()
        # CoT por LLM (H18/C2): opcional e plugável. Quando habilitado, a NARRATIVA
        # de raciocínio (chain_of_thought) é gerada por um LLM; a identificação de
        # tribunais e a confiança permanecem DETERMINÍSTICAS (reprodutibilidade do
        # roteamento). Sem LLM disponível ou em erro, degrada para a heurística.
        # ``llm_fn(prompt) -> str``; default = Ollama local (lazy). Flag:
        # ``ARCHITECT_COT_LLM=1``.
        self._llm_fn: Optional[Callable[[str], str]] = llm_fn
        self._use_llm: bool = (
            use_llm if use_llm is not None else _env_flag("ARCHITECT_COT_LLM", False)
        )
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
        self.metadata = {
            "reasoning_engine": "deterministic_keyword_heuristic",
            "cot_mode": (
                "llm+heuristica" if self._use_llm else "heuristica_deterministica"
            ),
            "llm_note": (
                "CoT plugável: narrativa pode vir de LLM (ARCHITECT_COT_LLM=1 ou "
                "llm_fn) com fallback determinístico; identificação de tribunais e "
                "confiança permanecem sempre determinísticas"
            ),
            "tribunal_keywords": {
                "TJSP": ["tjsp", "sao", "paulo"],
                "TJMG": ["tjmg", "minas", "gerais"],
                "TJRS": ["tjrs", "gaucho", "sul"],
                "TJRJ": ["tjrj", "fluminense", "rj"],
                "STF": ["stf", "supremo", "federal"],
            },
            "default_tribunal": "TJSP",
            "confidence": {
                "empty_task": 0.2,
                "base": 0.6,
                "increment_per_tribunal": 0.1,
                "max": 1.0,
            },
            "cot_steps_count": 5,
            "adr_status_default": "Accepted",
            "plan_components_default": [
                "API Gateway",
                "Auth Service",
                "Business Logic",
                "Database",
            ],
            "estimated_effort_default": "2 sprints",
            "risks_default": ["Complexidade", "Custo operacional"],
            "max_reasoning_history": None,
        }

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

        # C2: enriquece a NARRATIVA com LLM quando habilitado (tribunais/confiança
        # permanecem determinísticos). Qualquer falha → mantém o payload heurístico.
        if self._use_llm:
            reasoning_payload = self._enrich_with_llm(sanitized, reasoning_payload)

        self.reasoning_history.append(reasoning_payload)
        self.logger.info(
            "ArchitectAgent concluiu CoT com tribunais: %s", unique_tribunals
        )
        return reasoning_payload

    def _default_llm_fn(self) -> Optional[Callable[[str], str]]:
        """Resolve o cliente LLM (injeção explícita ou Ollama local lazy).

        Import preguiçoso mantém o agente importável mesmo sem o pacote ``ollama``
        instalado (retorna None → heurística determinística).
        """
        if self._llm_fn is not None:
            return self._llm_fn
        try:
            from src.services.llm_client import gerar_resposta_ollama

            return gerar_resposta_ollama
        except Exception:  # pragma: no cover - dependência opcional ausente
            return None

    def _enrich_with_llm(
        self, task_description: str, base_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Gera a narrativa (chain_of_thought) via LLM, preservando o roteamento.

        ``identified_tribunals`` e ``confidence`` são mantidos do payload
        determinístico. Qualquer falha/resposta inválida retorna o ``base_payload``
        inalterado (degradação graciosa).
        """
        llm = self._default_llm_fn()
        if llm is None:
            return base_payload

        tribunais = ", ".join(base_payload.get("identified_tribunals", [])) or "n/d"
        prompt = (
            "Você é um agente arquiteto de um sistema jurídico brasileiro. Raciocine "
            "em PASSOS NUMERADOS (chain-of-thought) sobre como abordar a solicitação "
            "a seguir. Responda apenas com os passos, um por linha.\n\n"
            f"Solicitação: {task_description}\n"
            f"Tribunais identificados (roteamento): {tribunais}\n"
        )
        try:
            text = llm(prompt)
        except Exception:
            self.logger.warning(
                "CoT-LLM falhou; mantendo heurística determinística", exc_info=True
            )
            return base_payload

        if not isinstance(text, str):
            return base_payload
        stripped = text.strip()
        # llm_client devolve "Erro: ..." quando o serviço está indisponível.
        if not stripped or stripped.lower().startswith("erro"):
            return base_payload

        steps = [line.strip() for line in stripped.splitlines() if line.strip()]
        if not steps:
            return base_payload

        enriched = dict(base_payload)
        enriched["chain_of_thought"] = steps
        enriched["problem_analysis"] = steps[0]
        enriched["reasoning_engine"] = "llm"
        return enriched

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
