"""Adaptive planner capable of recovering from failures."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AdaptiveReplanner:
    """Execute plans with the ability to replan after failures.

    BUGFIX (CRÍTICO-08): renomeada de ``AdaptivePlanner`` para eliminar a colisão
    de nome com :class:`src.planning.adaptive_planner.AdaptivePlanner` (duas
    classes homônimas no mesmo pacote dificultavam o diagnóstico).
    """

    max_replanning_attempts: int = 3
    failure_history: List[Dict[str, Any]] = field(default_factory=list)

    async def execute_with_replanning(
        self, initial_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Attempt to execute a plan with limited replanning attempts."""

        plan = dict(initial_plan)
        for attempt in range(1, self.max_replanning_attempts + 1):
            result = await self._execute_plan(plan)
            if result.get("success", False):
                return {"plan": plan, "result": result, "attempts": attempt}

            failure_context = self._analyze_failure(result, plan)
            self.failure_history.append(failure_context)
            plan = self._create_recovery_plan(plan, failure_context)
        return {
            "plan": plan,
            "result": {"success": False},
            "attempts": self.max_replanning_attempts,
        }

    async def _execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Executa o plano avaliando o desfecho de cada passo.

        BUGFIX (CRÍTICO-07): a versão anterior retornava ``{"success": True}``
        incondicionalmente, então o laço de replanejamento NUNCA era acionado.
        Agora um passo com ``outcome == "fail"`` faz a execução falhar, disparando
        de fato o replanejamento.
        """

        await asyncio.sleep(0)
        steps = plan.get("steps", [])
        for step in steps:
            if step.get("outcome") == "fail":
                return {
                    "success": False,
                    "failed_step": step,
                    "error": step.get("reason", "step failed"),
                }
        details = "Plano trivial executado" if not steps else "Plano executado"
        return {"success": True, "details": details, "steps_run": len(steps)}

    def _analyze_failure(
        self, result: Dict[str, Any], plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "plan": plan,
            "result": result,
            "reason": result.get("error", "unknown"),
        }

    def _create_recovery_plan(
        self, failed_plan: Dict[str, Any], failure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Gera um plano de recuperação limpando as falhas simuladas dos passos."""

        new_plan = dict(failed_plan)
        new_plan["steps"] = [
            {k: v for k, v in step.items() if k != "outcome"}
            for step in failed_plan.get("steps", [])
        ]
        new_plan.setdefault("recovery", []).append({"from": failure})
        return new_plan


# Compatibilidade retroativa: mantém o nome antigo como alias (nenhum módulo o
# importava, mas evita surpresas para integrações externas).
AdaptivePlanner = AdaptiveReplanner
