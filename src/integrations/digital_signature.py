"""Serviço de assinatura digital A1/A3 (S-F.1).

Assina payloads com certificado PKCS12 (A1) carregado de CAMINHO de arquivo
(volume montado em produção). O arquivo do certificado NUNCA é armazenado em
repo, imagem Docker ou variável de ambiente.

Ambiente de produção/homologação:
    CERT_A1_PATH=/run/secrets/cert.p12   # volume/secret montado
    CERT_A1_PASSPHRASE=...               # variável de ambiente (não em repo)

Sem certificado configurado (dev/testes): assina com chave RSA efêmera e
retorna ``is_stub=True`` no resultado — adequado para validar o fluxo sem cert.

Algoritmo: RSA-PSS / SHA-256 (conforme Nota Técnica EICP-NT-2024-001 para
assinatura de documentos fiscais eletrônicos).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_CERT_PATH_ENV = "CERT_A1_PATH"
_CERT_PASS_ENV = "CERT_A1_PASSPHRASE"


@dataclass
class SignatureResult:
    signature_b64: str
    algorithm: str
    subject_cn: str
    serial_number: str
    is_stub: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Real signer (PKCS12 A1)
# ─────────────────────────────────────────────────────────────────────────────


def _sign_with_pkcs12(
    payload: bytes, cert_path: str, passphrase: Optional[bytes]
) -> SignatureResult:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import pkcs12

    with open(cert_path, "rb") as f:
        pkcs12_data = f.read()

    private_key, cert, _ = pkcs12.load_key_and_certificates(pkcs12_data, passphrase)

    signature = private_key.sign(
        payload,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )

    subject = cert.subject
    cn_attr = subject.get_attributes_for_oid(
        __import__("cryptography.x509.oid", fromlist=["NameOID"]).NameOID.COMMON_NAME
    )
    cn = cn_attr[0].value if cn_attr else "desconhecido"
    serial = str(cert.serial_number)

    return SignatureResult(
        signature_b64=base64.b64encode(signature).decode(),
        algorithm="RSA-PSS/SHA-256",
        subject_cn=cn,
        serial_number=serial,
        is_stub=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stub signer (sem certificado real — dev/testes/homologação sem cert)
# ─────────────────────────────────────────────────────────────────────────────


def _sign_stub(payload: bytes) -> SignatureResult:
    """Assina com RSA efêmera de 2048 bits. Resultado não é juridicamente válido."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signature = private_key.sign(
        payload,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return SignatureResult(
        signature_b64=base64.b64encode(signature).decode(),
        algorithm="RSA-PSS/SHA-256",
        subject_cn="STUB-CERT-DEV",
        serial_number="0",
        is_stub=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def sign_payload(payload: bytes) -> SignatureResult:
    """Assina ``payload`` com o certificado configurado ou stub.

    Lê ``CERT_A1_PATH`` e ``CERT_A1_PASSPHRASE`` do ambiente. Se não estiverem
    definidos, cai para o stub (``is_stub=True``).
    """
    cert_path = os.environ.get(_CERT_PATH_ENV, "").strip()
    passphrase_raw = os.environ.get(_CERT_PASS_ENV, "").strip()
    passphrase = passphrase_raw.encode() if passphrase_raw else None

    if cert_path and os.path.isfile(cert_path):
        try:
            result = _sign_with_pkcs12(payload, cert_path, passphrase)
            logger.info(
                "Assinatura digital: CN=%s serial=%s",
                result.subject_cn,
                result.serial_number,
            )
            return result
        except Exception as exc:
            logger.error(
                "Falha ao assinar com certificado real (%s): %s — usando stub",
                cert_path,
                exc,
            )

    logger.warning(
        "Assinatura digital STUB — %s não configurado ou arquivo ausente. "
        "Configure CERT_A1_PATH para produção/homologação.",
        _CERT_PATH_ENV,
    )
    return _sign_stub(payload)


def verify_payload(
    payload: bytes, signature_b64: str, cert_path: Optional[str] = None
) -> bool:
    """Verifica assinatura RSA-PSS. Retorna True se válida."""
    if not cert_path:
        cert_path = os.environ.get(_CERT_PATH_ENV, "").strip()

    if not (cert_path and os.path.isfile(cert_path)):
        logger.warning("verify_payload: certificado não disponível para verificação.")
        return False

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import pkcs12

        passphrase_raw = os.environ.get(_CERT_PASS_ENV, "").strip()
        passphrase = passphrase_raw.encode() if passphrase_raw else None

        with open(cert_path, "rb") as f:
            pkcs12_data = f.read()

        _, cert, _ = pkcs12.load_key_and_certificates(pkcs12_data, passphrase)
        pub_key = cert.public_key()
        signature = base64.b64decode(signature_b64)

        pub_key.verify(
            signature,
            payload,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except Exception as exc:
        logger.debug("verify_payload: %s", exc)
        return False


__all__ = ["SignatureResult", "sign_payload", "verify_payload"]
