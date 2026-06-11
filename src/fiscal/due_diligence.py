"""DueDiligenceService — Relatório 360° jurídico+fiscal por CNPJ (S-A.1).

Cruza perfil societário/jurídico (IntelligenceOrchestrator) com perfil fiscal
(FiscalAgent: receita_cnpj + cadin + crc_protestos) para uma visão unificada.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CNPJ_DIGITS = re.compile(r"\D")


def _normalize_cnpj(cnpj: str) -> str:
    return _CNPJ_DIGITS.sub("", cnpj)


class DueDiligenceService:
    """Orchestrates FiscalAgent + IntelligenceOrchestrator for 360° CNPJ profile."""

    def __init__(self, fiscal_agent=None, orchestrator=None) -> None:
        self._fiscal_agent = fiscal_agent
        self._orchestrator = orchestrator

    @property
    def fiscal_agent(self):
        if self._fiscal_agent is None:
            from src.agents.fiscal_agent import FiscalAgent

            self._fiscal_agent = FiscalAgent()
        return self._fiscal_agent

    @property
    def orchestrator(self):
        if self._orchestrator is None:
            from src.integrations.orchestrator import get_intelligence_orchestrator

            self._orchestrator = get_intelligence_orchestrator()
        return self._orchestrator

    async def generate_report(
        self,
        cnpj: str,
        *,
        principal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns a 360° due diligence report for the CNPJ."""
        from src.integrations.identifiers import _validate_cnpj, mask_identifier

        normalized = _normalize_cnpj(cnpj)
        if not _validate_cnpj(normalized):
            raise ValueError(f"CNPJ inválido: {cnpj}")

        cnpj_masked = mask_identifier(normalized)

        fiscal_profile = await self.fiscal_agent.get_fiscal_profile(
            normalized, principal_id=principal_id
        )

        try:
            legal_report = await self.orchestrator.investigate(
                normalized, principal_id=principal_id
            )
            legal_data: Dict[str, Any] = {
                "risk_score": legal_report.risk_score,
                "summary": legal_report.summary,
                "recommendations": legal_report.recommendations,
                "hitl_status": legal_report.hitl_status.value,
            }
        except Exception as exc:
            logger.warning("Perfil jurídico indisponível para %s: %s", cnpj_masked, exc)
            legal_data = {"status": "indisponivel", "reason": "servico_externo"}

        fiscal_risk = fiscal_profile.get("risk_score", 0.0) or 0.0
        legal_risk = legal_data.get("risk_score", 0.0) or 0.0
        overall_risk = round((fiscal_risk + legal_risk) / 2, 3)

        return {
            "cnpj_masked": cnpj_masked,
            "overall_risk_score": overall_risk,
            "fiscal": fiscal_profile,
            "legal": legal_data,
            "module": "cadastro_risco",
            "version": "1.0.0",
        }


_service: Optional[DueDiligenceService] = None


def get_due_diligence_service() -> DueDiligenceService:
    """Singleton para DueDiligenceService."""
    global _service
    if _service is None:
        _service = DueDiligenceService()
    return _service
