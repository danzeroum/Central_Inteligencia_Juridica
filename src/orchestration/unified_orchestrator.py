"""Unified orchestrator that coordinates advanced agent workflows."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.agents.supervisor_agent import SupervisorAgent


class UnifiedOrchestrator:
    """High-level orchestrator activating the advanced supervisor pipeline."""

    def __init__(self, supervisor_agent: Optional[SupervisorAgent] = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.supervisor = supervisor_agent or SupervisorAgent()

    async def execute_complex_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a complex legal task leveraging CoT and consensus."""

        description = task_payload.get("description", "")
        task_id = task_payload.get("task_id") or f"adv_{int(time.time())}"
        requires_consensus = bool(task_payload.get("requires_consensus", False))

        self.logger.info(
            "UnifiedOrchestrator recebeu tarefa complexa %s (consenso=%s)",
            task_id,
            requires_consensus,
        )

        if not description:
            return {
                "task_id": task_id,
                "success": False,
                "error": "description_missing",
                "message": "Descrição da tarefa não fornecida",
            }

        start_time = time.perf_counter()

        advanced_result = await self.supervisor.process_task_advanced(description)

        success = advanced_result.get("status", "").startswith("success")
        consensus = advanced_result.get("consensus")
        consensus_strength = None
        if isinstance(consensus, dict):
            consensus_strength = consensus.get("consensus_strength")

        elapsed = time.perf_counter() - start_time

        response: Dict[str, Any] = {
            "task_id": task_id,
            "description": description,
            "success": success,
            "advanced_result": advanced_result,
            "consensus_strength": consensus_strength,
            "latency": elapsed,
            "requires_consensus": requires_consensus,
        }

        if not success and not advanced_result.get("fallback"):
            # Fallback para fluxo padrão quando advanced falha silenciosamente
            self.logger.warning(
                "UnifiedOrchestrator ativando fallback simples para tarefa %s", task_id
            )
            simple_result = await self.supervisor.process_task(description)
            response["fallback_result"] = simple_result

        self.logger.info(
            "UnifiedOrchestrator concluiu tarefa %s (success=%s, latency=%.3fs)",
            task_id,
            success,
            elapsed,
        )

        return response
