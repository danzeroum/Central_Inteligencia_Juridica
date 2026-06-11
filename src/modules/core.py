"""Módulos built-in da plataforma — registrados automaticamente no startup."""

from __future__ import annotations

from src.modules.manifest import ModuleManifest

JURIDICO_CORE = ModuleManifest(
    module_id="juridico_core",
    name="Jurídico Core",
    version="2.0.0",
    description=(
        "Módulo base: supervisor, tribunais e ledger de decisões. "
        "Sempre ativo; não requer licença separada."
    ),
    capabilities=["process_query", "jurisprudence_search", "decision_logging"],
    agent_types=["SupervisorAgent", "TribunalAgent"],
    endpoints=["/api/v1/tasks", "/api/v1/history"],
    is_active=True,
)

LEGISLATIVO = ModuleManifest(
    module_id="legislativo",
    name="Análise Legislativa",
    version="2.0.0",
    description="Consulta de proposições e análise de cenário legislativo via Câmara dos Deputados.",
    capabilities=["legislative_analysis", "bills_search"],
    agent_types=["FunctionalService"],
    endpoints=["/api/v1/proposicoes-legislativas", "/api/v1/analises-legislativas"],
    is_active=True,
)

JURISPRUDENCIA = ModuleManifest(
    module_id="jurisprudencia",
    name="Jurisprudência",
    version="2.0.0",
    description="Pesquisa e análise de jurisprudência via DataJud/DJEN.",
    capabilities=["jurisprudencia_search", "cnj_datajud"],
    agent_types=["QueueWorker"],
    endpoints=["/api/v1/jurisprudencia"],
    is_active=True,
)

BUILTIN_MODULES = [JURIDICO_CORE, LEGISLATIVO, JURISPRUDENCIA]
