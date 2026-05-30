"""Agente dedicado à exploração de ambientes de rede."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from src.agents.base_agent import BaseAgent


class ExplorationAgent(BaseAgent):
    """Responsável por varrer um ambiente em busca de vulnerabilidades.

    Conforma-se a ``BaseAgent`` (corrige a violação de LSP apontada na auditoria),
    mantendo o método ``arun`` original por compatibilidade retroativa.
    """

    def __init__(self, scanner_tool: Callable[[str], Awaitable[Any]]) -> None:
        super().__init__("exploration")
        self.scanner_tool = scanner_tool
        self.tools = ["scanner"]

    async def arun(self, instruction: str) -> str:
        """Executa um scan e retorna um relatório textual."""

        result = await self.scanner_tool(instruction)
        return f"Exploration report: {result}"

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Interface padrão de ``BaseAgent`` para orquestração uniforme."""

        if not self.validate_input(task):
            raise ValueError("Invalid exploration task payload")

        report = await self.arun(task["description"])
        return {"success": True, "agent": self.agent_type, "report": report}
