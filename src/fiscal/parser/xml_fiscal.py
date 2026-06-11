"""Parsers XML para documentos fiscais eletrônicos.

Suporta três tipos:
- NF-e  (Nota Fiscal Eletrônica) — namespace portalfiscal.inf.br/nfe
- CT-e  (Conhecimento de Transporte Eletrônico) — namespace portalfiscal.inf.br/cte
- NFS-e (Nota Fiscal de Serviço Eletrônica) — padrão ABRASF ou sem namespace

Todos os parsers usam defusedxml para prevenir XML-bomb / XXE.
Campos de CNPJ/CPF retornados como-estão (mascaramento é responsabilidade
da camada de persistência — veja src/fiscal/repository.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import defusedxml.ElementTree as ET

# ─────────────────────────────────────────────────────────────────────────────
# Resultado comum
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class XmlParseResult:
    """Resultado do parse de um documento fiscal em XML."""

    tipo: str  # "nfe" | "cte" | "nfse"
    chave: Optional[str] = None
    campos: Dict[str, Any] = field(default_factory=dict)
    itens: List[Dict[str, Any]] = field(default_factory=list)
    erros: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────


def _ns_tag(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}" if ns else name


def _child_text(el: Any, tag: str, ns: str) -> str:
    child = el.find(_ns_tag(ns, tag))
    return child.text.strip() if child is not None and child.text else ""


def _find_el(el: Any, tag: str, ns: str) -> Optional[Any]:
    return el.find(_ns_tag(ns, tag))


def _find_deep(root: Any, tag: str, ns: str) -> Optional[Any]:
    """Search anywhere in the tree, trying with and without namespace."""
    found = root.find(f".//{_ns_tag(ns, tag)}")
    if found is None and ns:
        found = root.find(f".//{tag}")
    return found


def _deep_text(root: Any, tag: str, ns: str) -> str:
    el = _find_deep(root, tag, ns)
    return el.text.strip() if el is not None and el.text else ""


# ─────────────────────────────────────────────────────────────────────────────
# NF-e
# ─────────────────────────────────────────────────────────────────────────────

_NFE_NS = "http://www.portalfiscal.inf.br/nfe"


class NFeParser:
    """Parser para NF-e em XML (modelo 55/65)."""

    NS = _NFE_NS

    def parse(self, data: bytes) -> XmlParseResult:
        result = XmlParseResult(tipo="nfe")
        try:
            root = ET.fromstring(data)
        except Exception as exc:
            result.erros.append(f"XML inválido: {exc}")
            return result

        ns = self.NS
        inf = _find_deep(root, "infNFe", ns)
        if inf is None:
            result.erros.append("Elemento infNFe não encontrado")
            return result

        result.chave = inf.get("Id", "").replace("NFe", "") or None

        def t(el: Any, tag: str) -> str:
            return _child_text(el, tag, ns)

        ide = _find_el(inf, "ide", ns)
        if ide is not None:
            result.campos.update(
                {
                    "n_nf": t(ide, "nNF"),
                    "serie": t(ide, "serie"),
                    "dt_emis": t(ide, "dhEmi") or t(ide, "dEmi"),
                    "nat_op": t(ide, "natOp"),
                    "tp_nf": t(ide, "tpNF"),
                    "tp_amb": t(ide, "tpAmb"),
                    "tp_emis": t(ide, "tpEmis"),
                    "cod_mun_fg": t(ide, "cMunFG"),
                }
            )

        emit = _find_el(inf, "emit", ns)
        if emit is not None:
            ender_emit = _find_el(emit, "enderEmit", ns)
            result.campos.update(
                {
                    "emit_cnpj": t(emit, "CNPJ"),
                    "emit_cpf": t(emit, "CPF"),
                    "emit_nome": t(emit, "xNome"),
                    "emit_ie": t(emit, "IE"),
                    "emit_crt": t(emit, "CRT"),
                    "emit_uf": (
                        _child_text(ender_emit, "UF", ns)
                        if ender_emit is not None
                        else ""
                    ),
                }
            )

        dest = _find_el(inf, "dest", ns)
        if dest is not None:
            ender_dest = _find_el(dest, "enderDest", ns)
            result.campos.update(
                {
                    "dest_cnpj": t(dest, "CNPJ"),
                    "dest_cpf": t(dest, "CPF"),
                    "dest_nome": t(dest, "xNome"),
                    "dest_ie": t(dest, "IE"),
                    "dest_uf": (
                        _child_text(ender_dest, "UF", ns)
                        if ender_dest is not None
                        else ""
                    ),
                }
            )

        total = _find_el(inf, "total", ns)
        if total is not None:
            icms_tot = _find_el(total, "ICMSTot", ns)
            if icms_tot is not None:
                for campo in [
                    "vNF",
                    "vProd",
                    "vDesc",
                    "vICMS",
                    "vICMSST",
                    "vIPI",
                    "vPIS",
                    "vCOFINS",
                    "vFrete",
                    "vSeg",
                    "vOutro",
                ]:
                    result.campos[campo.lower()] = t(icms_tot, campo)

        for det in inf.iter(_ns_tag(ns, "det")):
            item: Dict[str, Any] = {"n_item": det.get("nItem", "")}
            prod = _find_el(det, "prod", ns)
            if prod is not None:
                item.update(
                    {
                        "c_prod": t(prod, "cProd"),
                        "x_prod": t(prod, "xProd"),
                        "ncm": t(prod, "NCM"),
                        "cfop": t(prod, "CFOP"),
                        "u_com": t(prod, "uCom"),
                        "q_com": t(prod, "qCom"),
                        "v_un_com": t(prod, "vUnCom"),
                        "v_prod": t(prod, "vProd"),
                        "cest": t(prod, "CEST"),
                    }
                )
            imposto = _find_el(det, "imposto", ns)
            if imposto is not None:
                icms_grp = _find_el(imposto, "ICMS", ns)
                if icms_grp is not None:
                    children = list(icms_grp)
                    if children:
                        icms_det = children[0]
                        item["cst_icms"] = _child_text(
                            icms_det, "CST", ns
                        ) or _child_text(icms_det, "CSOSN", ns)
                        item["v_bc_icms"] = _child_text(icms_det, "vBC", ns)
                        item["aliq_icms"] = _child_text(icms_det, "pICMS", ns)
                        item["v_icms"] = _child_text(icms_det, "vICMS", ns)
                pis_grp = _find_el(imposto, "PIS", ns)
                if pis_grp is not None:
                    children = list(pis_grp)
                    if children:
                        pis_det = children[0]
                        item["cst_pis"] = _child_text(pis_det, "CST", ns)
                        item["v_bc_pis"] = _child_text(pis_det, "vBC", ns)
                        item["aliq_pis"] = _child_text(pis_det, "pPIS", ns)
                        item["v_pis"] = _child_text(pis_det, "vPIS", ns)
                cofins_grp = _find_el(imposto, "COFINS", ns)
                if cofins_grp is not None:
                    children = list(cofins_grp)
                    if children:
                        cofins_det = children[0]
                        item["cst_cofins"] = _child_text(cofins_det, "CST", ns)
                        item["v_bc_cofins"] = _child_text(cofins_det, "vBC", ns)
                        item["aliq_cofins"] = _child_text(cofins_det, "pCOFINS", ns)
                        item["v_cofins"] = _child_text(cofins_det, "vCOFINS", ns)
            result.itens.append(item)

        return result


# ─────────────────────────────────────────────────────────────────────────────
# CT-e
# ─────────────────────────────────────────────────────────────────────────────

_CTE_NS = "http://www.portalfiscal.inf.br/cte"


class CTeParser:
    """Parser para CT-e em XML (modelo 57)."""

    NS = _CTE_NS

    def parse(self, data: bytes) -> XmlParseResult:
        result = XmlParseResult(tipo="cte")
        try:
            root = ET.fromstring(data)
        except Exception as exc:
            result.erros.append(f"XML inválido: {exc}")
            return result

        ns = self.NS
        inf = _find_deep(root, "infCte", ns)
        if inf is None:
            result.erros.append("Elemento infCte não encontrado")
            return result

        result.chave = inf.get("Id", "").replace("CTe", "") or None

        def t(el: Any, tag: str) -> str:
            return _child_text(el, tag, ns)

        ide = _find_el(inf, "ide", ns)
        if ide is not None:
            result.campos.update(
                {
                    "n_ct": t(ide, "nCT"),
                    "serie": t(ide, "serie"),
                    "dh_emi": t(ide, "dhEmi"),
                    "modal": t(ide, "modal"),
                    "tp_cte": t(ide, "tpCTe"),
                    "cfop": t(ide, "CFOP"),
                    "nat_op": t(ide, "natOp"),
                    "tp_amb": t(ide, "tpAmb"),
                }
            )

        emit = _find_el(inf, "emit", ns)
        if emit is not None:
            result.campos.update(
                {
                    "emit_cnpj": t(emit, "CNPJ"),
                    "emit_nome": t(emit, "xNome"),
                    "emit_ie": t(emit, "IE"),
                }
            )

        rem = _find_el(inf, "rem", ns)
        if rem is not None:
            result.campos.update(
                {
                    "rem_cnpj": t(rem, "CNPJ"),
                    "rem_cpf": t(rem, "CPF"),
                    "rem_nome": t(rem, "xNome"),
                }
            )

        dest = _find_el(inf, "dest", ns)
        if dest is not None:
            result.campos.update(
                {
                    "dest_cnpj": t(dest, "CNPJ"),
                    "dest_cpf": t(dest, "CPF"),
                    "dest_nome": t(dest, "xNome"),
                }
            )

        vl_prest = _find_el(inf, "vPrest", ns)
        if vl_prest is not None:
            result.campos.update(
                {
                    "vl_tprest": t(vl_prest, "vTPrest"),
                    "vl_rec": t(vl_prest, "vRec"),
                }
            )

        imp = _find_el(inf, "imp", ns)
        if imp is not None:
            icms_grp = _find_el(imp, "ICMS", ns)
            if icms_grp is not None:
                children = list(icms_grp)
                if children:
                    icms_det = children[0]
                    result.campos.update(
                        {
                            "cst_icms": _child_text(icms_det, "CST", ns),
                            "v_bc": _child_text(icms_det, "vBC", ns),
                            "aliq_icms": _child_text(icms_det, "pICMS", ns),
                            "v_icms": _child_text(icms_det, "vICMS", ns),
                        }
                    )

        return result


# ─────────────────────────────────────────────────────────────────────────────
# NFS-e (padrão ABRASF)
# ─────────────────────────────────────────────────────────────────────────────

_NFSE_NS = "http://www.abrasf.org.br/nfse.xsd"


class NFSeParser:
    """Parser para NFS-e — padrão ABRASF (aceita também XML sem namespace)."""

    NS = _NFSE_NS

    def parse(self, data: bytes) -> XmlParseResult:
        result = XmlParseResult(tipo="nfse")
        try:
            root = ET.fromstring(data)
        except Exception as exc:
            result.erros.append(f"XML inválido: {exc}")
            return result

        ns = self.NS

        def ft(tag: str) -> str:
            return _deep_text(root, tag, ns)

        result.campos.update(
            {
                "numero": ft("Numero"),
                "competencia": ft("Competencia"),
                "dt_emissao": ft("DataEmissao"),
                "status": ft("Situacao"),
                "prest_cnpj": ft("Cnpj"),
                "prest_inscricao": ft("InscricaoMunicipal"),
                "tom_cnpj": ft("CnpjTomador"),
                "tom_cpf": ft("CpfTomador"),
                "tom_nome": ft("RazaoSocialTomador") or ft("NomeTomador"),
                "discriminacao": ft("Discriminacao"),
                "cod_serv": ft("CodigoServico") or ft("ItemListaServico"),
                "vl_servicos": ft("ValorServicos"),
                "vl_deducoes": ft("ValorDeducoes"),
                "vl_base_calc": ft("BaseCalculo"),
                "aliq_iss": ft("Aliquota"),
                "vl_iss": ft("ValorIss"),
                "vl_liquido": ft("ValorLiquidoNfse") or ft("ValorLiquido"),
                "vl_pis": ft("ValorPis"),
                "vl_cofins": ft("ValorCofins"),
                "vl_inss": ft("ValorInss"),
                "vl_ir": ft("ValorIr"),
                "vl_csll": ft("ValorCsll"),
            }
        )

        result.chave = result.campos.get("numero") or None
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

_XML_PARSERS: Dict[str, Any] = {
    "nfe": NFeParser,
    "cte": CTeParser,
    "nfse": NFSeParser,
}

_SUPPORTED_XML = set(_XML_PARSERS)


def get_xml_parser(tipo: str) -> Any:
    """Return the appropriate XML parser for the given document type.

    Args:
        tipo: One of ``"nfe"``, ``"cte"``, or ``"nfse"``.

    Raises:
        ValueError: If no parser is registered for *tipo*.
    """
    cls = _XML_PARSERS.get(tipo)
    if cls is None:
        raise ValueError(
            f"Parser XML não disponível para tipo: {tipo!r}. "
            f"Tipos suportados: {sorted(_SUPPORTED_XML)}"
        )
    return cls()
