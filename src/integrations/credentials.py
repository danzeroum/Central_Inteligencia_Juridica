"""Provider de credenciais para adaptadores (S-F.1 — Vault integrado).

Hierarquia de providers:
  1. VaultCredentialProvider  — lê do cofre cifrado (Onda 2, produção)
  2. EnvCredentialProvider    — lê de variáveis de ambiente (Onda 1, legacy)

Uso:
    from src.integrations.credentials import get_credential_provider
    creds = get_credential_provider().get_credentials("ecac", tenant_id="abc")

Seleciona VaultCredentialProvider automaticamente quando VAULT_MASTER_KEY está
definida; caso contrário usa EnvCredentialProvider para compatibilidade.
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
    ) -> Optional[SourceCredentials]: ...


class EnvCredentialProvider(CredentialProvider):
    """Lê credenciais de variáveis de ambiente (compatibilidade Onda 1)."""

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


class VaultCredentialProvider(CredentialProvider):
    """Lê credenciais do cofre cifrado (S-F.1).

    Usa ``src.integrations.vault.get_vault()`` para descifrar o payload e
    constrói um ``SourceCredentials``. Cai para ``EnvCredentialProvider`` se
    a credencial não estiver no cofre.
    """

    def __init__(self) -> None:
        self._fallback = EnvCredentialProvider()

    def get_credentials(
        self, source: str, tenant_id: Optional[str] = None
    ) -> Optional[SourceCredentials]:
        from src.integrations.vault import get_vault

        tid = tenant_id or "default"
        vault = get_vault()
        payload = vault.retrieve(source, tid)
        if payload:
            return SourceCredentials(
                api_key=payload.get("api_key"),
                client_id=payload.get("client_id"),
                client_secret=payload.get("client_secret"),
                token=payload.get("token"),
                extra={
                    k: v
                    for k, v in payload.items()
                    if k not in ("api_key", "client_id", "client_secret", "token")
                },
            )
        # Fallback a env (compatibilidade com Onda 1)
        return self._fallback.get_credentials(source, tenant_id)


_provider: Optional[CredentialProvider] = None


def get_credential_provider() -> CredentialProvider:
    """Retorna o provider ativo: Vault quando VAULT_MASTER_KEY configurada."""
    global _provider
    if _provider is None:
        if os.environ.get("VAULT_MASTER_KEY"):
            _provider = VaultCredentialProvider()
        else:
            _provider = EnvCredentialProvider()
    return _provider


def reset_provider() -> None:
    """Força recriação do provider. Útil em testes."""
    global _provider
    _provider = None


__all__ = [
    "SourceCredentials",
    "CredentialProvider",
    "EnvCredentialProvider",
    "VaultCredentialProvider",
    "get_credential_provider",
    "reset_provider",
]
