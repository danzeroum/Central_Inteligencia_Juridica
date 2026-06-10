"""Contexto GraphQL: injeta Principal a partir do JWT."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Request
from strawberry.fastapi import BaseContext

from src.api.rbac import Principal, current_principal


class IntelligenceContext(BaseContext):
    def __init__(self, principal: Principal) -> None:
        super().__init__()
        self.principal = principal


async def get_context(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> IntelligenceContext:
    return IntelligenceContext(principal=principal)
