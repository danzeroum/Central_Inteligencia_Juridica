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
            from src.integrations.orchestrator import IntelligenceOrchestrator
            from src.integrations.registry import get_registry
            from src.integrations.risk_engine import get_risk_engine
            from src.integrations.adapters.receita_cnpj_adapter import ReceitaCnpjAdapter
            from src.integrations.adapters.cadin_adapter import CadinAdapter
            from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter

            registry = get_registry()
            for cls in [ReceitaCnpjAdapter, CadinAdapter, CrcProtestosAdapter]:
                if not registry.get(cls.service_name):
                    try:
                        registry.register(cls)
                    except Exception as exc:
                        logger.warning("Falha ao registrar %s: %s", cls.service_name, exc)

            self._orchestrator = IntelligenceOrchestrator(
                registry,
                risk_engine=get_risk_engine(),
            )
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
        return IntelligenceOrchestrator.as_consensus_proposal(report, dimension=dimension)


__all__ = ["FiscalAgent"]
