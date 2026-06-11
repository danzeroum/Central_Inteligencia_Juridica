"""Entry point — inicializa logging, configura auth e cria a aplicação FastAPI."""

from __future__ import annotations

from src.utils.logging_config import configure_logging

configure_logging()

import src.api.config as _config  # noqa: F401,E402 — side-effect: AuthManager.configure()

from src.api.app_factory import create_app  # noqa: E402

app = create_app()
