"""Role-Based Access Control (RBAC) para a API.

SECURITY (IAM-001): introduz perfis e permissões sobre o ``AuthManager`` (que
até então só autenticava — sem autorização). As permissões são derivadas dos
papéis carregados no próprio JWT (claim ``roles``), mantendo a autorização
*stateless* e cloud-friendly (sem consulta a um store de usuários).

Compatibilidade: quando a autenticação está desligada (``AuthManager.REQUIRED``
= ``False``, usado em dev/testes), as checagens de permissão são relaxadas —
mesmo princípio do acesso "anonymous" já existente. Em produção
(``AUTH_REQUIRED=true``) as permissões são efetivamente exigidas.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, List, Sequence, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from src.api.auth import AuthManager, security


class Role(str, Enum):
    """Perfis de acesso suportados."""

    ADMIN = "admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    READONLY = "readonly"


# Mapa perfil → permissões. Permissões usam o formato ``recurso:ação``.
ROLE_PERMISSIONS: dict[Role, Set[str]] = {
    Role.ADMIN: {
        "hitl:write",
        "agents:read",
        "agents:manage",
        "config:write",
        "lgpd:read",
        "lgpd:write",
        "ledger:read",
        "monitoring:read",
        # API-06: comparação de modos (2× custo LLM) é operação privilegiada.
        "tasks:compare",
        # Inteligência jurídica (Onda 1)
        "intelligence:query",
        "intelligence:zone:credenciada",
        # S-F.1: cofre de credenciais
        "vault:read",
        "vault:write",
        "vault:rotate",
        # S-F.2: PER/DCOMP
        "per_dcomp:generate",
        "per_dcomp:validate",
        # S-E.2: relatórios premium + workbench
        "reports:read",
        "workbench:execute",
        "workbench:admin",
    },
    Role.OPERATOR: {
        "hitl:write",
        "agents:read",
        "monitoring:read",
        "intelligence:query",
        # S-F.2: PER/DCOMP
        "per_dcomp:generate",
        "per_dcomp:validate",
        # S-E.2: relatórios + workbench (leitura/execução, não admin)
        "reports:read",
        "workbench:execute",
    },
    Role.AUDITOR: {
        "ledger:read",
        "lgpd:read",
        "monitoring:read",
        # S-F.1: cofre de credenciais (somente leitura)
        "vault:read",
        # S-F.2: auditor pode validar (somente leitura)
        "per_dcomp:validate",
        # S-E.2: relatórios (somente leitura)
        "reports:read",
    },
    Role.READONLY: {"monitoring:read"},
}

# Papéis atribuídos a um token que não traz a claim ``roles`` (tokens legados).
# Propositadamente NÃO incluem admin: operações sensíveis (LGPD, config) exigem
# um token emitido explicitamente com o papel apropriado.
DEFAULT_ROLES: List[Role] = [Role.OPERATOR]

# SECURITY (BACEN 4.658): papéis com acesso de escrita/leitura sensível são
# considerados "privilegiados" e recebem um timeout de sessão mais curto. Apenas
# ``readonly`` é não-privilegiado.
PRIVILEGED_ROLES: Set[Role] = {Role.ADMIN, Role.OPERATOR, Role.AUDITOR}


def privileged_expiry_minutes() -> int:
    """Timeout (min) para tokens privilegiados (``JWT_PRIVILEGED_EXPIRY_MINUTES``)."""

    return int(os.getenv("JWT_PRIVILEGED_EXPIRY_MINUTES", "15"))


def is_privileged(roles: Iterable[Role]) -> bool:
    return any(role in PRIVILEGED_ROLES for role in roles)


def issue_token(user_id: str, roles: Sequence[str]) -> str:
    """Emite um JWT aplicando a política de timeout conforme o privilégio.

    Operações privilegiadas (admin/operator/auditor) recebem um token de vida
    curta (``JWT_PRIVILEGED_EXPIRY_MINUTES``, padrão 15 min); demais usam o
    padrão (``JWT_EXPIRY_MINUTES``, 30 min). Centraliza a regra de sessão.
    """

    coerced = _coerce_roles(roles)
    minutes = (
        privileged_expiry_minutes()
        if is_privileged(coerced)
        else AuthManager.EXPIRY_MINUTES
    )
    return AuthManager.create_token(
        user_id, roles=[r.value for r in coerced], expires_in_minutes=minutes
    )


def _coerce_roles(raw: Iterable[object]) -> List[Role]:
    roles: List[Role] = []
    for item in raw:
        try:
            roles.append(Role(str(item).strip().lower()))
        except ValueError:
            # Papel desconhecido é ignorado (não concede permissões).
            continue
    return roles


def roles_from_payload(payload: dict) -> List[Role]:
    """Extrai os papéis de um payload JWT, caindo para ``DEFAULT_ROLES``."""

    raw = payload.get("roles")
    if not raw:
        return list(DEFAULT_ROLES)
    if isinstance(raw, str):
        raw = [raw]
    coerced = _coerce_roles(raw)
    return coerced or list(DEFAULT_ROLES)


def permissions_for(roles: Iterable[Role]) -> Set[str]:
    """União das permissões concedidas pelos papéis informados."""

    granted: Set[str] = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(role, set())
    return granted


@dataclass
class Principal:
    """Identidade autenticada e seus papéis/permissões."""

    user_id: str
    roles: List[Role] = field(default_factory=list)

    @property
    def permissions(self) -> Set[str]:
        return permissions_for(self.roles)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    @property
    def is_anonymous(self) -> bool:
        return self.user_id == "anonymous"


async def current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Principal:
    """Resolve o :class:`Principal` da requisição a partir do JWT."""

    payload = AuthManager.verify_token_payload(credentials)
    return Principal(
        user_id=str(payload.get("sub", "anonymous")),
        roles=roles_from_payload(payload),
    )


def require_permissions(*permissions: str):
    """Dependência FastAPI que exige as permissões informadas.

    Relaxada quando ``AuthManager.REQUIRED`` é ``False`` (dev/testes): nesse
    modo não há identidade real a autorizar, então a checagem é ignorada — o
    mesmo contrato do acesso anônimo já existente.
    """

    required = set(permissions)

    async def dependency(
        principal: Principal = Depends(current_principal),
    ) -> Principal:
        if not AuthManager.REQUIRED:
            return principal
        granted = principal.permissions
        if not required.issubset(granted):
            missing = sorted(required - granted)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: missing {missing}",
            )
        return principal

    return dependency


__all__ = [
    "Role",
    "ROLE_PERMISSIONS",
    "DEFAULT_ROLES",
    "PRIVILEGED_ROLES",
    "Principal",
    "current_principal",
    "require_permissions",
    "permissions_for",
    "roles_from_payload",
    "is_privileged",
    "privileged_expiry_minutes",
    "issue_token",
]
