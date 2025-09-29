"""Supervisor Agent - Orchestrator for multi-agent collaboration system."""

from __future__ import annotations

import asyncio
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

    async def process_task(self, task_description: str) -> Dict[str, Any]:
        """
        Main entry point for task processing.
        EVOLUÇÃO STANDARD: Suporta execução paralela para múltiplos tribunais.
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

            # NOVO: Identifica TODOS os tribunais mencionados
            tribunal_codes = self._identify_all_tribunals(sanitized_task)

            if not tribunal_codes:
                tribunal_codes.append("TJSP")  # Fallback padrão

            self.logger.info(
                "Processing task with %d tribunals: %s",
                len(tribunal_codes),
                tribunal_codes,
            )

            # PARALELIZAÇÃO: Executa todas as delegações simultaneamente
            start_time = asyncio.get_event_loop().time()

            delegated_tasks = [
                self._delegate_to_tribunal_agent(code, sanitized_task)
                for code in tribunal_codes
            ]
            results = await asyncio.gather(*delegated_tasks, return_exceptions=True)

            elapsed_time = asyncio.get_event_loop().time() - start_time

            # Filtra erros e agrega resultados válidos
            valid_results = [
                r for r in results if isinstance(r, dict) and not isinstance(r, Exception)
            ]
            errors = [r for r in results if isinstance(r, Exception)]

            if errors:
                self.logger.warning("Errors in parallel execution: %s", errors)

            final_result = self._aggregate_results(valid_results, tribunal_codes)

            task_record = {
                "task": sanitized_task,
                "tribunals": tribunal_codes,
                "result": final_result,
                "execution_time": elapsed_time,
                "parallel": len(tribunal_codes) > 1,
                "timestamp": self._get_timestamp(),
            }
            self.task_history.append(task_record)

            self.ledger.log_decision(
                agent_type="SupervisorAgent",
                decision_type="TASK_COMPLETED",
                metadata={
                    "tribunals": tribunal_codes,
                    "result_status": final_result.get("status", "unknown"),
                    "execution_time": elapsed_time,
                    "parallel_execution": len(tribunal_codes) > 1,
                },
            )

            return {
                "status": "success",
                "supervisor_result": final_result,
                "tribunals_used": tribunal_codes,
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

        # Remove duplicatas mantendo ordem
        return list(dict.fromkeys(found_tribunals))

    async def _delegate_to_tribunal_agent(
        self, tribunal_code: str, task: str
    ) -> Dict[str, Any]:
        """
        Delega tarefa ao agente especializado.
        EVOLUÇÃO STANDARD: Agora assíncrono para suportar paralelização.
        """
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

        # Execute em thread separada para não bloquear event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, agent.execute_task, task)

    def _aggregate_results(
        self, results: List[Dict[str, Any]], tribunal_codes: List[str]
    ) -> Dict[str, Any]:
        """
        NOVO MÉTODO: Agrega múltiplos resultados em resposta única estruturada.
        """
        if not results:
            return {
                "status": "no_results",
                "message": "Nenhum resultado válido obtido",
                "tribunals_queried": tribunal_codes,
            }

        if len(results) == 1:
            # Backward compatibility: retorna direto se for apenas um tribunal
            return results[0]

        # Para múltiplos resultados, estrutura como dict de tribunais
        aggregated = {
            "status": "multiple_results",
            "count": len(results),
            "tribunals": {},
        }

        for result in results:
            tribunal = result.get("tribunal", "unknown")
            aggregated["tribunals"][tribunal] = result

        return aggregated

    def get_agent_stats(self) -> Dict[str, Any]:
        """Return statistics about active agents."""
        stats = {
            "total_delegates": len(self.active_delegates),
            "active_tribunals": list(self.active_delegates.keys()),
            "total_tasks_processed": len(self.task_history),
            "parallel_tasks_count": sum(
                1 for t in self.task_history if t.get("parallel", False)
            ),
            "latest_tasks": self.task_history[-5:] if self.task_history else [],
        }
        MetricsCollector.set_total_agents(
            {tribunal: 1 for tribunal in self.active_delegates}
        )
        return stats

    def _get_timestamp(self) -> str:
        return datetime.now().isoformat()


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    async def demo():
        supervisor = SupervisorAgent()

        # Teste single-tribunal (backward compatibility)
        result1 = await supervisor.process_task("Status do TJSP")
        print(f"✅ Single: {result1['tribunals_used']}")

        # Teste multi-tribunal (nova funcionalidade)
        result2 = await supervisor.process_task("Status do TJSP e TJMG")
        print(f"✅ Parallel: {result2['tribunals_used']}")
        print(f"⚡ Time: {result2['execution_time']:.3f}s")

    asyncio.run(demo())
