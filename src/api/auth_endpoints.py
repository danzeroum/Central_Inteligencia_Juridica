"""Endpoint de autenticação — emissão de JWT (base para o login real da SPA).

SECURITY (CRÍTICO-09): a SPA não tinha como autenticar de verdade porque não
existia um endpoint de login. Este módulo emite um JWT assinado a partir de
credenciais válidas, aplicando a política de papéis/timeout do RBAC.

Store de usuários (stateless/cloud-friendly): lido de ``AUTH_USERS`` (JSON) —
``{"usuario": {"password": "...", "roles": ["operator"]}, ...}``. Em produção a
variável é OBRIGATÓRIA; em ``development``/``test`` há defaults de conveniência.
A senha é comparada em tempo constante (``secrets.compare_digest``).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.api.rbac import issue_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=256)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    roles: List[str]


def _load_users() -> Dict[str, Dict[str, object]]:
    """Carrega o store de usuários de ``AUTH_USERS`` ou usa defaults de dev/test."""

    raw = os.getenv("AUTH_USERS")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k): v for k, v in data.items()}
            logger.error("AUTH_USERS deve ser um objeto JSON {usuario: {...}}")
        except (ValueError, TypeError) as exc:  # pragma: no cover - config inválida
            logger.error("AUTH_USERS inválido: %s", exc)
        return {}

    env = os.getenv("ENVIRONMENT", "development").strip().lower()
    if env in ("development", "test"):
        return {
            "admin": {"password": "admin", "roles": ["admin"]},
            "operator": {"password": "operator", "roles": ["operator"]},
            "auditor": {"password": "auditor", "roles": ["auditor"]},
        }
    return {}


def _verify_credentials(username: str, password: str) -> Optional[List[str]]:
    """Retorna os papéis do usuário se as credenciais conferirem; senão ``None``."""

    record = _load_users().get(username)
    expected = str(record.get("password", "")) if record else ""
    # Compara sempre (mesmo sem usuário) para reduzir o sinal de timing.
    candidate = expected or secrets.token_urlsafe(16)
    ok = bool(expected) and secrets.compare_digest(password, candidate)
    if not ok:
        return None
    roles = record.get("roles") or ["operator"]
    return [str(r) for r in roles]


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    """Valida credenciais e emite um JWT (com papéis e timeout do RBAC)."""

    roles = _verify_credentials(payload.username, payload.password)
    if roles is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )
    token = issue_token(payload.username, roles)
    logger.info("Login bem-sucedido para '%s' (roles=%s)", payload.username, roles)
    return LoginResponse(access_token=token, user_id=payload.username, roles=roles)


__all__ = ["router"]
