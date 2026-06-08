"""Agente dedicado à exploração de ambientes de rede."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from src.agents.base_agent import BaseAgent


class ExplorationAgent(BaseAgent):
    """Responsável por varrer um ambiente em busca de vulnerabilidades.

    Conforma-se a ``BaseAgent`` (corrige a violação de LSP apontada na auditoria),
    mantendo o método ``arun`` original por compatibilidade retroativa.
    """

    def __init__(
        self, scanner_tool: Optional[Callable[[str], Awaitable[Any]]] = None
    ) -> None:
        super().__init__("exploration")
        self.name = "Exploration Agent"
        self.description = "Responsável por varrer ambientes em busca de vulnerabilidades e pontos de falha."
        self.capabilities = [
            "vulnerability_scan",
            "network_exploration",
            "security_assessment",
        ]
        self.specialization = "exploration"
        self.scanner_tool = scanner_tool
        self.tools = ["scanner"]

    async def arun(self, instruction: str) -> str:
        """Executa um scan e retorna um relatório textual."""

        if self.scanner_tool is None:
            return f"Exploration acknowledged (no scanner configured): {instruction}"
        result = await self.scanner_tool(instruction)
        return f"Exploration report: {result}"

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Interface padrão de ``BaseAgent`` para orquestração uniforme."""

        if not self.validate_input(task):
            raise ValueError("Invalid exploration task payload")

        report = await self.arun(task["description"])
        return {"success": True, "agent": self.agent_type, "report": report}
