"""Adaptador Receita Federal / BrasilAPI — perfil societário completo.

Endpoint: GET https://brasilapi.com.br/api/cnpj/v1/{cnpj}
Retorna: situação cadastral, QSA, capital social, CNAE, porte, Simples/MEI.
"""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar, Dict, List, Optional, Set

import httpx
from pydantic import BaseModel

from src.integrations.base import LegalDataAdapter
from src.integrations.models import (
    EmpresaCadastro,
    IdentifierQuery,
    IdentifierType,
    SocioQSA,
    SourceZone,
)
from src.integrations.settings import SourceSettings

logger = logging.getLogger(__name__)

BRASILAPI_BASE = "https://brasilapi.com.br/api/cnpj/v1"


def _digits(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def _parse_qsa(qsa_raw: List[Dict[str, Any]]) -> List[SocioQSA]:
    socios = []
    for s in qsa_raw or []:
        nome = s.get("nome_socio") or s.get("nome") or ""
        qual = s.get("qualificacao_socio") or s.get("qualificacao") or ""
        identificador = s.get("cnpj_cpf_do_socio") or s.get("cpf_representante_legal") or ""
        # Determina tipo pelo comprimento do identificador (mascarado pode vir como ***.***.***-00)
        d = _digits(identificador)
        if len(d) == 14:
            tipo = "PJ"
        elif len(d) <= 11:
            tipo = "PF"
        else:
            tipo = None
        socios.append(
            SocioQSA(
                nome=nome,
                qualificacao=qual,
                tipo=tipo,
                identificador_mascarado=identificador if identificador else None,
                data_entrada=s.get("data_entrada_sociedade"),
            )
        )
    return socios


def _parse_empresa(data: Dict[str, Any]) -> EmpresaCadastro:
    cnpj = _digits(data.get("cnpj", ""))
    capital_raw = data.get("capital_social")
    capital = None
    if capital_raw is not None:
        try:
            capital = float(capital_raw)
        except (ValueError, TypeError):
            pass

    cnae_principal = None
    if data.get("cnae_fiscal"):
        cnae_principal = {
            "codigo": data.get("cnae_fiscal"),
            "descricao": data.get("cnae_fiscal_descricao", ""),
        }

    cnaes_secundarios = [
        {"codigo": c.get("codigo"), "descricao": c.get("descricao", "")}
        for c in (data.get("cnaes_secundarias") or [])
    ]

    nat_juridica = None
    if data.get("natureza_juridica"):
        nat_juridica = {
            "codigo": data.get("codigo_natureza_juridica"),
            "descricao": data.get("natureza_juridica"),
        }

    simples = data.get("opcao_pelo_simples")
    mei = data.get("opcao_pelo_mei")
    if isinstance(simples, str):
        simples = simples.strip().upper() in ("SIM", "S", "TRUE", "1")
    if isinstance(mei, str):
        mei = mei.strip().upper() in ("SIM", "S", "TRUE", "1")

    return EmpresaCadastro(
        cnpj=cnpj,
        razao_social=data.get("razao_social"),
        nome_fantasia=data.get("nome_fantasia"),
        situacao_cadastral=data.get("descricao_situacao_cadastral")
        or str(data.get("situacao_cadastral", "")),
        data_abertura=data.get("data_inicio_atividade"),
        capital_social=capital,
        porte=data.get("descricao_porte") or data.get("porte"),
        cnae_principal=cnae_principal,
        cnaes_secundarios=cnaes_secundarios,
        opcao_simples=simples,
        opcao_mei=mei,
        uf=data.get("uf"),
        municipio=data.get("municipio"),
        natureza_juridica=nat_juridica,
        qsa=_parse_qsa(data.get("qsa") or []),
    )


class ReceitaCnpjAdapter(LegalDataAdapter):
    """Adaptador BrasilAPI/Receita Federal — perfil societário (CNPJ Light)."""

    service_name: ClassVar[str] = "receita_cnpj"
    zone: ClassVar[SourceZone] = SourceZone.PUBLICA
    data_type: ClassVar[str] = "cadastro_empresa"
    supported_identifiers: ClassVar[Set[IdentifierType]] = {IdentifierType.CNPJ}
    item_model: ClassVar = EmpresaCadastro

    async def fetch_real(self, q: IdentifierQuery) -> List[BaseModel]:
        cnpj = _digits(q.identifier)
        url = f"{BRASILAPI_BASE}/{cnpj}"

        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        return [_parse_empresa(data)]
