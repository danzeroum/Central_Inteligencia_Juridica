"""Endpoints do cofre de credenciais (S-F.1).

RBAC:
  - vault:read   → ADMIN, AUDITOR (ler metadados, sem payload)
  - vault:write  → ADMIN (armazenar/rotacionar/excluir)
  - vault:rotate → ADMIN (rotacionar credencial — subconjunto de write)

Regras de segurança:
  - O payload decifrado NUNCA é retornado via API (apenas metadados).
  - Certificados: apenas o caminho do arquivo é aceito — não o conteúdo.
  - Todas as operações são registradas no log com usuário e tenant.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from src.api.rbac import Principal, require_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vault", tags=["Credential Vault"])

# ─────────────────────────────────────────────────────────────────────────────
# RBAC extension (adicionado ao ROLE_PERMISSIONS em rbac.py)
# ─────────────────────────────────────────────────────────────────────────────
# vault:read   → admin, auditor
# vault:write  → admin
# vault:rotate → admin
# (registradas em src/api/rbac.py)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────


class StoreRequest(BaseModel):
    source: str
    tenant_id: str
    payload: Dict[str, Any]
    cert_path: Optional[str] = None

    @field_validator("source")
    @classmethod
    def source_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source não pode ser vazio")
        return v.strip().lower()

    @field_validator("cert_path")
    @classmethod
    def cert_path_seguro(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Rejeita caminhos que parecem conteúdo de certificado (PEM/DER base64)
        if v.strip().startswith("-----BEGIN") or len(v) > 512:
            raise ValueError(
                "cert_path deve ser um caminho de arquivo, não conteúdo de certificado."
            )
        return v.strip()

    @field_validator("payload")
    @classmethod
    def payload_sem_cert_conteudo(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        for key, val in v.items():
            if isinstance(val, str) and val.strip().startswith("-----BEGIN"):
                raise ValueError(
                    f"Payload não pode conter conteúdo de certificado (campo '{key}'). "
                    "Use cert_path com caminho de arquivo."
                )
        return v


class RotateRequest(BaseModel):
    source: str
    tenant_id: str
    new_payload: Dict[str, Any]

    @field_validator("new_payload")
    @classmethod
    def payload_sem_cert_conteudo(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        for key, val in v.items():
            if isinstance(val, str) and val.strip().startswith("-----BEGIN"):
                raise ValueError(
                    f"Payload não pode conter conteúdo de certificado (campo '{key}')."
                )
        return v


class SignRequest(BaseModel):
    payload_b64: str
    source: Optional[str] = None
    tenant_id: Optional[str] = None


class VaultMetadata(BaseModel):
    slot_id: str
    source: str
    tenant_id: str
    created_at: float
    rotated_at: Optional[float]
    has_cert_path: bool


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/store",
    status_code=status.HTTP_201_CREATED,
    summary="Armazena credencial cifrada no cofre (S-F.1)",
)
async def store_credential(
    body: StoreRequest,
    principal: Principal = Depends(require_permissions("vault:write")),
) -> Dict[str, str]:
    try:
        from src.integrations.vault import get_vault

        slot_id = get_vault().store(
            source=body.source,
            tenant_id=body.tenant_id,
            payload=body.payload,
            cert_path=body.cert_path,
        )
        logger.info(
            "vault store: source=%s tenant=%s user=%s",
            body.source,
            body.tenant_id,
            principal.user_id,
        )
        return {"status": "stored", "slot_id": slot_id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("vault store [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )


@router.post(
    "/rotate",
    summary="Rotaciona credencial (substitui payload, mantém histórico de timestamps) (S-F.1)",
)
async def rotate_credential(
    body: RotateRequest,
    principal: Principal = Depends(require_permissions("vault:rotate")),
) -> Dict[str, Any]:
    try:
        from src.integrations.vault import get_vault

        existed = get_vault().rotate(
            source=body.source,
            tenant_id=body.tenant_id,
            new_payload=body.new_payload,
        )
        logger.info(
            "vault rotate: source=%s tenant=%s existed=%s user=%s",
            body.source,
            body.tenant_id,
            existed,
            principal.user_id,
        )
        return {"status": "rotated", "existed": existed}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("vault rotate [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno. Referência: {cid}",
        )


@router.get(
    "/metadata",
    response_model=VaultMetadata,
    summary="Metadados de uma credencial (sem payload) (S-F.1)",
)
async def get_metadata(
    source: str,
    tenant_id: str,
    principal: Principal = Depends(require_permissions("vault:read")),
) -> VaultMetadata:
    from src.integrations.vault import get_vault

    meta = get_vault().metadata(source, tenant_id)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credencial não encontrada: source={source} tenant={tenant_id}",
        )
    return VaultMetadata(**meta)


@router.delete(
    "/delete",
    summary="Remove credencial do cofre (S-F.1)",
)
async def delete_credential(
    source: str,
    tenant_id: str,
    principal: Principal = Depends(require_permissions("vault:write")),
) -> Dict[str, Any]:
    from src.integrations.vault import get_vault

    existed = get_vault().delete(source, tenant_id)
    logger.info(
        "vault delete: source=%s tenant=%s existed=%s user=%s",
        source,
        tenant_id,
        existed,
        principal.user_id,
    )
    if not existed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credencial não encontrada: source={source} tenant={tenant_id}",
        )
    return {"status": "deleted"}


@router.post(
    "/sign",
    summary="Assina payload com certificado digital A1 (S-F.1)",
    description=(
        "Assina o payload (base64) com o certificado configurado em CERT_A1_PATH. "
        "Retorna is_stub=true se nenhum certificado real estiver configurado."
    ),
)
async def sign_payload_endpoint(
    body: SignRequest,
    principal: Principal = Depends(require_permissions("vault:write")),
) -> Dict[str, Any]:
    import base64 as _b64

    try:
        payload_bytes = _b64.b64decode(body.payload_b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="payload_b64 deve ser base64 válido.",
        )

    try:
        from src.integrations.digital_signature import sign_payload

        result = sign_payload(payload_bytes)
        logger.info(
            "vault sign: user=%s cn=%s is_stub=%s",
            principal.user_id,
            result.subject_cn,
            result.is_stub,
        )
        return {
            "signature_b64": result.signature_b64,
            "algorithm": result.algorithm,
            "subject_cn": result.subject_cn,
            "serial_number": result.serial_number,
            "is_stub": result.is_stub,
        }
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("vault sign [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao assinar. Referência: {cid}",
        )
