"""Módulos built-in da plataforma — registrados automaticamente no startup."""

from __future__ import annotations

from src.modules.manifest import ModuleManifest
from src.modules.slots import FrontendSlot

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
    slot=FrontendSlot(
        label="Consultas Jurídicas",
        icon="gavel",
        route="/app/juridico",
        order=1,
        screen_id="assistant",
    ),
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
    slot=FrontendSlot(
        label="Análise Legislativa",
        icon="balance",
        route="/app/legislativo",
        order=2,
        screen_id="legis",
    ),
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
    slot=FrontendSlot(
        label="Jurisprudência",
        icon="library_books",
        route="/app/jurisprudencia",
        order=3,
        screen_id="juris",
    ),
)

CADASTRO_RISCO = ModuleManifest(
    module_id="cadastro_risco",
    name="Cadastro e Risco",
    version="1.0.0",
    description=(
        "Due Diligência Fiscal 360°: perfil societário+fiscal+protestos por CNPJ. "
        "Módulo comercial — Bloco A (S-A.1)."
    ),
    capabilities=["due_diligence_360", "fiscal_profile", "risk_scoring"],
    agent_types=["FiscalAgent"],
    endpoints=["/api/v1/fiscal/due-diligence/{cnpj}"],
    is_active=True,
    slot=FrontendSlot(
        label="Due Diligência",
        icon="search",
        route="/app/fiscal/due-diligence",
        order=4,
        screen_id="due-diligence",
    ),
)

CONSULTORIA_TRIBUTARIA = ModuleManifest(
    module_id="consultoria_tributaria",
    name="Consultoria Tributária",
    version="1.0.0",
    description=(
        "Parecer tributário assistido por RAG sobre legislação fiscal brasileira. "
        "CJ-001: citações verificáveis; sem invenção de normas. Bloco A (S-A.2)."
    ),
    capabilities=["tax_advisory", "rag_tributario", "guardrails_cj001"],
    agent_types=["FiscalAgent"],
    endpoints=["/api/v1/fiscal/consultoria"],
    is_active=True,
    slot=FrontendSlot(
        label="Consultoria Tributária",
        icon="calculate",
        route="/app/fiscal/consultoria",
        order=5,
        screen_id="consultoria",
    ),
)

BUILTIN_MODULES = [
    JURIDICO_CORE,
    LEGISLATIVO,
    JURISPRUDENCIA,
    CADASTRO_RISCO,
    CONSULTORIA_TRIBUTARIA,
]
