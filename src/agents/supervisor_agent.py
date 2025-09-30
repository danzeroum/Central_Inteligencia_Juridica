"""Supervisor Agent - Orchestrator for multi-agent collaboration system."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List

from src.agents.architect_agent import ArchitectAgent
from src.agents.tribunal_agent import TribunalAgent
from src.consensus.weighted_voting import WeightedConsensusEngine
from src.protocols.a2a_mixin import A2ACapable
from src.routing.intent_classifier import ClassifiedIntent, IntentClassifier
from src.memory.agent_memory import AgentMemorySystem
from src.memory.vector_memory import VectorMemory
from src.utils.input_sanitizer import InputSanitizer
from src.utils.ledger import DecisionLedger
from src.utils.metrics_collector import MetricsCollector
from src.utils.decision_metrics import DecisionMetricsCollector


class SupervisorAgent(A2ACapable):
    """Coordinate specialized tribunal agents and maintain decision history."""

    def __init__(self, ledger: DecisionLedger | None = None) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.sanitizer = InputSanitizer()
        self.ledger = ledger or DecisionLedger()
        self.active_delegates: Dict[str, TribunalAgent] = {}
        self.task_history: List[Dict[str, Any]] = []

        # Keywords para identificação direta de tribunais citados em tarefas
        self._tribunal_keywords: Dict[str, List[str]] = {
            "TJSP": ["tjsp", "são paulo", "sao paulo", "sp"],
            "TJMG": ["tjmg", "minas gerais", "minas", "mg"],
            "TJRS": ["tjrs", "rio grande do sul", "gaúcho", "gaucho", "rs"],
            "TJRJ": ["tjrj", "rio de janeiro", "fluminense", "rj"],
            "STF": ["stf", "supremo", "federal"],
        }

        # Regiões ajudam a identificar tribunais relacionados implicitamente
        self._region_to_tribunals: Dict[str, List[str]] = {
            "sudeste": ["TJSP", "TJMG", "TJRJ"],
            "sul": ["TJRS"],
            "federal": ["STF"],
        }

        # Consensus coordination
        self.consensus_engine = WeightedConsensusEngine()
        self.consensus_threshold = 0.7
        self.requires_consensus_keywords = [
            "crítico",
            "critico",
            "comparar",
            "comparação",
            "comparacao",
            "todos os tribunais",
            "multiplos",
            "múltiplos",
            "vários",
            "diversos",
            "colegiado",
            "consenso",
        ]

        # NOVO: Intent Classifier para routing inteligente
        self.intent_classifier = IntentClassifier(confidence_threshold=0.7)
        self.use_intelligent_routing = True

        # Vector Memory (Onda 2.2)
        self.memory = VectorMemory()
        self.memory_system = AgentMemorySystem()

        # Architect Agent for chain-of-thought reasoning
        self.architect = ArchitectAgent()

        self.logger.info(
            "SupervisorAgent inicializado com capacidades avançadas (CoT + Consenso)"
        )

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

    async def process_task_advanced(self, task_description: str) -> Dict[str, Any]:
        """Processa tarefas com Chain-of-Thought e consenso dinâmico."""

        try:
            sanitized_task = self.sanitizer.sanitize_text(task_description)

            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="ADVANCED_TASK_RECEIVED",
                metadata={
                    "original_task": task_description,
                    "sanitized_task": sanitized_task,
                    "mode": "cot_enabled",
                },
            )

            self.logger.info("Iniciando análise CoT via ArchitectAgent")
            reasoning_result = self.architect.reason_with_cot(sanitized_task)

            tribunais = self._extract_tribunals_from_reasoning(reasoning_result)
            if not tribunais:
                self.logger.warning("CoT não identificou tribunais, fallback para TJSP")
                tribunais = ["TJSP"]

            if len(tribunais) == 1:
                tribunal_code = tribunais[0]
                result = await self._delegate_to_tribunal_agent(
                    tribunal_code,
                    sanitized_task,
                )
                return {
                    "status": "success",
                    "mode": "advanced_single_tribunal",
                    "reasoning": reasoning_result,
                    "supervisor_result": result,
                    "tribunal_used": tribunal_code,
                    "timestamp": self._get_timestamp(),
                }

            self.logger.info(
                "Múltiplos tribunais detectados: %s, ativando consenso",
                tribunais,
            )

            propostas: Dict[str, Dict[str, Any]] = {}
            for tribunal in tribunais:
                proposta = await self._delegate_to_tribunal_agent(tribunal, sanitized_task)
                meta_block = proposta.get("meta") or proposta.get("metadata") or {}
                confidence = float(meta_block.get("confidence", 0.75))
                propostas[tribunal] = {"confidence": confidence, "proposal": proposta}

            consensus_result = self.consensus_engine.reach_consensus(
                propostas,
                "legal_analysis",
            )

            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="CONSENSUS_REACHED",
                metadata={
                    "consensus_strength": consensus_result.get("consensus_strength"),
                    "decision_maker": consensus_result.get("decision_maker"),
                    "tribunals_involved": tribunais,
                },
            )

            return {
                "status": "success_with_consensus",
                "mode": "advanced_multi_tribunal",
                "reasoning": reasoning_result,
                "consensus": consensus_result,
                "tribunais_envolvidos": tribunais,
                "timestamp": self._get_timestamp(),
            }

        except Exception as exc:  # pragma: no cover - defensive safeguard
            self.logger.error("Erro no processamento avançado: %s", exc, exc_info=True)
            return {
                "status": "error",
                "message": str(exc),
                "fallback": "use_simple_mode",
                "timestamp": self._get_timestamp(),
            }

    def _extract_tribunals_from_reasoning(self, reasoning: Dict[str, Any]) -> List[str]:
        """Extrai códigos de tribunais a partir do raciocínio estruturado."""

        combined_text = (
            f"{reasoning.get('recommendation', '')} "
            f"{reasoning.get('problem_analysis', '')}"
        ).upper()

        keywords = {
            "TJSP": ["TJSP", "SÃO PAULO", "SAO PAULO"],
            "TJMG": ["TJMG", "MINAS GERAIS", "MINAS"],
            "TJRS": ["TJRS", "RIO GRANDE DO SUL", "GAÚCHO", "GAUCHO"],
            "TJRJ": ["TJRJ", "RIO DE JANEIRO"],
            "STF": ["STF", "SUPREMO", "FEDERAL"],
        }

        detected: List[str] = []
        for tribunal, words in keywords.items():
            if any(word in combined_text for word in words):
                detected.append(tribunal)

        explicit = reasoning.get("identified_tribunals") or []
        for item in explicit:
            code = str(item).upper()
            if code:
                detected.append(code)

        return list(dict.fromkeys(detected))

    def _is_multi_tribunal_query(self, task: str) -> bool:
        """Detecta se a tarefa exige múltiplos tribunais ou consenso."""

        task_lower = task.lower()
        normalized = (
            task_lower.replace(",", " ")
            .replace(";", " ")
            .replace("-", " ")
        )
        words = {word for word in normalized.split() if word}

        tribunal_codes = ["tjsp", "tjmg", "tjrs", "tjrj", "stf"]
        mentioned_tribunals = sum(1 for code in tribunal_codes if code in task_lower)

        word_indicators = {
            "tribunais",
            "sudeste",
            "sul",
            "nordeste",
            "comparar",
            "comparação",
            "comparacao",
            "múltiplos",
            "multiplos",
            "diversos",
            "vários",
            "varios",
            "região",
            "regiao",
        }
        word_match = any(indicator in words for indicator in word_indicators)

        phrase_indicators = [
            "jurisprudência",
            "jurisprudencia",
            "todos os tribunais",
            "multi tribunal",
            "multi-tribunal",
        ]
        phrase_match = any(phrase in task_lower for phrase in phrase_indicators)

        consensus_keyword = any(
            keyword in task_lower for keyword in self.requires_consensus_keywords
        )

        return (
            mentioned_tribunals > 1
            or word_match
            or phrase_match
            or consensus_keyword
        )

    def _identify_relevant_tribunals(self, task: str) -> List[str]:
        """Identifica tribunais que devem ser consultados para a tarefa."""

        task_lower = task.lower()
        relevant: List[str] = []

        for region, tribunals in self._region_to_tribunals.items():
            if re.search(rf"\\b{re.escape(region)}\\b", task_lower):
                relevant.extend(tribunals)

        for tribunal, keywords in self._tribunal_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                if tribunal not in relevant:
                    relevant.append(tribunal)

        if not relevant and self._is_multi_tribunal_query(task):
            relevant = ["TJSP", "TJMG", "TJRS"]

        return relevant if relevant else [self._identify_tribunal(task)]

    def _identify_tribunal(self, task: str) -> str:
        """Retorna um único tribunal mais provável para a tarefa."""

        tribunals = self._identify_all_tribunals(task)
        if tribunals:
            return tribunals[0]
        return "TJSP"

    async def process_task(self, task_description: str) -> Dict[str, Any]:
        """
        Main entry point for task processing.
        EVOLUÇÃO STANDARD: Usa LLM-based intent classification.
        """

        start_time = time.time()
        consensus_strength_value: float | None = None

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

            tribunal_codes_raw = intent.tribunais if intent.tribunais else ["TJSP"]
            tribunal_codes = [code.upper() for code in tribunal_codes_raw]

            requires_consensus = self._is_multi_tribunal_query(
                sanitized_task
            ) or len(tribunal_codes) > 1

            if requires_consensus:
                suggested = self._identify_relevant_tribunals(sanitized_task)
                if suggested:
                    merged = tribunal_codes + suggested
                    tribunal_codes = list(dict.fromkeys(code.upper() for code in merged))
                memory_cache_hit = False
                cached_result = None

            if len(tribunal_codes) > 1:
                self.ledger.log_decision(
                    agent_type="SupervisorAgent",
                    decision_type="MULTI_TRIBUNAL_DECOMPOSITION",
                    metadata={
                        "tribunals": tribunal_codes,
                        "task_preview": sanitized_task[:100],
                    },
                )

            parallel_execution = len(tribunal_codes) > 1

            self.logger.info(
                "Processing task with %d tribunals: %s (op=%s, confidence=%.2f, recalled=%d, consensus=%s)",
                len(tribunal_codes),
                tribunal_codes,
                intent.operacao,
                intent.confidence,
                len(recalled_memories),
                requires_consensus,
            )

            consensus_payload: Dict[str, Any] | None = None
            consensus_used = False
            consultation_responses: Dict[str, Dict[str, Any]] = {}
            valid_results: List[Dict[str, Any]] = []

            if memory_cache_hit and cached_result is not None:
                elapsed_time = 0.0
                final_result = cached_result
                valid_results = [cached_result]
            elif requires_consensus:
                start_time = asyncio.get_running_loop().time()
                consultation_responses = await self._parallel_tribunal_consultation(
                    tribunal_codes, sanitized_task
                )
                valid_results = [
                    payload.get("response", {})
                    for payload in consultation_responses.values()
                    if isinstance(payload.get("response"), dict)
                ]
                final_result = self._aggregate_results(valid_results, tribunal_codes)
                elapsed_time = asyncio.get_running_loop().time() - start_time

                missing = [
                    code
                    for code in tribunal_codes
                    if code not in consultation_responses
                ]
                if missing:
                    self.logger.warning(
                        "Missing responses from tribunals during consensus: %s", missing
                    )

                consensus_payload = await self._process_with_consensus(
                    sanitized_task, tribunal_codes, consultation_responses
                )
                consensus_used = True
                consensus_strength_value = float(
                    consensus_payload.get("consensus_strength", 0.0)
                )
                consensus_details = consensus_payload.get("consensus", {}) or {}
                dissenting = consensus_details.get("dissenting_opinions") or []
                participants = (
                    len(dissenting) + 1 if consensus_details else len(tribunal_codes)
                )
                DecisionMetricsCollector.record_consensus(
                    decision_type="tribunal_operation",
                    strength=consensus_strength_value,
                    participants=participants,
                    winning_agent=consensus_details.get("decision_maker", "unknown"),
                    outcome="weak"
                    if consensus_strength_value < 0.6
                    else "strong",
                )

                if consensus_strength_value < 0.6:
                    DecisionMetricsCollector.record_hitl_request(
                        agent="SupervisorAgent",
                        status="pending",
                    )

                    self.ledger.log_decision(
                        agent_type="SupervisorAgent",
                        decision_type="HITL_REQUIRED",
                        metadata={
                            "reason": "weak_consensus",
                            "strength": consensus_strength_value,
                        },
                    )

                    return {
                        "status": "pending_human_review",
                        "message": "Consenso insuficiente. Revisão humana necessária.",
                        "consensus_strength": consensus_strength_value,
                        "consensus_details": consensus_details,
                        "tribunals_consulted": tribunal_codes,
                        "timestamp": self._get_timestamp(),
                    }
            else:
                start_time = asyncio.get_running_loop().time()
                delegated_tasks = [
                    self._delegate_to_tribunal_agent(code, sanitized_task)
                    for code in tribunal_codes
                ]
                results = await asyncio.gather(
                    *delegated_tasks, return_exceptions=True
                )

                elapsed_time = asyncio.get_running_loop().time() - start_time

                valid_results = [
                    r
                    for r in results
                    if isinstance(r, dict) and not isinstance(r, Exception)
                ]
                errors = [r for r in results if isinstance(r, Exception)]

                if errors:
                    self.logger.warning("Errors in parallel execution: %s", errors)

                final_result = self._aggregate_results(valid_results, tribunal_codes)

            if valid_results and self.memory.is_available() and not memory_cache_hit:
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

            consensus_info = (
                consensus_payload.get("consensus") if consensus_payload else None
            )
            consensus_strength = (
                consensus_payload.get("consensus_strength") if consensus_payload else None
            )
            consensus_decision = (
                consensus_payload.get("winning_proposal") if consensus_payload else None
            )
            consensus_acceptable = (
                consensus_payload.get("consensus_acceptable")
                if consensus_payload
                else None
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
                "consensus_used": consensus_used,
                "consensus": consensus_info,
                "consensus_strength": consensus_strength,
                "consensus_decision": consensus_decision,
                "consensus_acceptable": consensus_acceptable,
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
                    "consensus_used": consensus_used,
                    "consensus_strength": consensus_strength,
                },
            )

            response_payload: Dict[str, Any] = {
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
                "parallel": parallel_execution,
                "timestamp": self._get_timestamp(),
                "consensus_used": consensus_used,
                "tribunals_consulted": tribunal_codes,
            }

            if consensus_used and consensus_payload:
                consensus_details = consensus_payload.get("consensus", {})
                response_payload["consensus"] = {
                    "strength": consensus_strength,
                    "decision_maker": consensus_details.get("decision_maker"),
                    "dissenting_opinions": consensus_details.get(
                        "dissenting_opinions", []
                    ),
                    "acceptable": consensus_acceptable,
                    "decision": consensus_details.get("decision"),
                }
                response_payload["consensus_decision"] = consensus_decision

                if not consensus_acceptable:
                    response_payload["status"] = "weak_consensus"
            else:
                response_payload["consensus"] = None
                response_payload["consensus_decision"] = None

            if parallel_execution:
                response_payload["multi_tribunal"] = True
            else:
                response_payload["tribunal_used"] = tribunal_codes[0]

            total_duration = time.time() - start_time

            if consensus_used:
                DecisionMetricsCollector.record_decision(
                    agent="SupervisorAgent",
                    decision_type="consensus_task",
                    outcome="success",
                    confidence=consensus_strength_value or 0.0,
                    duration_seconds=total_duration,
                )
            else:
                DecisionMetricsCollector.record_decision(
                    agent="SupervisorAgent",
                    decision_type="standard_task",
                    outcome="success",
                    confidence=0.8,
                    duration_seconds=total_duration,
                )

            return response_payload
        except Exception as exc:  # pragma: no cover - defensive
            error_msg = f"Supervisor processing error: {exc}"
            self.logger.error(error_msg, exc_info=True)
            error_duration = time.time() - start_time
            DecisionMetricsCollector.record_decision(
                agent="SupervisorAgent",
                decision_type="error",
                outcome="failure",
                confidence=0.0,
                duration_seconds=error_duration,
            )
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
        """Retorna todos os tribunais mencionados preservando ordem de aparição."""

        task_lower = task.lower()
        matches: List[tuple[int, str]] = []

        for tribunal, keywords in self._tribunal_keywords.items():
            first_index: int | None = None
            for keyword in keywords:
                idx = task_lower.find(keyword)
                if idx != -1 and (first_index is None or idx < first_index):
                    first_index = idx

            if first_index is not None:
                matches.append((first_index, tribunal))

        matches.sort(key=lambda item: item[0])
        ordered = [tribunal for _, tribunal in matches]

        # Remover duplicados mantendo ordem resultante
        seen: set[str] = set()
        ordered_unique: List[str] = []
        for tribunal in ordered:
            if tribunal not in seen:
                seen.add(tribunal)
                ordered_unique.append(tribunal)

        return ordered_unique

    def _get_or_create_tribunal_agent(self, tribunal_code: str) -> TribunalAgent:
        """Retorna agente existente ou cria novo delegado para o tribunal."""

        if tribunal_code not in self.active_delegates:
            agent = TribunalAgent(
                tribunal_code=tribunal_code,
                ledger=self.ledger,
                memory_system=self.memory_system,
            )
            self.active_delegates[tribunal_code] = agent
            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="AGENT_CREATED",
                metadata={
                    "tribunal": tribunal_code,
                    "delegate_count": len(self.active_delegates),
                },
            )
            MetricsCollector.set_agent_active(tribunal_code, True)

        return self.active_delegates[tribunal_code]

    async def _delegate_to_tribunal_agent(
        self, tribunal_code: str, task: str
    ) -> Dict[str, Any]:
        """Delega tarefa ao agente especializado."""

        agent = self._get_or_create_tribunal_agent(tribunal_code)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, agent.execute_task, task)

    async def _parallel_tribunal_consultation(
        self, tribunals: List[str], task: str
    ) -> Dict[str, Dict[str, Any]]:
        """Consulta múltiplos tribunais em paralelo com suporte A2A."""

        if not tribunals:
            return {}

        unique_tribunals: List[str] = []
        seen = set()
        for code in tribunals:
            code_upper = code.upper()
            if code_upper not in seen:
                seen.add(code_upper)
                unique_tribunals.append(code_upper)

        self.logger.info(
            "Parallel consultation initiated for %d tribunals: %s",
            len(unique_tribunals),
            unique_tribunals,
        )

        # Ensure delegates exist and send A2A notifications
        send_tasks = []
        for tribunal_code in unique_tribunals:
            self._get_or_create_tribunal_agent(tribunal_code)
            agent_id = f"{tribunal_code.lower()}_agent"
            send_tasks.append(
                self.send_to_agent(
                    target_agent_id=agent_id,
                    message_type="consultation_request",
                    payload={
                        "query": task,
                        "consultation_id": f"consult_{len(self.task_history)}",
                        "requires_response": True,
                    },
                    priority=3,
                    requires_response=True,
                )
            )

        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)

        consultation_tasks = [
            self._delegate_to_tribunal_agent(code, task) for code in unique_tribunals
        ]
        results = await asyncio.gather(*consultation_tasks, return_exceptions=True)

        responses: Dict[str, Dict[str, Any]] = {}
        for tribunal_code, result in zip(unique_tribunals, results):
            if isinstance(result, Exception):
                self.logger.error(
                    "Error during consultation with %s: %s", tribunal_code, result
                )
                self.ledger.log_decision(
                    agent_type="SupervisorAgent",
                    decision_type="CONSULTATION_ERROR",
                    metadata={"tribunal": tribunal_code, "error": str(result)},
                )
                continue

            confidence = self._estimate_response_confidence(result)
            responses[tribunal_code] = {
                "response": result,
                "confidence": confidence,
                "agent": tribunal_code,
            }

        return responses

    def _estimate_response_confidence(self, result: Dict[str, Any]) -> float:
        """Estima confiança na resposta do tribunal consultado."""

        confidence = 0.8
        status = result.get("status", "")

        if status == "success":
            confidence += 0.1
        elif status == "simulated":
            confidence -= 0.05
        elif status == "error":
            confidence -= 0.2

        if result.get("data"):
            confidence += 0.05

        meta = result.get("meta") or result.get("metadata") or {}
        source = meta.get("source")
        if source == "real_api":
            confidence += 0.05
        elif meta.get("fallback") or source == "simulated":
            confidence -= 0.1

        return min(1.0, max(0.0, confidence))

    async def _process_with_consensus(
        self,
        task: str,
        tribunals: List[str],
        responses: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Processa respostas de múltiplos tribunais usando consenso ponderado."""

        proposals: Dict[str, Dict[str, Any]] = {}
        for tribunal_code, payload in responses.items():
            proposals[tribunal_code.lower()] = {
                "confidence": payload.get("confidence", 0.0),
                "proposal": payload.get("response", {}),
            }

        consensus_result = self.consensus_engine.reach_consensus(
            proposals, "jurisprudence_analysis"
        )

        consensus_strength = float(consensus_result.get("consensus_strength", 0.0))
        consensus_acceptable = consensus_strength >= self.consensus_threshold

        self.ledger.log_decision(
            agent_type="SupervisorAgent",
            decision_type="CONSENSUS_REACHED"
            if consensus_acceptable
            else "CONSENSUS_WEAK",
            metadata={
                "tribunals_consulted": tribunals,
                "consensus_strength": consensus_strength,
                "decision_maker": consensus_result.get("decision_maker"),
                "dissenting": consensus_result.get("dissenting_opinions", []),
                "threshold": self.consensus_threshold,
            },
        )

        winning_proposal: Dict[str, Any] | None = None
        decision_block = consensus_result.get("decision")
        if isinstance(decision_block, dict):
            winning_proposal = decision_block.get("proposal")

        if not winning_proposal and responses:
            # fallback para a resposta de maior confiança
            sorted_responses = sorted(
                responses.values(), key=lambda item: item.get("confidence", 0.0), reverse=True
            )
            if sorted_responses:
                winning_proposal = sorted_responses[0].get("response")

        return {
            "consensus": consensus_result,
            "consensus_strength": consensus_strength,
            "consensus_acceptable": consensus_acceptable,
            "winning_proposal": winning_proposal,
        }

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
            "multi_tribunal_tasks": sum(
                1 for t in self.task_history if len(t.get("tribunals", [])) > 1
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

