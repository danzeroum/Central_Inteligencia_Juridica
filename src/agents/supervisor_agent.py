"""Supervisor Agent - Orchestrator for multi-agent collaboration system."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from src.agents.tribunal_agent import TribunalAgent
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

    def process_task(self, task_description: str) -> Dict[str, Any]:
        """Main entry point for task processing."""

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

            tribunal_code = self._identify_tribunal(sanitized_task)
            result = self._delegate_to_tribunal_agent(tribunal_code, sanitized_task)

            task_record = {
                "task": sanitized_task,
                "tribunal": tribunal_code,
                "result": result,
                "timestamp": self._get_timestamp(),
            }
            self.task_history.append(task_record)

            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="TASK_COMPLETED",
                metadata={
                    "tribunal": tribunal_code,
                    "result_status": result.get("status", "unknown"),
                    "task_history_count": len(self.task_history),
                },
            )

            return {
                "status": "success",
                "supervisor_result": result,
                "tribunal_used": tribunal_code,
                "task_id": f"task_{len(self.task_history):04d}",
                "timestamp": self._get_timestamp(),
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            error_msg = f"Supervisor processing error: {exc}"
            self.logger.error(error_msg)
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

    def _identify_tribunal(self, task: str) -> str:
        """Identify which tribunal specialization is needed."""

        task_lower = task.lower()
        tribunal_keywords: Dict[str, List[str]] = {
            "TJSP": ["tjsp", "são paulo", "sao paulo", "sp"],
            "TJMG": ["tjmg", "minas gerais", "minas", "mg"],
            "TJRS": ["tjrs", "rio grande do sul", "gaúcho", "gaucho", "rs"],
            "TJRJ": ["tjrj", "rio de janeiro", "fluminense", "rj"],
            "STF": ["stf", "supremo", "federal"],
        }

        for tribunal, keywords in tribunal_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                return tribunal

        return "TJSP"

    def _delegate_to_tribunal_agent(self, tribunal_code: str, task: str) -> Dict[str, Any]:
        """Delegate task to appropriate tribunal agent."""

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
        return agent.execute_task(task)

    def get_agent_stats(self) -> Dict[str, Any]:
        """Return statistics about active agents."""

        stats = {
            "total_delegates": len(self.active_delegates),
            "active_tribunals": list(self.active_delegates.keys()),
            "total_tasks_processed": len(self.task_history),
            "latest_tasks": self.task_history[-5:] if self.task_history else [],
        }
        MetricsCollector.set_total_agents({tribunal: 1 for tribunal in self.active_delegates})
        return stats

    def _get_timestamp(self) -> str:
        return datetime.now().isoformat()


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    logging.basicConfig(level=logging.INFO)
    supervisor = SupervisorAgent()
    for task in [
        "Verificar status do tribunal TJSP",
        "Consultar processo no TJMG número 123456",
        "Status do sistema do TJRS",
        "Preciso de informações sobre o STF",
    ]:
        print(f"\n🔍 Processando: {task}")
        outcome = supervisor.process_task(task)
        print(f"✅ Resultado: {outcome['status']}")
        print(f"🏛️  Tribunal: {outcome['tribunal_used']}")
        print(f"📊 Dados: {outcome.get('supervisor_result', {})}")

    print(f"\n📈 Estatísticas: {supervisor.get_agent_stats()}")
