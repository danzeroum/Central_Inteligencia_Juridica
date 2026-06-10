"""Skeleton OAuth2 client-credentials para adaptadores credenciados (Onda 2).

Implementação mínima com cache de token — adaptadores credenciados herdarão daqui.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OAuth2Token:
    access_token: str
    expires_at: float
    token_type: str = "Bearer"

    def is_expired(self, margin_seconds: float = 30.0) -> bool:
        return time.time() >= (self.expires_at - margin_seconds)


class OAuth2ClientCredentials:
    """Cliente client-credentials com cache de token (Onda 2 skeleton)."""

    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
    ) -> None:
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._cached_token: Optional[OAuth2Token] = None

    async def get_token(self) -> str:
        if self._cached_token and not self._cached_token.is_expired():
            return self._cached_token.access_token

        import httpx

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scope:
            payload["scope"] = self.scope

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(self.token_url, data=payload)
            resp.raise_for_status()
            data = resp.json()

        token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._cached_token = OAuth2Token(
            access_token=token,
            expires_at=time.time() + expires_in,
            token_type=data.get("token_type", "Bearer"),
        )
        logger.debug("OAuth2 token obtido para %s (expira em %ds)", self.token_url, expires_in)
        return token

    def invalidate(self) -> None:
        self._cached_token = None


__all__ = ["OAuth2ClientCredentials", "OAuth2Token"]
