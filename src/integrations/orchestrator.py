"""IntelligenceOrchestrator — coração da camada de integrações jurídicas.

Executa consulta paralela a todos os adaptadores relevantes, agrega resultados,
calcula risk score multidimensional e aciona HITL quando necessário.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional

from src.integrations.identifiers import (
    audit_hash,
    classify_identifier,
    mask_identifier,
)
from src.integrations.models import (
    AdapterResult,
    AdapterStatus,
    ConsolidatedReport,
    DataMode,
    HitlStatus,
    IdentifierQuery,
    IdentifierType,
    RelatedPartyFinding,
)
from src.integrations.registry import AdapterRegistry
from src.integrations.risk_engine import RiskEngine
from src.integrations.settings import get_qsa_settings

logger = logging.getLogger(__name__)


class IntelligenceOrchestrator:
    """Orquestrador paralelo com cache, rate limit, CB, ledger e HITL."""

    def __init__(
        self,
        registry: AdapterRegistry,
        *,
        cache=None,
        ledger=None,
        autonomy=None,
        policy=None,
        risk_engine: Optional[RiskEngine] = None,
        rate_limiter=None,
    ) -> None:
        self.registry = registry
        self._cache = cache
        self._ledger = ledger
        self._autonomy = autonomy
        self._policy = policy
        self._risk_engine = risk_engine
        self._rate_limiter = rate_limiter

    async def investigate(
        self,
        identifier: str,
        *,
        sources: Optional[List[str]] = None,
        principal_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        expand_qsa: bool = False,
    ) -> ConsolidatedReport:
        """Investigação completa — nunca propaga exceção."""
        try:
            return await self._investigate_inner(
                identifier,
                sources=sources,
                principal_id=principal_id,
                limit=limit,
                offset=offset,
                expand_qsa=expand_qsa,
            )
        except Exception as exc:
            logger.exception("IntelligenceOrchestrator.investigate falhou: %s", exc)
            id_type = classify_identifier(identifier)
            return ConsolidatedReport(
                query_id=str(uuid.uuid4()),
                identifier_masked=mask_identifier(identifier, id_type),
                identifier_type=id_type,
                metadata={"error": str(exc)},
            )

    async def _investigate_inner(
        self,
        identifier: str,
        *,
        sources: Optional[List[str]],
        principal_id: Optional[str],
        limit: int,
        offset: int,
        expand_qsa: bool,
    ) -> ConsolidatedReport:
        query_id = str(uuid.uuid4())
        id_type = classify_identifier(identifier)
        id_masked = mask_identifier(identifier, id_type)
        id_hash = audit_hash(identifier)

        # Seleciona adaptadores
        candidates = self.registry.for_identifier(id_type)
        if sources:
            candidates = [a for a in candidates if a.service_name in sources]

        q = IdentifierQuery(
            identifier=identifier,
            identifier_type=id_type,
            limit=limit,
            offset=offset,
        )

        # Execução paralela com captura de erros
        results: Dict[str, AdapterResult] = {}
        skipped: List[str] = []

        if candidates:
            tasks = []
            names = []
            for adapter in candidates:
                # Verificação de política
                if self._policy:
                    try:
                        self._policy.assert_source(adapter.data_type, "llm")
                    except Exception:
                        pass  # apenas garantindo que não é LLM
                tasks.append(self._query_with_cache(adapter, q))
                names.append(adapter.service_name)

            raw_results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, res in zip(names, raw_results):
                if isinstance(res, Exception):
                    results[name] = AdapterResult(
                        source=name,
                        status=AdapterStatus.FAILED,
                        error=str(res),
                    )
                else:
                    results[name] = res

        # Marca adaptadores habilitados mas não selecionados como SKIPPED
        for adapter in self.registry.all_enabled():
            if adapter.service_name not in results:
                results[adapter.service_name] = AdapterResult(
                    source=adapter.service_name,
                    status=AdapterStatus.SKIPPED,
                )

        # Expansão QSA
        related_parties: List[RelatedPartyFinding] = []
        if expand_qsa:
            related_parties = await self._expand_qsa(results, q)

        # Risk score
        risk_score = 0.0
        risk_dimensions = []
        risk_factors = []
        recommendations: List[str] = []
        summary = None

        if self._risk_engine:
            risk_score, risk_dimensions, risk_factors, recommendations, summary = (
                self._risk_engine.score(results, related_parties)
            )
        else:
            from src.integrations.risk_engine import get_risk_engine
            engine = get_risk_engine()
            risk_score, risk_dimensions, risk_factors, recommendations, summary = (
                engine.score(results, related_parties)
            )

        # HITL gate
        hitl_status = HitlStatus.NOT_REQUIRED
        engine = self._risk_engine or __import__(
            "src.integrations.risk_engine", fromlist=["get_risk_engine"]
        ).get_risk_engine()
        if engine.requires_hitl(risk_score):
            hitl_status = HitlStatus.PENDING
            if self._autonomy:
                try:
                    decision = await self._autonomy.execute_with_autonomy(
                        "intelligence_agent",
                        {"type": "intelligence_query", "score": risk_score, "critical": True},
                    )
                    if decision.get("executed"):
                        hitl_status = HitlStatus.APPROVED
                    else:
                        hitl_status = HitlStatus.REJECTED
                except Exception as exc:
                    logger.warning("HITL gate falhou: %s", exc)

        # Ledger
        self._log_to_ledger(
            query_id=query_id,
            identifier_hash=id_hash,
            identifier_type=id_type,
            risk_score=risk_score,
            hitl_status=hitl_status,
            principal_id=principal_id,
        )

        return ConsolidatedReport(
            query_id=query_id,
            identifier_masked=id_masked,
            identifier_type=id_type,
            results={k: v.model_dump() for k, v in results.items()},
            risk_score=risk_score,
            risk_dimensions=risk_dimensions,
            risk_factors=risk_factors,
            related_parties=related_parties,
            recommendations=recommendations,
            summary=summary,
            hitl_status=hitl_status,
            metadata={
                "qsa_expanded": expand_qsa and bool(related_parties),
                "socios_consultados": len(related_parties),
                "sources_queried": list(results.keys()),
            },
        )

    async def _query_with_cache(self, adapter, q: IdentifierQuery) -> AdapterResult:
        """Executa consulta com cache opcional e rate limiting."""
        source = adapter.service_name

        # Rate limiter
        if self._rate_limiter:
            try:
                await self._rate_limiter.acquire(source)
            except Exception as exc:
                logger.warning("Rate limiter falhou para %s: %s", source, exc)

        # Cache (síncrono via thread)
        cache_key = None
        if self._cache:
            cache_key = f"ci_integrations:{source}:{audit_hash(q.identifier)}"
            try:
                cached = await asyncio.to_thread(
                    self._cache.get_cached, "ci_integrations", source,
                    identifier=audit_hash(q.identifier)
                )
                if cached is not None:
                    from src.integrations.metrics import record_cache_hit
                    record_cache_hit(source)
                    result_data = cached if isinstance(cached, dict) else {}
                    result = AdapterResult(**result_data) if result_data else None
                    if result:
                        result.from_cache = True
                        return result
            except Exception as exc:
                logger.debug("Cache read falhou para %s: %s", source, exc)

        # Consulta real
        result = await adapter.query(q)

        # Grava cache
        if self._cache and result.status == AdapterStatus.SUCCESS:
            try:
                ttl = adapter.settings.cache_ttl_seconds
                await asyncio.to_thread(
                    self._cache.set_cached,
                    "ci_integrations",
                    source,
                    result.model_dump(),
                    identifier=audit_hash(q.identifier),
                    ttl=ttl,
                )
            except Exception as exc:
                logger.debug("Cache write falhou para %s: %s", source, exc)

        # Métricas
        try:
            from src.integrations.metrics import record_query
            record_query(
                source=source,
                status=result.status.value,
                data_mode=result.data_mode.value,
                latency_s=result.latency_ms / 1000,
            )
        except Exception:
            pass

        return result

    async def _expand_qsa(
        self,
        results: Dict[str, AdapterResult],
        original_q: IdentifierQuery,
    ) -> List[RelatedPartyFinding]:
        """Expansão QSA: consulta paralela por sócios da empresa."""
        qsa_settings = get_qsa_settings()
        if not qsa_settings.get("enabled"):
            return []

        receita_result = results.get("receita_cnpj")
        if not receita_result or receita_result.status != AdapterStatus.SUCCESS:
            return []

        if not receita_result.items:
            return []

        from src.integrations.models import EmpresaCadastro

        empresa = receita_result.items[0]
        if not isinstance(empresa, EmpresaCadastro):
            # Pode ser dict se veio do cache
            if isinstance(empresa, dict):
                empresa = EmpresaCadastro.model_validate(empresa)
            else:
                return []

        socios = empresa.qsa or []
        max_socios = int(qsa_settings.get("max_socios", 5))
        socios = socios[:max_socios]

        tasks = [self._consult_socio(socio) for socio in socios]
        findings = await asyncio.gather(*tasks, return_exceptions=True)

        return [f for f in findings if isinstance(f, RelatedPartyFinding)]

    async def _consult_socio(self, socio) -> Optional[RelatedPartyFinding]:
        """Consulta um sócio em DJEN/TSE (PF) ou receita_cnpj (PJ)."""
        try:
            nome = socio.nome if hasattr(socio, "nome") else (socio.get("nome") or "")
            tipo = socio.tipo if hasattr(socio, "tipo") else (socio.get("tipo") or "PF")

            if not nome:
                return None

            total_ocorrencias = 0
            fontes_usadas = []

            if tipo == "PJ":
                # Sócio PJ: consulta receita_cnpj
                identificador = (
                    socio.identificador_mascarado
                    if hasattr(socio, "identificador_mascarado")
                    else (socio.get("identificador_mascarado") or "")
                )
                import re
                d = re.sub(r"\D", "", identificador or "")
                if len(d) == 14:
                    q_pj = IdentifierQuery(
                        identifier=d,
                        identifier_type=IdentifierType.CNPJ,
                        limit=1,
                    )
                    adapter = self.registry.get("receita_cnpj")
                    if adapter:
                        res = await adapter.query(q_pj)
                        if res.status == AdapterStatus.SUCCESS and res.items:
                            fontes_usadas.append("receita_cnpj")

                return RelatedPartyFinding(
                    nome=nome,
                    vinculo="socio",
                    tipo="PJ",
                    fonte="receita_cnpj",
                    resumo=f"Sócio PJ: {nome}",
                    total_ocorrencias=total_ocorrencias,
                    homonimo_possivel=False,
                )
            else:
                # Sócio PF: consulta DJEN e TSE por nome
                q_nome = IdentifierQuery(
                    identifier=nome,
                    identifier_type=IdentifierType.NOME,
                    limit=10,
                )

                djen_adapter = self.registry.get("djen")
                tse_adapter = self.registry.get("tse")

                djen_count = 0
                tse_count = 0

                if djen_adapter:
                    try:
                        res = await djen_adapter.query(q_nome)
                        if res.status == AdapterStatus.SUCCESS:
                            djen_count = len(res.items)
                            fontes_usadas.append("djen")
                    except Exception:
                        pass

                if tse_adapter:
                    try:
                        res = await tse_adapter.query(q_nome)
                        if res.status == AdapterStatus.SUCCESS:
                            tse_count = len(res.items)
                            fontes_usadas.append("tse")
                    except Exception:
                        pass

                total_ocorrencias = djen_count + tse_count
                fonte_str = ", ".join(fontes_usadas) if fontes_usadas else "djen"

                return RelatedPartyFinding(
                    nome=nome,
                    vinculo="socio",
                    tipo="PF",
                    fonte=fonte_str,
                    resumo=(
                        f"Sócio PF encontrado em {total_ocorrencias} publicação(ões)/registro(s)."
                        if total_ocorrencias > 0
                        else f"Sócio PF: {nome} (sem ocorrências nas fontes consultadas)."
                    ),
                    total_ocorrencias=total_ocorrencias,
                    homonimo_possivel=True,  # busca por nome sempre tem risco de homônimos
                )
        except Exception as exc:
            logger.warning("_consult_socio falhou para %s: %s", socio, exc)
            return None

    def _log_to_ledger(
        self,
        query_id: str,
        identifier_hash: str,
        identifier_type: IdentifierType,
        risk_score: float,
        hitl_status: HitlStatus,
        principal_id: Optional[str],
    ) -> None:
        if not self._ledger:
            return
        try:
            self._ledger.record(
                decision_type="INTELLIGENCE_QUERY",
                identifier_hash=identifier_hash,
                identifier_type=identifier_type.value,
                query_id=query_id,
                risk_score=risk_score,
                hitl_status=hitl_status.value,
                principal_id=principal_id or "anonymous",
            )
        except Exception as exc:
            logger.debug("Ledger record falhou: %s", exc)

    def health(self) -> Dict[str, Any]:
        """Status de saúde do orquestrador e de cada adaptador."""
        adapters_health = {}
        for name in self.registry.names():
            adapter = self.registry.get(name)
            if adapter:
                adapters_health[name] = {
                    "enabled": adapter.enabled,
                    "mode": adapter.settings.mode,
                    "zone": adapter.zone.value,
                }
        return {"status": "ok", "adapters": adapters_health}

    @staticmethod
    def as_consensus_proposal(
        report: ConsolidatedReport,
        dimension: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Converte relatório em proposta de consenso para o WeightedConsensusEngine.

        dimension=None → usa score total; dimension='fiscal' → usa score fiscal.
        """
        if dimension:
            dim_score = next(
                (d.score for d in report.risk_dimensions if d.name == dimension), 0.0
            )
        else:
            dim_score = report.risk_score

        confidence = max(0.0, 1.0 - dim_score / 100.0)
        return {
            "proposal": report.summary or f"Risk score {dim_score:.0f}/100",
            "confidence": round(confidence, 3),
            "risk_score": dim_score,
            "dimension": dimension or "total",
        }


__all__ = ["IntelligenceOrchestrator"]
