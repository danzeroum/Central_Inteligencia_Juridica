"""Encryption key provisioning with a KMS-ready abstraction.

CLOUD-READINESS: o ``KeyProvider`` é o ponto de extensão para gestão de chaves.
Hoje (Docker) usamos ``EnvKeyProvider``, que lê a chave de uma variável de
ambiente. Ao migrar para a nuvem, basta implementar um ``KmsKeyProvider`` (AWS
KMS) ou ``VaultKeyProvider`` (HashiCorp Vault) e trocar o provider em
``get_key_provider`` — nenhum consumidor (ex.: ``CacheManager``) muda, pois todos
dependem apenas da interface ``get_encryption_key()``.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class KeyProvider(Protocol):
    """Fornece a chave de criptografia simétrica (formato Fernet, urlsafe b64)."""

    def get_encryption_key(self) -> Optional[bytes]:
        """Retorna a chave (32 bytes urlsafe-base64) ou ``None`` se ausente."""
        ...


def _normalise_to_fernet_key(raw: str) -> bytes:
    """Converte um segredo arbitrário em uma chave Fernet válida.

    Se ``raw`` já for uma chave Fernet (32 bytes urlsafe-base64), é usada
    diretamente. Caso contrário, derivamos uma via SHA-256 — conveniente para
    desenvolvimento, mas em produção recomenda-se gerar com
    ``Fernet.generate_key()`` e injetar via segredo gerenciado.
    """

    candidate = raw.strip().encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(candidate)
        if len(decoded) == 32:
            return candidate
    except Exception:  # noqa: BLE001 - qualquer falha cai no derivador
        pass
    digest = hashlib.sha256(candidate).digest()
    return base64.urlsafe_b64encode(digest)


class EnvKeyProvider:
    """Lê a chave de criptografia da variável de ambiente ``CACHE_ENCRYPTION_KEY``."""

    def __init__(self, env_var: str = "CACHE_ENCRYPTION_KEY") -> None:
        self._env_var = env_var

    def get_encryption_key(self) -> Optional[bytes]:
        raw = os.getenv(self._env_var)
        if not raw:
            return None
        return _normalise_to_fernet_key(raw)


# --- Seam para a nuvem (não implementado nesta entrega) ----------------------
# class KmsKeyProvider:
#     """Recupera a chave de dados do AWS KMS / Vault.
#
#     Implementar ``get_encryption_key`` chamando ``kms.decrypt`` sobre uma data
#     key cifrada (envelope encryption) e devolvendo o plaintext em formato
#     Fernet. Trocar ``get_key_provider`` para retornar esta classe quando
#     ``KEY_PROVIDER=kms``.
#     """


_provider: Optional[KeyProvider] = None


def get_key_provider() -> KeyProvider:
    """Retorna o ``KeyProvider`` configurado (env por padrão)."""

    global _provider
    if _provider is None:
        # KEY_PROVIDER permite futura seleção (env | kms | vault) sem refatorar.
        provider_name = os.getenv("KEY_PROVIDER", "env").strip().lower()
        if provider_name != "env":  # pragma: no cover - seam para a nuvem
            logger.warning(
                "KEY_PROVIDER=%s ainda não implementado; usando EnvKeyProvider.",
                provider_name,
            )
        _provider = EnvKeyProvider()
    return _provider


def reset_key_provider() -> None:
    """Reseta o provider (útil em testes)."""

    global _provider
    _provider = None


__all__ = [
    "KeyProvider",
    "EnvKeyProvider",
    "get_key_provider",
    "reset_key_provider",
]
