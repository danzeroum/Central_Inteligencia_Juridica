"""IntelligenceOrchestrator — coração da camada de integrações jurídicas.

Executa consulta paralela a todos os adaptadores relevantes, agrega resultados,
calcula risk score multidimensional e aciona HITL quando necessário.
"""

from __future__ import annotations

import asyncio
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
    HitlStatus,
    IdentifierQuery,
    IdentifierType,
    RelatedPartyFinding,
)
from src.integrations.registry import AdapterRegistry
from src.integrations.risk_engine import RiskEngine
from src.integrations.settings import get_qsa_settings

logger = logging.getLogger(__name__)

# Per-source circuit breakers — created on first use by _get_source_cb()
_source_circuit_breakers: Dict[str, Any] = {}


def _get_source_cb(source: str):
    """Return (or create) the CircuitBreaker for a given integration source."""
    if source not in _source_circuit_breakers:
        from src.tools.circuit_breaker import CircuitBreaker

        _source_circuit_breakers[source] = CircuitBreaker(
            name=f"integration_{source}",
            failure_threshold=5,
            timeout_seconds=60.0,
            success_threshold=2,
        )
    return _source_circuit_breakers[source]


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

        # Seleciona adaptadores; aplica política de fonte (CJ-001)
        candidates = self.registry.for_identifier(id_type)
        if sources:
            candidates = [a for a in candidates if a.service_name in sources]

        if self._policy:
            allowed = []
            for adapter in candidates:
                authorized = self._policy.authorized_source(adapter.data_type)
                if authorized and authorized.lower() == "llm":
                    # CJ-001: data_type governado como LLM-only — não consultar API real
                    logger.warning(
                        "CJ-001: %s/%s marcado como fonte LLM; adaptador ignorado.",
                        adapter.service_name,
                        adapter.data_type,
                    )
                else:
                    allowed.append(adapter)
            candidates = allowed

        q = IdentifierQuery(
            identifier=identifier,
            identifier_type=id_type,
            limit=limit,
            offset=offset,
        )

        # Execução paralela com captura de erros
        results: Dict[str, AdapterResult] = {}

        if candidates:
            tasks = [self._query_with_cache(adapter, q) for adapter in candidates]
            names = [adapter.service_name for adapter in candidates]

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
        engine = self._risk_engine
        if engine is None:
            from src.integrations.risk_engine import get_risk_engine

            engine = get_risk_engine()

        risk_score, risk_dimensions, risk_factors, recommendations, summary = (
            engine.score(results, related_parties)
        )

        # HITL gate — resultados retidos até decisão quando PENDING ou REJECTED
        hitl_status = HitlStatus.NOT_REQUIRED
        if engine.requires_hitl(risk_score):
            hitl_status = HitlStatus.PENDING
            if self._autonomy:
                try:
                    decision = await self._autonomy.execute_with_autonomy(
                        "intelligence_agent",
                        {
                            "type": "intelligence_query",
                            "score": risk_score,
                            "critical": True,
                        },
                    )
                    hitl_status = (
                        HitlStatus.APPROVED
                        if decision.get("executed")
                        else HitlStatus.REJECTED
                    )
                except Exception as exc:
                    logger.warning("HITL gate falhou: %s", exc)

        # Ledger — registra decisão com hash (nunca PII bruta)
        self._log_to_ledger(
            query_id=query_id,
            identifier_hash=id_hash,
            identifier_type=id_type,
            risk_score=risk_score,
            hitl_status=hitl_status,
            principal_id=principal_id,
        )

        # Retém resultados brutos enquanto HITL não for aprovado
        exposed_results = (
            {}
            if hitl_status in (HitlStatus.PENDING, HitlStatus.REJECTED)
            else {k: v.model_dump() for k, v in results.items()}
        )

        return ConsolidatedReport(
            query_id=query_id,
            identifier_masked=id_masked,
            identifier_type=id_type,
            results=exposed_results,
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
        """Executa consulta com cache, rate limiting e circuit breaker por fonte."""
        source = adapter.service_name

        # Rate limiter
        if self._rate_limiter:
            try:
                await self._rate_limiter.acquire(source)
            except Exception as exc:
                logger.warning("Rate limiter falhou para %s: %s", source, exc)

        # Cache hit — retorna antes de tocar o CB
        if self._cache:
            try:
                cached = await asyncio.to_thread(
                    self._cache.get_cached,
                    "ci_integrations",
                    source,
                    identifier=audit_hash(q.identifier),
                )
                if cached is not None:
                    from src.integrations.metrics import record_cache_hit

                    record_cache_hit(source)
                    result_data = cached if isinstance(cached, dict) else {}
                    if result_data:
                        result = AdapterResult.model_validate(result_data)
                        result.from_cache = True
                        return result
            except Exception as exc:
                logger.debug("Cache read falhou para %s: %s", source, exc)

        # Circuit breaker protege a chamada real ao adaptador
        cb = _get_source_cb(source)
        from src.tools.circuit_breaker import CircuitBreakerOpenError

        try:
            with cb.protect():
                result = await adapter.query(q)
        except CircuitBreakerOpenError:
            from src.integrations.metrics import record_circuit_state

            record_circuit_state(source, "open")
            return AdapterResult(
                source=source,
                status=AdapterStatus.FAILED,
                error="circuit_breaker_open",
            )

        # Grava resultado no cache
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

        # Métricas Prometheus
        try:
            from src.integrations.metrics import record_circuit_state, record_query

            record_query(
                source=source,
                status=result.status.value,
                data_mode=result.data_mode.value,
                latency_s=result.latency_ms / 1000,
            )
            record_circuit_state(source, cb.state.value)
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
                    # busca por nome tem risco inerente de homônimos
                    homonimo_possivel=True,
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
            self._ledger.log_decision(
                agent_type="intelligence_agent",
                decision_type="INTELLIGENCE_QUERY",
                metadata={
                    "identifier_hash": identifier_hash,
                    "identifier_type": identifier_type.value,
                    "query_id": query_id,
                    "risk_score": risk_score,
                    "hitl_status": hitl_status.value,
                    "principal_id": principal_id or "anonymous",
                },
            )
        except Exception as exc:
            logger.debug("Ledger log_decision falhou: %s", exc)

    def health(self) -> Dict[str, Any]:
        """Status de saúde do orquestrador, adaptadores e circuit breakers."""
        adapters_health = {}
        for name in self.registry.names():
            adapter = self.registry.get(name)
            if adapter:
                cb = _source_circuit_breakers.get(f"integration_{name}")
                adapters_health[name] = {
                    "enabled": adapter.enabled,
                    "mode": adapter.settings.mode,
                    "zone": adapter.zone.value,
                    "circuit_breaker": cb.state.value if cb else "closed",
                }
        return {"status": "ok", "adapters": adapters_health}

    @staticmethod
    def as_consensus_proposal(
        report: ConsolidatedReport,
        dimension: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Converte relatório em proposta de consenso para o WeightedConsensusEngine."""
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


_orchestrator_singleton: Optional[IntelligenceOrchestrator] = None


def get_intelligence_orchestrator() -> IntelligenceOrchestrator:
    """Singleton factory que constrói o orquestrador com todas as dependências.

    Usado por schema.py, IntelligenceAgent e FiscalAgent para compartilhar
    instância com cache/ledger/policy/rate_limiter/autonomy devidamente injetados.
    """
    global _orchestrator_singleton
    if _orchestrator_singleton is not None:
        return _orchestrator_singleton

    from src.integrations.adapters.cadin_adapter import CadinAdapter
    from src.integrations.adapters.crc_protestos_adapter import CrcProtestosAdapter
    from src.integrations.adapters.datajud_adapter import DataJudAdapter
    from src.integrations.adapters.djen_adapter import DjenAdapter
    from src.integrations.adapters.onr_imoveis_adapter import OnrImoveisAdapter
    from src.integrations.adapters.receita_cnpj_adapter import ReceitaCnpjAdapter
    from src.integrations.adapters.tse_adapter import TseAdapter
    from src.integrations.rate_limiter import AsyncRateLimiter
    from src.integrations.registry import get_registry
    from src.integrations.risk_engine import get_risk_engine
    from src.utils.ledger import DecisionLedger

    registry = get_registry()
    for cls in [
        DataJudAdapter,
        DjenAdapter,
        ReceitaCnpjAdapter,
        TseAdapter,
        CrcProtestosAdapter,
        CadinAdapter,
        OnrImoveisAdapter,
    ]:
        if not registry.get(cls.service_name):
            try:
                registry.register(cls)
            except Exception as exc:
                logger.warning("Falha ao registrar %s: %s", cls.service_name, exc)

    cache = None
    try:
        from src.utils.cache_manager import CacheManager

        cache = CacheManager()
    except Exception as exc:
        logger.warning("CacheManager indisponível: %s — continuando sem cache", exc)

    autonomy = None
    try:
        from src.hitl.progressive_autonomy import get_autonomy_manager

        autonomy = get_autonomy_manager()
    except Exception as exc:
        logger.warning("AutonomyManager indisponível: %s", exc)

    policy = None
    try:
        from src.governance.data_source_policy import get_data_source_policy

        policy = get_data_source_policy()
    except Exception as exc:
        logger.warning("DataSourcePolicy indisponível: %s", exc)

    _orchestrator_singleton = IntelligenceOrchestrator(
        registry,
        cache=cache,
        ledger=DecisionLedger(),
        autonomy=autonomy,
        policy=policy,
        risk_engine=get_risk_engine(),
        rate_limiter=AsyncRateLimiter(),
    )
    return _orchestrator_singleton


__all__ = ["IntelligenceOrchestrator", "get_intelligence_orchestrator"]
