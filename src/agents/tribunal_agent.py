from __future__ import annotations

import logging
import random
import re
import time
from typing import Any, Dict

from src.tools.tribunal_api_adapter import TribunalAPIAdapter
from src.utils.input_sanitizer import InputSanitizer
from src.utils.ledger import DecisionLedger
from src.utils.metrics_collector import MetricsCollector


class TribunalAgent:
    """Agente especializado que consulta tribunais reais com fallback."""

    _PROCESS_NUMBER_RE = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")

    def __init__(self, tribunal_code: str, ledger: DecisionLedger | None = None) -> None:
        self.tribunal_code = tribunal_code
        self.logger = logging.getLogger(__name__)
        self.sanitizer = InputSanitizer()
        self.ledger = ledger or DecisionLedger()
        self.api_adapter = TribunalAPIAdapter(tribunal_code)

        MetricsCollector.set_agent_active(self.tribunal_code, True)

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

        processo_payload = self.api_adapter.get_processo(process_number)
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
