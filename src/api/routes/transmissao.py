"""Endpoints de transmissão PER/DCOMP ao e-CAC (S-F.3).

RBAC:
  - transmissao:enviar    → ADMIN, OPERATOR
  - transmissao:consultar → ADMIN, OPERATOR, AUDITOR

Segurança:
  - Modo stub quando ECAC_HOMOLOGACAO_URL / CERT_A1_PATH não configurados.
  - Idempotência: mesmo ficha_id + XML → mesmo resultado.
  - Falha de transmissão não corrompe estado: resultado ERRO retornado, não exceção.
  - Circuit breaker: após 3 falhas → 503 com retry_after.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from src.api.rbac import Principal, require_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fiscal/transmissao", tags=["Transmissão e-CAC"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────


class EnviarRequest(BaseModel):
    # Contrato completo (original)
    ficha_id: Optional[str] = None
    tipo_ficha: Optional[str] = None
    cnpj_masked: Optional[str] = None
    xml_b64: Optional[str] = None
    # Contrato simplificado (frontend envia escrituracao_id + ambiente)
    escrituracao_id: Optional[str] = None
    ambiente: Optional[str] = None

    @field_validator("xml_b64", mode="before")
    @classmethod
    def xml_valido(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import base64

        try:
            decoded = base64.b64decode(v)
            if not decoded.strip():
                raise ValueError("xml_b64 decodifica para conteúdo vazio.")
        except Exception as exc:
            raise ValueError(f"xml_b64 deve ser base64 válido: {exc}")
        return v


class TransmissaoResponse(BaseModel):
    transmissao_id: str
    ficha_id: str
    situacao: str
    protocolo: Optional[str]
    mensagem: Optional[str]
    is_stub: bool
    enviado_em: str
    atualizado_em: str


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/enviar",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Transmite ficha PER/DCOMP ao e-CAC (homologação) (S-F.3)",
    description=(
        "Envia o XML da ficha PER/DCOMP ao webservice SOAP do e-CAC. "
        "Retorna is_stub=true quando ECAC_HOMOLOGACAO_URL ou CERT_A1_PATH "
        "não estiverem configurados. Idempotente: mesmo ficha_id+XML retorna "
        "resultado já registrado."
    ),
)
async def enviar_transmissao(
    body: EnviarRequest,
    principal: Principal = Depends(require_permissions("transmissao:enviar")),
) -> Dict[str, Any]:
    import base64
    import datetime

    # Contrato simplificado: apenas escrituracao_id + ambiente (stub)
    if body.escrituracao_id and not body.xml_b64:
        try:
            tx_id = str(uuid.uuid4())
            protocolo = f"PROT-{tx_id[:8].upper()}"
            now = datetime.datetime.utcnow().isoformat()
            logger.info(
                "transmissao enviar stub: escrituracao_id=%s ambiente=%s user=%s",
                body.escrituracao_id,
                body.ambiente,
                principal.user_id,
            )
            return {
                "transmissao_id": tx_id,
                "ficha_id": body.escrituracao_id,
                "situacao": "transmitido",
                "protocolo": protocolo,
                "recibo": f"REC-{tx_id[-8:].upper()}",
                "mensagem": f"Transmissão em {body.ambiente or 'homologacao'} (stub)",
                "is_stub": True,
                "ambiente": body.ambiente or "homologacao",
                "enviado_em": now,
                "atualizado_em": now,
            }
        except Exception as exc:
            cid = uuid.uuid4().hex
            logger.error("transmissao enviar stub [%s]: %s", cid, exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro interno (stub). Referência: {cid}",
            )

    # Contrato completo: valida campos obrigatórios
    if not body.xml_b64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Forneça xml_b64 + ficha_id, ou apenas escrituracao_id.",
        )

    from src.integrations.ecac.adapter import get_ecac_adapter
    from src.integrations.ecac.models import SolicitacaoTransmissao

    try:
        xml_content = base64.b64decode(body.xml_b64).decode("utf-8")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="xml_b64 inválido.",
        )

    solicitacao = SolicitacaoTransmissao(
        ficha_id=body.ficha_id,
        tipo_ficha=body.tipo_ficha,
        cnpj_masked=body.cnpj_masked,
        xml_content=xml_content,
        correlation_id=uuid.uuid4().hex,
    )

    try:
        adapter = get_ecac_adapter()
        resultado = adapter.transmitir(solicitacao)
        logger.info(
            "transmissao enviar: tx=%s ficha=%s situacao=%s is_stub=%s user=%s",
            resultado.transmissao_id,
            resultado.ficha_id,
            resultado.situacao.value,
            resultado.is_stub,
            principal.user_id,
        )
        return resultado.to_dict()
    except Exception as exc:
        cid = uuid.uuid4().hex
        logger.error("transmissao enviar [%s]: %s", cid, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na transmissão. Referência: {cid}",
        )


@router.get(
    "/status/{transmissao_id}",
    summary="Consulta status de uma transmissão (S-F.3)",
)
async def consultar_status(
    transmissao_id: str,
    principal: Principal = Depends(require_permissions("transmissao:consultar")),
) -> Dict[str, Any]:
    from src.integrations.ecac.adapter import get_ecac_adapter

    adapter = get_ecac_adapter()
    resultado = adapter.consultar_status(transmissao_id)
    if resultado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transmissão não encontrada: {transmissao_id}",
        )
    logger.info(
        "transmissao status: tx=%s situacao=%s user=%s",
        transmissao_id,
        resultado.situacao.value,
        principal.user_id,
    )
    return resultado.to_dict()


@router.get(
    "/historico",
    summary="Lista histórico de transmissões da sessão (S-F.3)",
)
async def listar_historico(
    principal: Principal = Depends(require_permissions("transmissao:consultar")),
) -> List[Dict[str, Any]]:
    from src.integrations.ecac.adapter import get_ecac_adapter

    adapter = get_ecac_adapter()
    return adapter.historico()


@router.get(
    "/circuit",
    summary="Estado do circuit breaker do e-CAC (S-F.3)",
)
async def circuit_status(
    principal: Principal = Depends(require_permissions("transmissao:consultar")),
) -> Dict[str, Any]:
    from src.integrations.ecac.adapter import get_ecac_adapter

    adapter = get_ecac_adapter()
    cs = adapter.circuit_status()
    cs["is_stub"] = adapter.is_stub
    # Normalise: expose 'open' (bool) and 'status' (str) so callers don't need
    # to know the internal 'state' field name from CircuitBreaker.
    cs["open"] = cs.get("state") == "open"
    cs["status"] = cs.get("state", "closed")
    return cs
