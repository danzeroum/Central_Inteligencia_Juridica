"""IntelligenceAgent — due diligence 360° via IntelligenceOrchestrator.

Integra ao sistema multi-agente existente:
- Delegável pelo SupervisorAgent para intents de due diligence/patrimonial.
- Expõe tool MCP `consulta_inteligencia` via MCPToolRegistry.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class IntelligenceAgent:
    """Agente de due diligence 360° — consulta todos os adaptadores da Onda 1."""

    def __init__(self, orchestrator=None) -> None:
        self._orchestrator = orchestrator

    @property
    def orchestrator(self):
        if self._orchestrator is None:
            from src.integrations.orchestrator import get_intelligence_orchestrator

            self._orchestrator = get_intelligence_orchestrator()
        return self._orchestrator

    async def investigate(
        self,
        identifier: str,
        *,
        expand_qsa: bool = False,
        sources: Optional[list] = None,
        principal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Investigação completa. Retorna dict serializável."""
        report = await self.orchestrator.investigate(
            identifier,
            expand_qsa=expand_qsa,
            sources=sources,
            principal_id=principal_id,
        )
        return report.model_dump()

    async def process_task(self, task_description: str, **kwargs) -> Dict[str, Any]:
        """Interface compatível com o sistema de agentes do Supervisor."""
        from src.integrations.identifiers import classify_identifier

        # Extrai identificador do texto da tarefa
        import re

        cnpj_pat = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
        cpf_pat = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
        processo_pat = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")

        identifier = None
        for pat in [processo_pat, cnpj_pat, cpf_pat]:
            match = pat.search(task_description)
            if match:
                identifier = match.group(0)
                break

        if not identifier:
            return {
                "status": "error",
                "message": "Identificador (CPF/CNPJ/processo) não encontrado na tarefa.",
                "agent": "intelligence_agent",
            }

        report = await self.orchestrator.investigate(
            identifier,
            expand_qsa=kwargs.get("expand_qsa", False),
        )
        return {
            "status": "success",
            "agent": "intelligence_agent",
            "identifier_masked": report.identifier_masked,
            "risk_score": report.risk_score,
            "risk_dimensions": [d.model_dump() for d in report.risk_dimensions],
            "summary": report.summary,
            "hitl_status": report.hitl_status.value,
            "recommendations": report.recommendations,
        }

    def register_mcp_tool(self, registry) -> None:
        """Registra a tool `consulta_inteligencia` no MCPToolRegistry."""
        try:
            registry.register_tool(
                name="consulta_inteligencia",
                description="Realiza due diligence 360° para um CPF/CNPJ/processo",
                agent=self,
                handler=self.process_task,
            )
        except Exception as exc:
            logger.warning("Falha ao registrar tool MCP: %s", exc)


__all__ = ["IntelligenceAgent"]
