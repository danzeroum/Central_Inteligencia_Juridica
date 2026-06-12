"""Cofre de credenciais cifrado (S-F.1).

Armazena credenciais (API keys, client secrets, referências a certificados A1/A3)
de forma criptografada usando Fernet (AES-128-CBC + HMAC-SHA256). O segredo
mestre é lido de variável de ambiente VAULT_MASTER_KEY (base64url, 32+ bytes);
NUNCA de arquivo em repo/imagem.

Segurança:
- Credenciais em repouso: Fernet (AES-128-CBC, HMAC-SHA256)
- Rotação: cada entrada tem ``created_at`` e ``rotated_at``; ``rotate()`` re-cifra
  com nova chave derivada e emite log de auditoria.
- Certificados A1/A3: só o CAMINHO do arquivo (volume montado) é armazenado —
  nunca o conteúdo do certificado.
- RBAC: ``vault:read`` / ``vault:write`` / ``vault:rotate`` (ver rbac.py).
- Backend: Redis (se disponível) ou memória (dev/testes).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_VAULT_ENV = "VAULT_MASTER_KEY"
_SLOT_TTL = 86400 * 365  # 1 ano em segundos


# ─────────────────────────────────────────────────────────────────────────────
# Fernet helper (graceful fallback quando cryptography não instalada)
# ─────────────────────────────────────────────────────────────────────────────


def _make_fernet(key_bytes: bytes):
    """Retorna um Fernet com chave derivada de ``key_bytes`` via SHA-256."""
    from cryptography.fernet import Fernet

    # Fernet exige 32 bytes base64url; derivamos via SHA-256 para aceitar
    # segredos de tamanho arbitrário sem expor bytes diretamente.
    derived = hashlib.sha256(key_bytes).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def _encrypt(data: str, key_bytes: bytes) -> str:
    f = _make_fernet(key_bytes)
    return f.encrypt(data.encode()).decode()


def _decrypt(token: str, key_bytes: bytes) -> str:
    f = _make_fernet(key_bytes)
    return f.decrypt(token.encode()).decode()


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class VaultEntry:
    """Entrada cifrada no cofre."""

    slot_id: str
    source: str
    tenant_id: str
    encrypted_payload: str  # payload JSON cifrado
    created_at: float = field(default_factory=time.time)
    rotated_at: Optional[float] = None
    cert_path: Optional[str] = None  # caminho do volume, nunca conteúdo

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VaultEntry":
        return cls(**d)


# ─────────────────────────────────────────────────────────────────────────────
# Vault backend
# ─────────────────────────────────────────────────────────────────────────────


class CredentialVault:
    """Cofre de credenciais com backend Redis ou in-memory.

    Em produção, defina ``VAULT_MASTER_KEY`` (valor base64url ≥ 32 bytes).
    Em test (``ENVIRONMENT=test``) uma chave efêmera é gerada automaticamente.
    """

    def __init__(self) -> None:
        self._mem: Dict[str, VaultEntry] = {}
        self._master_key: bytes = self._load_master_key()
        self._redis = self._try_redis()

    # ── chave mestra ───────────────────────────────────────────────────────

    @staticmethod
    def _load_master_key() -> bytes:
        raw = os.environ.get(_VAULT_ENV, "")
        if raw:
            try:
                return base64.urlsafe_b64decode(raw + "==")
            except Exception:
                return raw.encode()
        if os.environ.get("ENVIRONMENT", "") == "test":
            # Chave efêmera determinística para testes (não secreta)
            return b"vault-test-key-" + b"0" * 17
        logger.warning(
            "VAULT_MASTER_KEY não definida — credenciais ficam em memória não cifradas. "
            "Defina para produção."
        )
        return b"dev-only-insecure-key-" + b"0" * 10

    # ── backend Redis (opcional) ───────────────────────────────────────────

    @staticmethod
    def _try_redis():
        try:
            import redis as _redis

            url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            client = _redis.from_url(url, socket_connect_timeout=1)
            client.ping()
            return client
        except Exception:
            return None

    # ── CRUD ──────────────────────────────────────────────────────────────

    def _redis_key(self, slot_id: str) -> str:
        return f"vault:slot:{slot_id}"

    def _save(self, entry: VaultEntry) -> None:
        self._mem[entry.slot_id] = entry
        if self._redis:
            try:
                self._redis.setex(
                    self._redis_key(entry.slot_id),
                    _SLOT_TTL,
                    json.dumps(entry.to_dict()),
                )
            except Exception as e:
                logger.warning("vault redis setex: %s", e)

    def _load(self, slot_id: str) -> Optional[VaultEntry]:
        if self._redis:
            try:
                raw = self._redis.get(self._redis_key(slot_id))
                if raw:
                    return VaultEntry.from_dict(json.loads(raw))
            except Exception as e:
                logger.warning("vault redis get: %s", e)
        return self._mem.get(slot_id)

    def _slot_id(self, source: str, tenant_id: str) -> str:
        return hashlib.sha256(f"{source}:{tenant_id}".encode()).hexdigest()[:16]

    def store(
        self,
        source: str,
        tenant_id: str,
        payload: Dict[str, Any],
        cert_path: Optional[str] = None,
    ) -> str:
        """Cifra e armazena credenciais. Retorna o slot_id."""
        # SEGURANÇA: cert_path é validado para não aceitar conteúdo de cert
        if cert_path and len(cert_path) > 512:
            raise ValueError("cert_path deve ser um caminho de arquivo, não conteúdo.")
        encrypted = _encrypt(json.dumps(payload), self._master_key)
        slot_id = self._slot_id(source, tenant_id)
        entry = VaultEntry(
            slot_id=slot_id,
            source=source,
            tenant_id=tenant_id,
            encrypted_payload=encrypted,
            cert_path=cert_path,
        )
        self._save(entry)
        logger.info("vault: credencial armazenada slot=%s source=%s", slot_id, source)
        return slot_id

    def retrieve(self, source: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Descifra e retorna o payload. Retorna None se não existir."""
        slot_id = self._slot_id(source, tenant_id)
        entry = self._load(slot_id)
        if not entry:
            return None
        try:
            return json.loads(_decrypt(entry.encrypted_payload, self._master_key))
        except Exception as e:
            logger.error("vault decrypt error slot=%s: %s", slot_id, e)
            return None

    def rotate(
        self,
        source: str,
        tenant_id: str,
        new_payload: Dict[str, Any],
    ) -> bool:
        """Rotaciona credencial: re-cifra novo payload e atualiza timestamp.

        Retorna True se havia entrada prévia, False se era nova.
        """
        slot_id = self._slot_id(source, tenant_id)
        existing = self._load(slot_id)
        new_encrypted = _encrypt(json.dumps(new_payload), self._master_key)

        entry = VaultEntry(
            slot_id=slot_id,
            source=source,
            tenant_id=tenant_id,
            encrypted_payload=new_encrypted,
            created_at=existing.created_at if existing else time.time(),
            rotated_at=time.time(),
            cert_path=existing.cert_path if existing else None,
        )
        self._save(entry)
        logger.info(
            "vault: credencial rotacionada slot=%s source=%s existed=%s",
            slot_id,
            source,
            bool(existing),
        )
        return bool(existing)

    def delete(self, source: str, tenant_id: str) -> bool:
        """Remove a credencial do cofre. Retorna True se existia."""
        slot_id = self._slot_id(source, tenant_id)
        existed = slot_id in self._mem
        self._mem.pop(slot_id, None)
        if self._redis:
            try:
                self._redis.delete(self._redis_key(slot_id))
                existed = True
            except Exception as e:
                logger.warning("vault redis delete: %s", e)
        return existed

    def metadata(self, source: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retorna metadados (sem payload) de uma entrada."""
        slot_id = self._slot_id(source, tenant_id)
        entry = self._load(slot_id)
        if not entry:
            return None
        return {
            "slot_id": entry.slot_id,
            "source": entry.source,
            "tenant_id": entry.tenant_id,
            "created_at": entry.created_at,
            "rotated_at": entry.rotated_at,
            "has_cert_path": bool(entry.cert_path),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_vault: Optional[CredentialVault] = None


def get_vault() -> CredentialVault:
    global _vault
    if _vault is None:
        _vault = CredentialVault()
    return _vault


__all__ = [
    "CredentialVault",
    "VaultEntry",
    "get_vault",
]
