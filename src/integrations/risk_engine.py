"""Motor de risco determinístico para a camada de integrações jurídicas.

Calcula score 0-100 a partir dos resultados dos adaptadores.
Sem LLM (CJ-001). Configurado via config/integrations/risk_scoring.yaml.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from src.integrations.models import (
    AdapterResult,
    AdapterStatus,
    PendenciaCadin,
    Protesto,
    RelatedPartyFinding,
    RiskDimension,
    RiskFactor,
)

logger = logging.getLogger(__name__)

DEFAULT_RISK_CONFIG = (
    Path(__file__).resolve().parents[2] / "config" / "integrations" / "risk_scoring.yaml"
)


@lru_cache(maxsize=1)
def _load_risk_config(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logger.warning("risk_scoring.yaml não encontrado; usando defaults.")
        return {}


class RiskEngine:
    """Motor de risco multidimensional configurado por YAML."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config = _load_risk_config(config_path or DEFAULT_RISK_CONFIG)
        self._weights: Dict[str, Dict[str, Any]] = self._config.get("weights") or {}
        self._max_score: int = int(self._config.get("max_score", 100))
        self._hitl_threshold: int = int(
            (self._config.get("hitl") or {}).get("threshold", 70)
        )
        self._hitl_enabled: bool = bool(
            (self._config.get("hitl") or {}).get("enabled", True)
        )
        self._recommendations_config: Dict[str, str] = (
            self._config.get("recommendations") or {}
        )

    def score(
        self,
        results: Dict[str, AdapterResult],
        related_parties: Optional[List[RelatedPartyFinding]] = None,
    ) -> Tuple[float, List[RiskDimension], List[RiskFactor], List[str], str]:
        """Calcula score total (0-100), dimensões, fatores, recomendações e sumário.

        Retorna: (score_total, dimensoes, fatores, recomendacoes, sumario)
        Determinístico — sem LLM.
        """
        factors: List[RiskFactor] = []

        # Protestos
        if "crc_protestos" in results:
            r = results["crc_protestos"]
            if r.status == AdapterStatus.SUCCESS and r.items:
                ativos = [
                    p for p in r.items
                    if isinstance(p, Protesto) and (p.situacao or "").upper() in ("PROTESTADO", "ATIVO")
                ]
                if ativos:
                    factors.append(self._factor("protesto_ativo", "crc_protestos"))

        # Cadin
        if "cadin" in results:
            r = results["cadin"]
            if r.status == AdapterStatus.SUCCESS and r.items:
                pendencias = [
                    p for p in r.items
                    if isinstance(p, PendenciaCadin) and (p.situacao or "").upper() == "ATIVO"
                ]
                if pendencias:
                    factors.append(self._factor("cadin_pendencia", "cadin"))

        # Processos
        if "datajud" in results:
            r = results["datajud"]
            if r.status == AdapterStatus.SUCCESS:
                total = r.total_available or len(r.items)
                if total > 5:
                    factors.append(self._factor("processos_total_gt_5", "datajud"))
                # Execuções: detecta pela classe/assunto
                execucoes = sum(
                    1
                    for p in r.items
                    if _is_execucao(p)
                )
                if execucoes > 2:
                    factors.append(self._factor("execucoes_gt_2", "datajud"))

        # Publicações com execução
        if "djen" in results:
            r = results["djen"]
            if r.status == AdapterStatus.SUCCESS:
                exec_pubs = sum(1 for p in r.items if _pub_is_execucao(p))
                if exec_pubs > 0:
                    factors.append(self._factor("publicacao_execucao_recente", "djen"))

        # Empresa situação irregular
        if "receita_cnpj" in results:
            r = results["receita_cnpj"]
            if r.status == AdapterStatus.SUCCESS and r.items:
                for empresa in r.items:
                    sit = (getattr(empresa, "situacao_cadastral", "") or "").upper()
                    if sit in ("INAPTA", "SUSPENSA", "BAIXADA", "CANCELADA"):
                        factors.append(self._factor("empresa_situacao_irregular", "receita_cnpj"))
                        break

        # QSA / relacionados
        if related_parties:
            com_processos = any(
                p.total_ocorrencias > 0 and p.fonte in ("datajud", "djen")
                for p in related_parties
            )
            if com_processos:
                factors.append(self._factor("qsa_socio_com_processos", "qsa"))

            com_publicacoes = any(
                p.total_ocorrencias > 0 and p.fonte == "djen"
                for p in related_parties
            )
            if com_publicacoes:
                factors.append(self._factor("qsa_socio_com_publicacoes", "qsa"))

        # Cálculo por dimensão
        dim_scores: Dict[str, float] = defaultdict(float)
        for f in factors:
            dim_scores[f.dimension] += f.weight

        dimensions = [
            RiskDimension(name=dim, score=min(dim_scores[dim], 100.0))
            for dim in ["juridico", "fiscal", "patrimonial", "societario"]
        ]

        total = min(sum(f.weight for f in factors), self._max_score)
        total = float(total)

        recommendations = self._build_recommendations(factors, total)
        summary = self._build_summary(total, factors)

        return total, dimensions, factors, recommendations, summary

    def requires_hitl(self, score: float) -> bool:
        return self._hitl_enabled and score >= self._hitl_threshold

    def _factor(self, code: str, source: str) -> RiskFactor:
        cfg = self._weights.get(code) or {}
        return RiskFactor(
            code=code,
            description=self._recommendations_config.get(code, code.replace("_", " ")),
            weight=int(cfg.get("peso", 5)),
            source=source,
            dimension=str(cfg.get("dimension", "juridico")),
        )

    def _build_recommendations(
        self, factors: List[RiskFactor], score: float
    ) -> List[str]:
        recs = [
            self._recommendations_config.get(f.code, f.description)
            for f in factors
            if self._recommendations_config.get(f.code)
        ]
        if score >= self._hitl_threshold:
            generic = self._recommendations_config.get(
                "score_gte_70", "Recomenda-se due diligence aprofundada e revisão humana."
            )
            if generic not in recs:
                recs.append(generic)
        return recs

    def _build_summary(self, score: float, factors: List[RiskFactor]) -> str:
        if not factors:
            return f"Nenhum fator de risco identificado. Score: {score:.0f}/100."
        nomes = ", ".join(f.code.replace("_", " ") for f in factors[:3])
        suffix = f" e mais {len(factors)-3} fator(es)" if len(factors) > 3 else ""
        return (
            f"Score de risco: {score:.0f}/100. "
            f"Fatores identificados: {nomes}{suffix}."
        )


def _is_execucao(processo: Any) -> bool:
    """Verifica se um ProcessoNormalizado é execução."""
    classe = (getattr(processo, "classe", "") or "").lower()
    assuntos = getattr(processo, "assuntos", []) or []
    assunto_nomes = " ".join(
        (a.get("nome", "") if isinstance(a, dict) else "").lower()
        for a in assuntos
    )
    return "execu" in classe or "execu" in assunto_nomes or "cobran" in classe


def _pub_is_execucao(pub: Any) -> bool:
    tipo = (getattr(pub, "tipo", "") or "").lower()
    texto = (getattr(pub, "texto", "") or "").lower()
    return "execu" in tipo or "execu" in texto or "cobran" in tipo


_engine: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    global _engine
    if _engine is None:
        _engine = RiskEngine()
    return _engine


__all__ = ["RiskEngine", "get_risk_engine"]
