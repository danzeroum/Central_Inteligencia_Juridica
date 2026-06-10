"""Provider de credenciais para adaptadores (Onda 2 ready).

Onda 1: EnvCredentialProvider lê INTEGRATIONS_{SOURCE}_API_KEY etc.
Onda 2: implementar vault/DB multi-tenant substituindo EnvCredentialProvider.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceCredentials:
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token: Optional[str] = None
    extra: Optional[dict] = None


class CredentialProvider(ABC):
    @abstractmethod
    def get_credentials(
        self, source: str, tenant_id: Optional[str] = None
    ) -> Optional[SourceCredentials]:
        ...


class EnvCredentialProvider(CredentialProvider):
    """Lê credenciais de variáveis de ambiente."""

    def get_credentials(
        self, source: str, tenant_id: Optional[str] = None
    ) -> Optional[SourceCredentials]:
        prefix = f"INTEGRATIONS_{source.upper()}"
        api_key = os.getenv(f"{prefix}_API_KEY")
        client_id = os.getenv(f"{prefix}_CLIENT_ID")
        client_secret = os.getenv(f"{prefix}_CLIENT_SECRET")
        if not any([api_key, client_id, client_secret]):
            return None
        return SourceCredentials(
            api_key=api_key,
            client_id=client_id,
            client_secret=client_secret,
        )


_provider: Optional[CredentialProvider] = None


def get_credential_provider() -> CredentialProvider:
    global _provider
    if _provider is None:
        _provider = EnvCredentialProvider()
    return _provider


__all__ = [
    "SourceCredentials",
    "CredentialProvider",
    "EnvCredentialProvider",
    "get_credential_provider",
]
