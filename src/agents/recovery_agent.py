"""Agente dedicado à recuperação após anomalias."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from src.agents.base_agent import BaseAgent


class RecoveryAgent(BaseAgent):
    """Executa procedimentos de mitigação e recuperação.

    Conforma-se a ``BaseAgent`` (corrige a violação de LSP apontada na auditoria),
    mantendo o método ``arun`` original por compatibilidade retroativa.
    """

    def __init__(self, remediation_tool: Callable[[str], Awaitable[Any]]) -> None:
        super().__init__("recovery")
        self.remediation_tool = remediation_tool
        self.tools = ["remediation"]

    async def arun(self, incident_report: str) -> str:
        """Aciona rotinas de recuperação baseadas no relatório recebido."""

        result = await self.remediation_tool(incident_report)
        return f"Recovery actions: {result}"

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Interface padrão de ``BaseAgent`` para orquestração uniforme."""

        if not self.validate_input(task):
            raise ValueError("Invalid recovery task payload")

        actions = await self.arun(task["description"])
        return {"success": True, "agent": self.agent_type, "actions": actions}
