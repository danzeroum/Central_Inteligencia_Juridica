"""Helpers compartilhados entre os módulos de rota.

Funções que eram privadas em main.py e usadas em múltiplos handlers.
"""

from __future__ import annotations

import base64
import re
from typing import Optional

from fastapi import HTTPException, status

from src.api.rbac import Principal

# SECURITY (P0-5): allowlist estrito para identificadores de agente A2A.
_AGENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


def validate_agent_id(agent_id: str, field: str) -> str:
    """Valida um identificador de agente A2A contra o allowlist estrito."""

    if not isinstance(agent_id, str) or not _AGENT_ID_PATTERN.match(agent_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Identificador de agente inválido em '{field}'",
        )
    return agent_id


def enforce_agent_identity(sender_id: str, principal: Principal) -> None:
    """SECURITY (IAM-002): amarra o sender_id à identidade autenticada."""

    if principal.is_anonymous or principal.has_permission("agents:manage"):
        return
    if sender_id != principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="sender_id não corresponde à identidade autenticada",
        )


def encode_cursor(offset: int) -> str:
    """Codifica offset de paginação em cursor opaco (base64)."""

    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")


def decode_cursor(cursor: Optional[str]) -> int:
    """Decodifica cursor opaco em offset inteiro."""

    if not cursor:
        return 0
    try:
        offset = int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii"))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="cursor inválido"
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="cursor inválido"
        )
    return offset
