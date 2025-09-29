"""Supervisor Agent - Orchestrator for multi-agent collaboration system."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

from src.agents.tribunal_agent import TribunalAgent
from src.routing.intent_classifier import ClassifiedIntent, IntentClassifier
from src.memory.vector_memory import VectorMemory
from src.utils.input_sanitizer import InputSanitizer
from src.utils.ledger import DecisionLedger
from src.utils.metrics_collector import MetricsCollector


class SupervisorAgent:
    """Coordinate specialized tribunal agents and maintain decision history."""

    def __init__(self, ledger: DecisionLedger | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.sanitizer = InputSanitizer()
        self.ledger = ledger or DecisionLedger()
        self.active_delegates: Dict[str, TribunalAgent] = {}
        self.task_history: List[Dict[str, Any]] = []

        # NOVO: Intent Classifier para routing inteligente
        self.intent_classifier = IntentClassifier(confidence_threshold=0.7)
        self.use_intelligent_routing = True

        # Vector Memory (Onda 2.2)
        self.memory = VectorMemory()

        if not self.memory.is_available():
            self.logger.warning(
                "VectorMemory not available. Memory features disabled. "
                "Start ChromaDB with: docker-compose up -d chromadb"
            )

    async def _classify_intent(self, sanitized_task: str) -> ClassifiedIntent:
        """Classifica a intenção do usuário usando LLM ou fallback keyword-based."""

        if (
            self.use_intelligent_routing
            and self.intent_classifier.llm_enabled
            and self.intent_classifier.should_use_llm(sanitized_task)
        ):
            self.logger.info("Using LLM-based intent classification")
            intent = await self.intent_classifier.classify(sanitized_task)

            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="INTENT_CLASSIFIED",
                metadata={
                    "method": "llm",
                    "confidence": intent.confidence,
                    "reasoning": intent.reasoning,
                    "tribunais": intent.tribunais,
                    "operacao": intent.operacao,
                },
            )

            if intent.confidence < self.intent_classifier.confidence_threshold:
                self.logger.warning(
                    "LLM confidence %.2f below threshold %.2f, using keyword fallback",
                    intent.confidence,
                    self.intent_classifier.confidence_threshold,
                )
                tribunals_keywords = self._identify_all_tribunals(sanitized_task)
                if tribunals_keywords:
                    intent.tribunais = tribunals_keywords
                    if intent.reasoning:
                        intent.reasoning = (
                            f"{intent.reasoning} | Tribunais ajustados por fallback"
                        )
                    else:
                        intent.reasoning = "Tribunais ajustados por fallback"
            return intent

        self.logger.info("Using keyword-based intent classification")
        tribunals = self._identify_all_tribunals(sanitized_task)
        intent = ClassifiedIntent(
            tribunais=tribunals,
            operacao="generic",
            parametros={},
            confidence=0.8,
            reasoning="Keyword-based fallback classification",
        )
        self.ledger.log_decision(
            agent_type="SupervisorAgent",
            decision_type="INTENT_CLASSIFIED",
            metadata={
                "method": "keywords",
                "confidence": intent.confidence,
                "reasoning": intent.reasoning,
                "tribunais": intent.tribunais,
                "operacao": intent.operacao,
            },
        )
        return intent

    async def process_task(self, task_description: str) -> Dict[str, Any]:
        """
        Main entry point for task processing.
        EVOLUÇÃO STANDARD: Usa LLM-based intent classification.
        """

        try:
            sanitized_task = self.sanitizer.sanitize_text(task_description)

            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="TASK_RECEIVED",
                metadata={
                    "original_task": task_description,
                    "sanitized_task": sanitized_task,
                    "step": "initial_processing",
                },
            )

            # Memory recall before intent classification
            recalled_memories: List[Dict[str, Any]] = []
            recall_time = 0.0
            memory_cache_hit = False
            cached_result: Dict[str, Any] | None = None

            if self.memory.is_available():
                recall_start = time.perf_counter()
                recalled_memories = self.memory.recall_similar(
                    sanitized_task,
                    k=3,
                )
                recall_time = time.perf_counter() - recall_start

                self.ledger.log_decision(
                    agent_type="SupervisorAgent",
                    decision_type="MEMORY_RECALLED",
                    metadata={
                        "recalled_count": len(recalled_memories),
                        "recall_time": recall_time,
                        "memories": [
                            {
                                "task": memory.get("original_task", "")[:100],
                                "similarity": memory.get("similarity_score", 0.0),
                                "tribunals": memory.get("tribunals", []),
                            }
                            for memory in recalled_memories
                        ],
                    },
                )

                if recalled_memories:
                    best_memory = recalled_memories[0]
                    similarity = float(best_memory.get("similarity_score", 0.0))
                    snapshot = best_memory.get("result_snapshot")

                    cache_threshold = 0.85
                    if self.memory.using_manual_embeddings:
                        cache_threshold = 0.1

                    tribunals_from_memory = best_memory.get("tribunals") or []

                    if (
                        snapshot
                        and similarity >= cache_threshold
                        and tribunals_from_memory
                    ):
                        try:
                            cached_result = json.loads(snapshot)
                        except (TypeError, ValueError) as exc:
                            self.logger.debug(
                                "Failed to deserialize cached result from memory: %s",
                                exc,
                            )
                        else:
                            if isinstance(cached_result, dict):
                                memory_cache_hit = True
                                self.ledger.log_decision(
                                    agent_type="SupervisorAgent",
                                    decision_type="MEMORY_CACHE_HIT",
                                    metadata={
                                        "similarity": similarity,
                                        "tribunals": best_memory.get("tribunals", []),
                                    },
                                )
                            else:
                                cached_result = None

            intent = await self._classify_intent(sanitized_task)

            if recalled_memories:
                best_memory = recalled_memories[0]
                memory_similarity = float(best_memory.get("similarity_score", 0.0))
                memory_tribunals = best_memory.get("tribunals") or []

                if memory_tribunals:
                    similarity_override_threshold = 0.5
                    if self.memory.using_manual_embeddings:
                        similarity_override_threshold = 0.1

                    if (
                        memory_similarity >= similarity_override_threshold
                        and (
                            not intent.tribunais
                            or intent.tribunais == ["TJSP"]
                        )
                    ):
                        intent.tribunais = list(dict.fromkeys(memory_tribunals))

            tribunal_codes = intent.tribunais if intent.tribunais else ["TJSP"]

            self.logger.info(
                "Processing task with %d tribunals: %s (op=%s, confidence=%.2f, recalled=%d)",
                len(tribunal_codes),
                tribunal_codes,
                intent.operacao,
                intent.confidence,
                len(recalled_memories),
            )

            if memory_cache_hit and cached_result is not None:
                elapsed_time = 0.0
                final_result = cached_result
                valid_results: List[Dict[str, Any]] = [cached_result]
            else:
                start_time = asyncio.get_event_loop().time()

                delegated_tasks = [
                    self._delegate_to_tribunal_agent(code, sanitized_task)
                    for code in tribunal_codes
                ]
                results = await asyncio.gather(
                    *delegated_tasks, return_exceptions=True
                )

                elapsed_time = asyncio.get_event_loop().time() - start_time

                valid_results = [
                    r
                    for r in results
                    if isinstance(r, dict) and not isinstance(r, Exception)
                ]
                errors = [r for r in results if isinstance(r, Exception)]

                if errors:
                    self.logger.warning("Errors in parallel execution: %s", errors)

                final_result = self._aggregate_results(valid_results, tribunal_codes)

                if valid_results and self.memory.is_available():
                    remember_success = self.memory.remember(
                        task=sanitized_task,
                        result=final_result,
                        metadata={
                            "tribunals": tribunal_codes,
                            "intent_operacao": intent.operacao,
                            "intent_confidence": intent.confidence,
                            "execution_time": elapsed_time,
                            "recalled_count": len(recalled_memories),
                            "timestamp": self._get_timestamp(),
                        },
                    )

                    if remember_success:
                        self.ledger.log_decision(
                            agent_type="SupervisorAgent",
                            decision_type="MEMORY_STORED",
                            metadata={"task": sanitized_task[:100]},
                        )

            task_record = {
                "task": sanitized_task,
                "tribunals": tribunal_codes,
                "intent": intent.model_dump(),
                "recalled_memories": len(recalled_memories),
                "result": final_result,
                "execution_time": elapsed_time,
                "recall_time": recall_time,
                "parallel": len(tribunal_codes) > 1,
                "memory_cache_hit": memory_cache_hit,
                "timestamp": self._get_timestamp(),
            }
            self.task_history.append(task_record)

            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="TASK_COMPLETED",
                metadata={
                    "tribunals": tribunal_codes,
                    "intent_confidence": intent.confidence,
                    "recalled_count": len(recalled_memories),
                    "result_status": final_result.get("status", "unknown"),
                    "execution_time": elapsed_time,
                },
            )

            return {
                "status": "success",
                "supervisor_result": final_result,
                "tribunals_used": tribunal_codes,
                "intent": {
                    "operacao": intent.operacao,
                    "confidence": intent.confidence,
                },
                "memory": {
                    "recalled_count": len(recalled_memories),
                    "recall_time": recall_time,
                    "cache_hit": memory_cache_hit,
                },
                "task_id": f"task_{len(self.task_history):04d}",
                "execution_time": elapsed_time,
                "parallel": len(tribunal_codes) > 1,
                "timestamp": self._get_timestamp(),
            }
        except Exception as exc:  # pragma: no cover - defensive
            error_msg = f"Supervisor processing error: {exc}"
            self.logger.error(error_msg, exc_info=True)
            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="TASK_ERROR",
                metadata={"error": error_msg},
            )
            return {
                "status": "error",
                "message": error_msg,
                "timestamp": self._get_timestamp(),
            }

    def _identify_all_tribunals(self, task: str) -> List[str]:
        """
        NOVO MÉTODO: Identifica TODOS os tribunais mencionados na tarefa.
        Substitui o antigo _identify_tribunal que retornava apenas um.
        """

        task_lower = task.lower()
        tribunal_keywords: Dict[str, List[str]] = {
            "TJSP": ["tjsp", "são paulo", "sao paulo", "sp"],
            "TJMG": ["tjmg", "minas gerais", "minas", "mg"],
            "TJRS": ["tjrs", "rio grande do sul", "gaúcho", "gaucho", "rs"],
            "TJRJ": ["tjrj", "rio de janeiro", "fluminense", "rj"],
            "STF": ["stf", "supremo", "federal"],
        }

        found_tribunals = []
        for tribunal, keywords in tribunal_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                found_tribunals.append(tribunal)

        return list(dict.fromkeys(found_tribunals))

    async def _delegate_to_tribunal_agent(
        self, tribunal_code: str, task: str
    ) -> Dict[str, Any]:
        """Delega tarefa ao agente especializado."""

        if tribunal_code not in self.active_delegates:
            self.active_delegates[tribunal_code] = TribunalAgent(
                tribunal_code=tribunal_code,
                ledger=self.ledger,
            )
            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="AGENT_CREATED",
                metadata={
                    "tribunal": tribunal_code,
                    "delegate_count": len(self.active_delegates),
                },
            )
            MetricsCollector.set_agent_active(tribunal_code, True)

        agent = self.active_delegates[tribunal_code]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, agent.execute_task, task)

    def _aggregate_results(
        self, results: List[Dict[str, Any]], tribunal_codes: List[str]
    ) -> Dict[str, Any]:
        """Agrega múltiplos resultados em resposta única estruturada."""

        if not results:
            return {
                "status": "no_results",
                "message": "Nenhum resultado válido obtido",
                "tribunals_queried": tribunal_codes,
            }

        if len(results) == 1:
            return results[0]

        aggregated = {
            "status": "multiple_results",
            "count": len(results),
            "tribunals": {},
        }

        for result in results:
            tribunal = result.get("tribunal", "unknown")
            aggregated["tribunals"][tribunal] = result

        return aggregated

    def get_api_health_stats(self) -> Dict[str, Any]:
        """Retorna estado das integrações reais para cada tribunal ativo."""

        return {
            tribunal: agent.get_circuit_breaker_stats()
            for tribunal, agent in self.active_delegates.items()
        }

    def get_agent_stats(self) -> Dict[str, Any]:
        """Return statistics about active agents."""

        stats = {
            "total_delegates": len(self.active_delegates),
            "active_tribunals": list(self.active_delegates.keys()),
            "total_tasks_processed": len(self.task_history),
            "parallel_tasks_count": sum(
                1 for t in self.task_history if t.get("parallel", False)
            ),
            "tasks_with_memory_recall": sum(
                1 for t in self.task_history if t.get("recalled_memories", 0) > 0
            ),
            "tasks_with_memory_cache_hit": sum(
                1 for t in self.task_history if t.get("memory_cache_hit")
            ),
            "latest_tasks": self.task_history[-5:] if self.task_history else [],
        }

        if self.memory.is_available():
            stats["memory"] = self.memory.get_stats()

        if self.active_delegates:
            stats["api_health"] = self.get_api_health_stats()

        MetricsCollector.set_total_agents(
            {tribunal: 1 for tribunal in self.active_delegates}
        )
        return stats

    def _get_timestamp(self) -> str:
        return datetime.now().isoformat()


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    async def demo() -> None:
        supervisor = SupervisorAgent()

        result1 = await supervisor.process_task("Status do TJSP")
        print(f"✅ Single: {result1['tribunals_used']}")

        result2 = await supervisor.process_task("Status do TJSP e TJMG")
        print(f"✅ Parallel: {result2['tribunals_used']}")
        print(f"⚡ Time: {result2['execution_time']:.3f}s")

    asyncio.run(demo())

