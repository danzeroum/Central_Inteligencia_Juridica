"""Factory de aplicação FastAPI — criação, middlewares e inclusão de routers."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.config import _csv_env
from src.api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from src.utils.request_context import get_correlation_id
from src.utils.tracing import configure_tracing

logger = logging.getLogger(__name__)

_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def create_app() -> FastAPI:
    """Cria e configura a instância FastAPI com todos os middlewares e routers."""

    app = FastAPI(title="Central Inteligência Jurídica")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_csv_env(
            "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ),
        allow_credentials=True,
        allow_methods=_csv_env("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE,OPTIONS"),
        allow_headers=_csv_env("CORS_ALLOW_HEADERS", "Authorization,Content-Type"),
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    configure_tracing(app)

    # Onda 1 — routers originais
    from src.api.auth_endpoints import router as auth_router
    from src.api.autonomy_endpoints import router as autonomy_router
    from src.api.hitl_endpoints import router as hitl_router
    from src.api.intelligence_endpoints import router as intelligence_router
    from src.api.intelligence_graphql.schema import create_graphql_router
    from src.api.jurisprudencia_endpoints import router as jurisprudencia_router
    from src.api.ledger_endpoints import router as ledger_router
    from src.api.lgpd_endpoints import router as lgpd_router
    from src.api.monitoring_endpoints import router as monitoring_router
    from src.api.profile_endpoints import router as profile_router
    from src.api.training_endpoints import router as training_router

    app.include_router(auth_router)
    app.include_router(hitl_router)
    app.include_router(training_router)
    app.include_router(ledger_router)
    app.include_router(lgpd_router)
    app.include_router(autonomy_router)
    app.include_router(monitoring_router)
    app.include_router(jurisprudencia_router)
    app.include_router(profile_router)
    app.include_router(intelligence_router)
    app.include_router(
        create_graphql_router(),
        prefix="/api/v1/intelligence/graphql",
    )

    # Onda 2 — routers decompostos do god module
    from src.api.routes.a2a import router as a2a_router
    from src.api.routes.agents import router as agents_router
    from src.api.routes.jobs import router as jobs_router
    from src.api.routes.legislative import router as legislative_router
    from src.api.routes.modules import router as modules_router
    from src.api.routes.slots import router as slots_router
    from src.api.routes.system import router as system_router
    from src.api.routes.tasks import router as tasks_router

    app.include_router(agents_router)
    app.include_router(a2a_router)
    app.include_router(tasks_router)
    app.include_router(legislative_router)
    app.include_router(system_router)
    app.include_router(modules_router)
    app.include_router(slots_router)
    app.include_router(jobs_router)

    # Bloco A — Quick Wins Fiscais
    from src.api.routes.fiscal import router as fiscal_router

    app.include_router(fiscal_router)

    # Bloco B — Ingestão & Normalização
    from src.api.routes.upload import router as upload_router

    app.include_router(upload_router)

    # Bloco F.1 — Cofre de credenciais (S-F.1)
    from src.api.routes.vault import router as vault_router

    app.include_router(vault_router)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        correlation_id = get_correlation_id() or uuid.uuid4().hex
        logger.error(
            "Erro não tratado [%s] em %s %s: %s",
            correlation_id,
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": 500,
                "title": "Internal Server Error",
                "detail": f"Erro interno. Referência para suporte: {correlation_id}",
            },
        )

    spa_dir = os.path.join(_static_dir, "spa")
    if os.path.isdir(spa_dir):
        app.mount("/app", StaticFiles(directory=spa_dir, html=True), name="spa")
    else:
        logger.info("SPA não encontrada em %s (rode 'npm run build').", spa_dir)

    return app
