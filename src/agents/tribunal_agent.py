<<<<<<< HEAD
"""Tribunal Agent - Specialized agent for tribunal-specific operations."""

from __future__ import annotations

import copy
import hashlib
=======
from __future__ import annotations

>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
import logging
import random
import re
import time
<<<<<<< HEAD
from datetime import datetime
from typing import Any, Dict, List

from src.agents.tribunal_api_client import TribunalAPIClient
from src.utils.cache_manager import get_cache_manager
from src.utils.input_sanitizer import InputSanitizer
from src.utils.ledger import DecisionLedger
from src.utils.metrics_collector import MetricsCollector


class TribunalAgent:
    """Handle tribunal-specific tasks delegated by the supervisor."""

    def __init__(self, tribunal_code: str, ledger: DecisionLedger | None = None) -> None:
        self.tribunal_code = tribunal_code
        self.logger = logging.getLogger(__name__)
        self.sanitizer = InputSanitizer()
        self.ledger = ledger or DecisionLedger()
        self.task_count = 0

        self.config = self._load_tribunal_config()
        self.capabilities = self._define_capabilities()
        self.cache = get_cache_manager()
        self.api_client = TribunalAPIClient(tribunal_code)

        MetricsCollector.set_agent_active(self.tribunal_code, True)

    def execute_task(self, task_description: str) -> Dict[str, Any]:
        """Execute tribunal-specific task."""

        self.task_count += 1
        task_id = f"{self.tribunal_code}_task_{self.task_count:04d}"

        start_time = time.perf_counter()
        operation_for_metrics = "unknown"
        success_for_metrics = False

        try:
            sanitized_task = self.sanitizer.sanitize_text(task_description)

            self.ledger.log_decision(
                agent_type=f"TribunalAgent_{self.tribunal_code}",
                decision_type="TASK_EXECUTION_START",
                metadata={
                    "task_id": task_id,
                    "sanitized_task": sanitized_task,
                    "tribunal": self.tribunal_code,
                },
            )

            self.logger.info(
                "Executing task %s for %s: %s",
                task_id,
                self.tribunal_code,
                sanitized_task,
            )

            result = self._route_task(sanitized_task, task_id)
            operation_for_metrics = result.get("operation", "unknown")
            success_for_metrics = result.get("status") not in {"error"}

            self.ledger.log_decision(
                agent_type=f"TribunalAgent_{self.tribunal_code}",
                decision_type="TASK_EXECUTION_COMPLETE",
                metadata={
                    "task_id": task_id,
                    "operation": result.get("operation", "unknown"),
                    "result_status": result.get("status", "unknown"),
                },
            )

            return result
        except Exception as exc:  # pragma: no cover - defensive logging
            error_msg = f"TribunalAgent error for {self.tribunal_code}: {exc}"
            self.logger.error(error_msg)
            self.ledger.log_decision(
                agent_type=f"TribunalAgent_{self.tribunal_code}",
                decision_type="TASK_EXECUTION_ERROR",
                metadata={"task_id": task_id, "error": error_msg},
            )
            operation_for_metrics = "error"
            success_for_metrics = False
            return {
                "status": "error",
                "message": error_msg,
                "tribunal": self.tribunal_code,
                "timestamp": self._get_timestamp(),
            }
        finally:
            duration = time.perf_counter() - start_time
            MetricsCollector.record_task(self.tribunal_code, operation_for_metrics, duration, success_for_metrics)

    def _route_task(self, task: str, task_id: str) -> Dict[str, Any]:
        task_lower = task.lower()

        if any(word in task_lower for word in ["status", "sistema", "operacional", "funcionamento"]):
            return self._check_tribunal_status(task_id)
        if any(word in task_lower for word in ["processo", "consulta", "número", "numero", "protocolo"]):
            return self._process_query(task, task_id)
        if any(word in task_lower for word in ["andamento", "movimentação", "movimentacao"]):
            return self._process_movements(task_id)
        return self._generic_tribunal_response(task_id)

    def _check_tribunal_status(self, task_id: str | None = None) -> Dict[str, Any]:
        operation = "status_check"
        cached = self._maybe_return_cached(operation, {}, task_id)
        if cached:
            return cached

        status_map: Dict[str, Dict[str, Any]] = {
            "TJSP": {
                "status": "operacional",
                "ultima_atualizacao": "2024-01-15T10:00:00",
                "mensagem": "Sistema funcionando normalmente",
                "tempo_resposta": "45ms",
                "servicos_ativos": 95,
            },
            "TJMG": {
                "status": "instabilidade",
                "ultima_atualizacao": "2024-01-15T09:30:00",
                "mensagem": "Manutenção programada em andamento",
                "tempo_resposta": "120ms",
                "servicos_ativos": 78,
            },
            "TJRS": {
                "status": "operacional",
                "ultima_atualizacao": "2024-01-15T08:45:00",
                "mensagem": "Funcionamento normal",
                "tempo_resposta": "32ms",
                "servicos_ativos": 92,
            },
            "TJRJ": {
                "status": "degradado",
                "ultima_atualizacao": "2024-01-15T07:15:00",
                "mensagem": "Problemas intermitentes na consulta",
                "tempo_resposta": "210ms",
                "servicos_ativos": 65,
            },
            "STF": {
                "status": "operacional",
                "ultima_atualizacao": "2024-01-15T11:20:00",
                "mensagem": "Sistema estável",
                "tempo_resposta": "28ms",
                "servicos_ativos": 98,
            },
        }

        default_status = {
            "status": "desconhecido",
            "mensagem": "Tribunal não configurado",
            "servicos_ativos": 0,
        }

        api_response = self.api_client.get_real_status()
        if api_response and not api_response.get("error"):
            result = self._build_response(
                operation=operation,
                data=api_response,
                status="success",
                task_id=task_id,
                meta={"source": "real_api"},
            )
            self._store_in_cache(operation, {}, result)
            return result

        if api_response.get("error"):
            MetricsCollector.record_api_error(self.tribunal_code, "api_error")

        fallback_meta = {"source": "simulated", "fallback": True}
        if api_response.get("error"):
            fallback_meta["error"] = api_response["error"]

        result = self._build_response(
            operation=operation,
            data=status_map.get(self.tribunal_code, default_status),
            status="success",
            task_id=task_id,
            meta=fallback_meta,
        )
        self._store_in_cache(operation, {}, result)
        return result

    def _process_query(self, task: str, task_id: str | None = None) -> Dict[str, Any]:
        operation = "process_query"
        process_number = self._extract_process_number(task or "") or self._generate_process_number()
        cache_params = {"process_number": process_number}

        cached = self._maybe_return_cached(operation, cache_params, task_id)
        if cached:
            return cached

        api_response = self.api_client.query_real_process(process_number)
        if api_response and not api_response.get("error"):
            result = self._build_response(
                operation=operation,
                data=api_response,
                status="success",
                task_id=task_id,
                meta={"source": "real_api"},
            )
            self._store_in_cache(operation, cache_params, result)
            return result

        if api_response.get("error"):
            MetricsCollector.record_api_error(self.tribunal_code, "api_error")

        fallback = self._simulate_process_query(
            task=task,
            task_id=task_id,
            process_number=process_number,
        )
        if not isinstance(fallback, dict):
            return fallback

        fallback_copy = copy.deepcopy(fallback)
        if {"tribunal", "operation"}.issubset(fallback_copy):
            meta = copy.deepcopy(fallback_copy.get("meta", {}))
            meta.update({"source": "simulated", "fallback": True})
            if api_response.get("error"):
                meta["error"] = api_response["error"]
            fallback_copy["meta"] = meta
            fallback_copy["status"] = fallback_copy.get("status", "success")
            self._store_in_cache(operation, cache_params, fallback_copy)
            return fallback_copy

        return fallback

    def _process_movements(self, task_id: str | None = None) -> Dict[str, Any]:
        operation = "process_movements"
        cached = self._maybe_return_cached(operation, {}, task_id)
        if cached:
            return cached

        result = self._simulate_process_movements(task_id)
        self._store_in_cache(operation, {}, result)
        return result

    def _simulate_process_query(
        self,
        task: str | None = None,
        task_id: str | None = None,
        process_number: str | None = None,
    ) -> Dict[str, Any]:
        process_id = process_number or self._extract_process_number(task or "") or self._generate_process_number()

        data = {
            "numero_processo": process_id,
            "situacao": "Em andamento",
            "classe_processual": "Procedimento Ordinário",
            "assunto": "Direito Civil",
            "ultima_movimentacao": "2024-01-15 10:30:00",
            "orgao_julgador": "1ª Vara Cível",
            "valor_causa": "R$ 45.000,00",
        }

        return self._build_response(
            operation="process_query",
            data=data,
            status="success",
            task_id=task_id,
            meta={"source": "simulated"},
        )

    def _simulate_process_movements(self, task_id: str | None = None) -> Dict[str, Any]:
        movements = [
            {"data": "2024-01-15", "descricao": "Distribuição por sorteio"},
            {"data": "2024-01-10", "descricao": "Juntada de petição inicial"},
            {"data": "2024-01-05", "descricao": "Autuação do processo"},
        ]

        data = {
            "movimentacoes": movements,
            "total_movimentacoes": len(movements),
        }

        return self._build_response(
            operation="process_movements",
            data=data,
            status="success",
            task_id=task_id,
            meta={"source": "simulated"},
        )

    def _generic_tribunal_response(self, task_id: str | None = None) -> Dict[str, Any]:
        operation = "generic_response"
        cached = self._maybe_return_cached(operation, {}, task_id)
        if cached:
            return cached

        result = self._build_response(
            operation=operation,
            data={
                "message": f"Operação genérica para {self.tribunal_code}",
                "capacidades": self.capabilities,
                "config": self.config,
            },
            status="success",
            task_id=task_id,
            meta={"source": "simulated"},
        )
        self._store_in_cache(operation, {}, result)
        return result

    def _maybe_return_cached(
        self,
        operation: str,
        params: Dict[str, Any],
        task_id: str | None = None,
    ) -> Dict[str, Any] | None:
        cached = self.cache.get_cached(self.tribunal_code, operation, params)
        if not cached:
            return None

        cached_result = copy.deepcopy(cached)
        cached_result["task_id"] = task_id or cached_result.get("task_id", self._generate_task_id_stub())
        cached_result["timestamp"] = self._get_timestamp()
        meta = copy.deepcopy(cached_result.get("meta", {}))
        meta["cache"] = "hit"
        cached_result["meta"] = meta
        MetricsCollector.record_cache_hit(self.tribunal_code, operation)
        return cached_result

    def _store_in_cache(self, operation: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        payload = copy.deepcopy(result)
        if "meta" in payload:
            meta = dict(payload["meta"])
            meta.pop("cache", None)
            payload["meta"] = meta
        self.cache.set_cache(self.tribunal_code, operation, params, payload)

    def _build_response(
        self,
        *,
        operation: str,
        data: Dict[str, Any],
        status: str,
        task_id: str | None,
        meta: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        response = {
            "tribunal": self.tribunal_code,
            "operation": operation,
            "task_id": task_id or self._generate_task_id_stub(),
            "data": data,
            "timestamp": self._get_timestamp(),
            "status": status,
        }
        if meta:
            response["meta"] = meta
        return response

    def _extract_process_number(self, task: str) -> str | None:
        patterns = [
            r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}",
            r"\d{4}\.\d{3}\.\d{6}-\d",
            r"processo[\s:]*([\d\.-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, task, flags=re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _generate_process_number(self) -> str:
        base = f"{self.tribunal_code}{random.randint(1000000, 9999999)}"
        hash_int = int(hashlib.md5(base.encode()).hexdigest()[:8], 16)

        if self.tribunal_code == "STF":
            return f"STF-{hash_int % 100000:05d}"
        formatted = f"{hash_int % 10000000:07d}-{hash_int % 100:02d}.2024.8.26.{hash_int % 10000:04d}"
        return f"{self.tribunal_code}-{formatted}"

    def _load_tribunal_config(self) -> Dict[str, Any]:
        configs: Dict[str, Dict[str, Any]] = {
            "TJSP": {
                "api_endpoint": "https://api.tjsp.jus.br",
                "timeout": 30,
                "versao_api": "v2.1",
                "limite_consultas": 1000,
            },
            "TJMG": {
                "api_endpoint": "https://api.tjmg.jus.br",
                "timeout": 25,
                "versao_api": "v1.8",
                "limite_consultas": 800,
            },
            "TJRS": {
                "api_endpoint": "https://api.tjrs.jus.br",
                "timeout": 35,
                "versao_api": "v3.0",
                "limite_consultas": 1200,
            },
            "TJRJ": {
                "api_endpoint": "https://api.tjrj.jus.br",
                "timeout": 40,
                "versao_api": "v1.5",
                "limite_consultas": 600,
            },
            "STF": {
                "api_endpoint": "https://api.stf.jus.br",
                "timeout": 20,
                "versao_api": "v4.2",
                "limite_consultas": 2000,
            },
        }
        return configs.get(self.tribunal_code, {})

    def _define_capabilities(self) -> List[str]:
        base_capabilities = ["status_check", "process_query", "process_movements"]
        if self.tribunal_code == "STF":
            base_capabilities.extend(["constitutional_review", "federal_laws"])
        else:
            base_capabilities.extend(["state_laws", "local_jurisdiction"])
        return base_capabilities

    def _generate_task_id_stub(self) -> str:
        return f"{self.tribunal_code}_task_stub"

    def _get_timestamp(self) -> str:
        return datetime.now().isoformat()


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    agent = TribunalAgent("TJSP")
    print(agent.execute_task("Verificar status do sistema"))
=======
from typing import Any, Dict, Optional

from src.protocols.a2a_channel import A2AMessage
from src.protocols.a2a_mixin import A2ACapable, create_status_handler
from src.tools.tribunal_api_adapter import TribunalAPIAdapter
from src.utils.input_sanitizer import InputSanitizer
from src.utils.ledger import DecisionLedger
from src.utils.metrics_collector import MetricsCollector
from src.memory.agent_memory import AgentMemorySystem


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

                return {"success": True, "data": self._simulate_generic_response(sanitized)}
        except Exception as exc:  # pragma: no cover - defensive safeguard
            self.logger.error("Erro ao processar solicitação A2A: %s", exc, exc_info=True)
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

    def _determine_operation(self, task: str) -> str:
        lower = task.lower()
        if "status" in lower or "disponibilidade" in lower:
            return "status"
        if "processo" in lower or self._PROCESS_NUMBER_RE.search(lower):
            return "process_query"
        return "generic"

    def _check_tribunal_status(self) -> Dict[str, Any]:
        status_payload = self.api_adapter.get_status()
        metadata = status_payload.pop("_metadata", {})
        source = metadata.get("source", "unknown")

        if source == "simulated":
            self.logger.warning(
                "Using MOCK data for %s (fallback)", self.tribunal_code
            )
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
            rag_context = {"documents": [[]], "metadatas": [[]], "note": "rag_unavailable"}

        try:
            processo_payload = self.api_adapter.get_processo(process_number)
        except Exception as exc:  # pragma: no cover - defensive safeguard
            self.logger.error(
                "Erro ao consultar processo real %s: %s", process_number, exc, exc_info=True
            )
            fallback = self._simulate_generic_response(sanitized_task)
            fallback.setdefault("data", {})
            fallback["data"]["rag_context"] = rag_context
            fallback["process_number"] = process_number
            fallback.setdefault("metadata", {})
            fallback["metadata"].update({"source": "simulated", "rag_enabled": True, "fallback": True})
            return fallback

        metadata = processo_payload.pop("_metadata", {})
        source = metadata.get("source", "unknown")

        if source == "simulated":
            self.logger.warning(
                "Using MOCK data for processo %s (fallback)", process_number
            )
        else:
            self.logger.info(
                "Using REAL API data for processo %s", process_number
            )

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
>>>>>>> origin/codex/implementar-central-de-inteligencia-juridica
