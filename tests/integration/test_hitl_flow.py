"""Integration test for complete HITL flow."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.hitl.hitl_queue import get_hitl_queue
from src.hitl.progressive_autonomy import ProgressiveAutonomyManager


def test_hitl_full_workflow():
    """Testa fluxo completo: requisição → fila → decisão → resposta."""

    manager = ProgressiveAutonomyManager()
    queue = get_hitl_queue()
    queue.clear()

    # Simular agente com baixa confiança (deve acionar HITL)
    manager.agent_trust_scores["test_agent"] = 0.3

    action = {
        "type": "execute_critical_task",
        "critical": True,
        "parameters": {"target": "production_database"},
    }

    # Executar em thread separada para não bloquear
    async def execute_and_approve():
        # Iniciar execução (vai bloquear esperando aprovação)
        execution_task = asyncio.create_task(
            manager.execute_with_autonomy("test_agent", action)
        )

        # Aguardar request aparecer na fila
        await asyncio.sleep(0.5)

        # Verificar que existe pendente
        pending = queue.get_pending_requests()
        assert len(pending) > 0

        request_id = pending[0]["request_id"]

        # Simular aprovação humana
        queue.record_decision(
            request_id=request_id,
            approved=True,
            operator_id="test_operator",
        )

        # Aguardar conclusão
        result = await execution_task

        assert result["executed"] is True
        return result

    result = asyncio.run(execute_and_approve())
    queue.clear()
    print("✅ HITL Flow Test Passed:", result)


if __name__ == "__main__":
    test_hitl_full_workflow()
