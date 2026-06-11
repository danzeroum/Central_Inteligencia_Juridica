"""Configuração centralizada — variáveis de ambiente e inicialização de auth.

Importar este módulo tem o efeito colateral de chamar ``AuthManager.configure()``,
que deve ocorrer antes dos módulos de rota e dos singletons de agente.
``main.py`` é o único entry point que garante esta ordem.
"""

from __future__ import annotations

import os
from typing import List

from src.api.auth import AuthManager


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _csv_env(name: str, default: str) -> List[str]:
    return [
        item.strip() for item in os.getenv(name, default).split(",") if item.strip()
    ]


ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()

# SECURITY (SEC-001): JWT exigido por padrão; relaxado em ENVIRONMENT=test.
AUTH_REQUIRED: bool = _env_flag("AUTH_REQUIRED", default=ENVIRONMENT != "test")

# Efeito colateral intencional: configura o AuthManager antes de qualquer rota.
AuthManager.configure(required=AUTH_REQUIRED)
