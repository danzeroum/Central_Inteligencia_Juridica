"""FiscalAgent — perfil fiscal de empresas via integrações jurídicas.

Consulta fontes fiscais: receita_cnpj + cadin + crc_protestos.
Gera proposta de consenso na dimensão fiscal via as_consensus_proposal().
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_FISCAL_SOURCES = ["receita_cnpj", "cadin", "crc_protestos"]


class FiscalAgent:
    """Agente fiscal delegável pelo SupervisorAgent para consultas de perfil fiscal."""

    def __init__(self, orchestrator=None) -> None:
        self._orchestrator = orchestrator

    @property
    def orchestrator(self):
        if self._orchestrator is None:
            from src.integrations.orchestrator import get_intelligence_orchestrator

            self._orchestrator = get_intelligence_orchestrator()
        return self._orchestrator

    async def get_fiscal_profile(
        self,
        cnpj: str,
        *,
        principal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retorna perfil fiscal completo de uma empresa."""
        report = await self.orchestrator.investigate(
            cnpj,
            sources=_FISCAL_SOURCES,
            principal_id=principal_id,
        )
        # Proposta de consenso na dimensão fiscal
        consensus_proposal = self.orchestrator.as_consensus_proposal(
            report, dimension="fiscal"
        )
        return {
            "identifier_masked": report.identifier_masked,
            "risk_score": report.risk_score,
            "fiscal_dimension": next(
                (d.model_dump() for d in report.risk_dimensions if d.name == "fiscal"),
                {"name": "fiscal", "score": 0.0},
            ),
            "recommendations": report.recommendations,
            "summary": report.summary,
            "consensus_proposal": consensus_proposal,
            "hitl_status": report.hitl_status.value,
        }

    async def process_task(self, task_description: str, **kwargs) -> Dict[str, Any]:
        """Interface compatível com o sistema de agentes do Supervisor."""
        cnpj_pat = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
        match = cnpj_pat.search(task_description)
        if not match:
            # Tenta com apenas dígitos
            digits_pat = re.compile(r"\b\d{14}\b")
            match = digits_pat.search(task_description)

        if not match:
            return {
                "status": "error",
                "message": "CNPJ não encontrado na tarefa.",
                "agent": "fiscal_agent",
            }

        cnpj = match.group(0)
        profile = await self.get_fiscal_profile(cnpj)
        return {
            "status": "success",
            "agent": "fiscal_agent",
            **profile,
        }

    def as_consensus_proposal(
        self,
        report,
        dimension: str = "fiscal",
    ) -> Dict[str, Any]:
        """Gera proposta de consenso na dimensão fiscal."""
        from src.integrations.orchestrator import IntelligenceOrchestrator

        return IntelligenceOrchestrator.as_consensus_proposal(
            report, dimension=dimension
        )


__all__ = ["FiscalAgent"]
