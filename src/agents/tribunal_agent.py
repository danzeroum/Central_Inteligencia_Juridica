from __future__ import annotations

import logging
import random
import re
import time
from typing import Any, Dict, Optional

from src.memory.agent_memory import AgentMemorySystem
from src.protocols.a2a_channel import A2AMessage
from src.protocols.a2a_mixin import A2ACapable, create_status_handler
from src.tools.tribunal_api_adapter import TribunalAPIAdapter
from src.utils.input_sanitizer import InputSanitizer
from src.utils.ledger import DecisionLedger
from src.utils.metrics_collector import MetricsCollector


class TribunalAgent(A2ACapable):
    """Agente especializado que consulta tribunais reais com fallback."""

    _PROCESS_NUMBER_RE = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")

    def __init__(
        self,
        tribunal_code: str,
        ledger: DecisionLedger | None = None,
        memory_system: AgentMemorySystem | None = None,
    ) -> None:
        self.tribunal_code = tribunal_code
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.sanitizer = InputSanitizer()
        self.ledger = ledger or DecisionLedger()
        self.memory = memory_system or AgentMemorySystem()
        self.api_adapter = TribunalAPIAdapter(tribunal_code)

        MetricsCollector.set_agent_active(self.tribunal_code, True)

        self._register_a2a_handlers()

    def execute_task(self, task: str) -> Dict[str, Any]:
        """Executa tarefa delegada pelo supervisor."""

        start = time.perf_counter()
        sanitized_task = self.sanitizer.sanitize_text(task)
        operation = self._determine_operation(sanitized_task)

        self.ledger.log_decision(
            agent_type=f"TribunalAgent[{self.tribunal_code}]",
            decision_type="TASK_RECEIVED",
            metadata={"task": sanitized_task, "operation": operation},
        )

        try:
            if operation == "status":
                result = self._check_tribunal_status()
            elif operation == "process_query":
                result = self._process_query(sanitized_task)
            elif operation == "jurisprudencia":
                result = self._jurisprudencia_search(sanitized_task)
            else:
                result = self._simulate_generic_response(sanitized_task)
        except Exception as exc:  # pragma: no cover - defensive safeguard
            self.logger.error("Error executing task: %s", exc, exc_info=True)
            result = self._error_response(str(exc))

        latency = time.perf_counter() - start
        result.setdefault("tribunal", self.tribunal_code)
        result.setdefault("operation", operation)
        result["task"] = task
        result["latency"] = latency

        self.ledger.log_decision(
            agent_type=f"TribunalAgent[{self.tribunal_code}]",
            decision_type="TASK_EXECUTED",
            metadata={"latency": latency, "operation": operation},
        )
        return result

    def _register_a2a_handlers(self) -> None:
        """Configura handlers padrão para mensagens A2A."""
        self.register_handler("status_request", create_status_handler())
        self.register_handler("data_request", self._handle_data_request)
        self.register_handler("tribunal_info", self._handle_tribunal_info)

    async def _handle_data_request(self, message: A2AMessage) -> Dict[str, Any]:
        """Responde solicitações de dados de outros agentes."""
        query = message.payload.get("query", "")
        process_number = message.payload.get("process_number")

        self.logger.info(
            "%s recebeu solicitação de dados de %s",
            self.tribunal_code,
            message.sender_id,
        )

        try:
            if process_number:
                data = self.api_adapter.get_processo(process_number)
                return {
                    "success": True,
                    "process_number": process_number,
                    "data": data,
                }

            if query:
                sanitized = self.sanitizer.sanitize_text(query)
                operation = self._determine_operation(sanitized)

                if operation == "status":
                    return {"success": True, "data": self._check_tribunal_status()}
                if operation == "process_query":
                    return {"success": True, "data": self._process_query(sanitized)}

                return {
                    "success": True,
                    "data": self._simulate_generic_response(sanitized),
                }
        except Exception as exc:  # pragma: no cover - defensive safeguard
            self.logger.error(
                "Erro ao processar solicitação A2A: %s", exc, exc_info=True
            )
            return {"success": False, "error": str(exc)}

        return {"success": False, "error": "Nenhum parâmetro de consulta fornecido"}

    async def _handle_tribunal_info(self, message: A2AMessage) -> Dict[str, Any]:
        """Retorna informações gerais do tribunal."""
        return {
            "tribunal": self.tribunal_code,
            "supported_operations": ["status", "process_query", "generic"],
            "circuit_breaker": self.api_adapter.get_circuit_breaker_state(),
        }

    async def collaborate_with_tribunal(
        self,
        target_tribunal: str,
        query: str,
        process_number: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Solicita informações a outro agente de tribunal via A2A."""
        target_agent_id = f"{target_tribunal.lower()}_agent"

        self.logger.info(
            "%s solicitando dados de %s",
            self.tribunal_code,
            target_tribunal,
        )

        return await self.request_from_agent(
            target_agent_id=target_agent_id,
            message_type="data_request",
            payload={
                "query": query,
                "process_number": process_number,
                "requesting_tribunal": self.tribunal_code,
            },
            timeout=30.0,
        )

    _JURIS_KEYWORDS = frozenset(
        [
            "jurisprudência",
            "jurisprudencia",
            "decisão",
            "decisões",
            "decisoes",
            "acórdão",
            "acordao",
            "acórdãos",
            "acordaos",
            "precedente",
            "precedentes",
            "comparar",
            "comparação",
            "comparacao",
            "entendimento",
            "julgamento",
            "julgamentos",
            "súmula",
            "sumula",
        ]
    )

    def _determine_operation(self, task: str) -> str:
        lower = task.lower()
        # Process number takes priority: "status do processo X" is a process query
        if (
            "processo" in lower
            or "processar" in lower
            or self._PROCESS_NUMBER_RE.search(lower)
        ):
            return "process_query"
        if "status" in lower or "disponív" in lower or "disponibilidade" in lower or "available" in lower:
            return "status"
        if any(kw in lower for kw in self._JURIS_KEYWORDS):
            return "jurisprudencia"
        return "generic"

    def _check_tribunal_status(self) -> Dict[str, Any]:
        status_payload = self.api_adapter.get_status()
        metadata = status_payload.pop("_metadata", {})
        source = metadata.get("source", "unknown")

        if source == "simulated":
            self.logger.warning("Using MOCK data for %s (fallback)", self.tribunal_code)
        else:
            self.logger.info("Using REAL API data for %s", self.tribunal_code)

        return {
            "tribunal": self.tribunal_code,
            "operation": "status",
            "status": "success",
            "data": status_payload,
            "metadata": metadata,
        }

    def _process_query(self, sanitized_task: str) -> Dict[str, Any]:
        process_number = self._extract_process_number(sanitized_task)
        if not process_number:
            process_number = self._generate_process_number()

        rag_query = (
            f"jurisprudência {self.tribunal_code} processo similar a {sanitized_task}"
        )
        try:
            rag_context = self.memory.recall_similar(query=rag_query, k=3)
            retrieved = rag_context.get("documents", [[]])[0]
            self.logger.info(
                "RAG recuperou %d documentos para %s",
                len(retrieved) if isinstance(retrieved, list) else 0,
                process_number,
            )
        except Exception as exc:  # pragma: no cover - defensive safeguard
            self.logger.warning("RAG falhou, continuando sem contexto: %s", exc)
            rag_context = {
                "documents": [[]],
                "metadatas": [[]],
                "note": "rag_unavailable",
            }

        try:
            processo_payload = self.api_adapter.get_processo(process_number)
        except Exception as exc:  # pragma: no cover - defensive safeguard
            self.logger.error(
                "Erro ao consultar processo real %s: %s",
                process_number,
                exc,
                exc_info=True,
            )
            fallback = self._simulate_generic_response(sanitized_task)
            fallback.setdefault("data", {})
            fallback["data"]["rag_context"] = rag_context
            fallback["process_number"] = process_number
            fallback.setdefault("metadata", {})
            fallback["metadata"].update(
                {"source": "simulated", "rag_enabled": True, "fallback": True}
            )
            return fallback

        metadata = processo_payload.pop("_metadata", {})
        source = metadata.get("source", "unknown")

        if source == "simulated":
            self.logger.warning(
                "Using MOCK data for processo %s (fallback)", process_number
            )
        else:
            self.logger.info("Using REAL API data for processo %s", process_number)

        processo_payload["rag_context"] = rag_context

        metadata.update({"rag_enabled": True})

        return {
            "tribunal": self.tribunal_code,
            "operation": "process_query",
            "status": "success",
            "process_number": process_number,
            "data": processo_payload,
            "metadata": metadata,
        }

    def _jurisprudencia_search(self, task: str) -> Dict[str, Any]:
        """Busca jurisprudência por tema no DataJud para este tribunal."""
        # Extrai o tema: remove menções ao tribunal para não poluir a query
        tema = re.sub(
            r"\b(comparar|jurisprudência|jurisprudencia|decisões|decisao|acórdão|acordao"
            r"|no\s+\w+|do\s+\w+|no\s+stf|no\s+stj|no\s+tj\w+)\b",
            " ",
            task,
            flags=re.IGNORECASE,
        ).strip()
        tema = re.sub(r"\s+", " ", tema).strip() or task

        resultado = self.api_adapter.search_tema_sync(tema, size=5)

        if resultado is None:
            return {
                "tribunal": self.tribunal_code,
                "operation": "jurisprudencia",
                "status": "simulated",
                "message": "DataJud indisponível ou sem chave configurada.",
                "tema": tema,
                "processos": [],
            }

        metadata = resultado.pop("_metadata", {})
        return {
            "tribunal": self.tribunal_code,
            "operation": "jurisprudencia",
            "status": "success",
            "tema": tema,
            "total": resultado.get("total", 0),
            "processos": resultado.get("processos", []),
            "metadata": metadata,
        }

    def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        return {
            "tribunal": self.tribunal_code,
            "circuit_breaker": self.api_adapter.get_circuit_breaker_state(),
        }

    def _simulate_generic_response(self, task: str) -> Dict[str, Any]:
        self.logger.info(
            "Falling back to generic simulation for %s with task '%s'",
            self.tribunal_code,
            task,
        )
        return {
            "tribunal": self.tribunal_code,
            "operation": "generic",
            "status": "simulated",
            "message": f"Nenhuma ação específica reconhecida para: {task}",
        }

    def _extract_process_number(self, task: str) -> str | None:
        match = self._PROCESS_NUMBER_RE.search(task)
        if match:
            return match.group(0)

        digits = re.sub(r"\D", "", task)
        if len(digits) >= 7:
            return digits
        return None

    def _generate_process_number(self) -> str:
        random_part = random.randint(1000000, 9999999)
        return f"{random_part}-00.2024.8.26.0100"

    def _error_response(self, error_message: str) -> Dict[str, Any]:
        return {
            "tribunal": self.tribunal_code,
            "operation": "error",
            "status": "error",
            "message": f"Erro ao processar tarefa: {error_message}",
        }
