"""Serialização XML da ficha PER/DCOMP (S-F.2).

Gera XML baseado no leiaute do Programa PER/DCOMP Web (e-CAC / Receita Federal).
A transmissão real via SOAP é responsabilidade do S-F.3.

Referência: Leiaute PER/DCOMP versão 6.x (IN RFB nº 2055/2021 e alterações).
"""

from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from decimal import Decimal

from src.fiscal.per_dcomp.models import FichaPERDCOMP, TipoFicha

# Mapeamento tipo ficha → código numérico do Programa PER/DCOMP Web
_CODIGO_TIPO: dict[TipoFicha, str] = {
    TipoFicha.PER_RESTITUICAO: "21",  # PIS/COFINS crédito apuração
    TipoFicha.PER_RESSARCIMENTO: "22",  # PIS/COFINS ressarcimento
    TipoFicha.PER_SALDO_NEGATIVO_IRPJ: "30",  # Saldo negativo IRPJ
    TipoFicha.PER_SALDO_NEGATIVO_CSLL: "31",  # Saldo negativo CSLL
    TipoFicha.DCOMP_CREDITO_APURACAO: "71",  # DCOMP crédito apuração
    TipoFicha.DCOMP_PAGAMENTO_INDEVIDO: "72",  # DCOMP pagamento indevido
}


def _periodo_para_xml(periodo: str) -> str:
    """Converte AAAA-MM para MMAAAA (formato do leiaute XML PER/DCOMP)."""
    try:
        ano, mes = periodo.split("-")
        return f"{mes}{ano}"
    except (ValueError, AttributeError):
        return periodo


def _fmt_valor(value: Decimal) -> str:
    """Formata Decimal como string com 2 casas decimais."""
    return f"{value:.2f}"


def to_xml(ficha: FichaPERDCOMP) -> str:
    """Serializa a ficha para XML compatível com o leiaute PER/DCOMP Web."""
    root = ET.Element("PedidoEletronicoRestituicaoOuDeclaracaoCompensacao")
    root.set("xmlns", "http://www.sped.fazenda.gov.br/perdcomp")
    root.set("versao", "6.0")

    # Cabeçalho
    cab = ET.SubElement(root, "cabecalho")
    ET.SubElement(cab, "idFicha").text = ficha.ficha_id
    ET.SubElement(cab, "tipoFicha").text = _CODIGO_TIPO.get(ficha.tipo, "21")
    ET.SubElement(cab, "correlationId").text = ficha.correlation_id or ""
    ET.SubElement(cab, "geradoEm").text = ficha.gerado_em

    # Identificação do contribuinte
    ide = ET.SubElement(root, "ideDeclarante")
    ET.SubElement(ide, "CNPJ").text = ficha.identificacao.cnpj_masked
    ET.SubElement(ide, "nomeEmpresarial").text = ficha.identificacao.nome_empresarial
    ET.SubElement(ide, "periodoApuracao").text = _periodo_para_xml(
        ficha.identificacao.periodo_apuracao
    )

    # Crédito tributário
    cred = ET.SubElement(root, "credito")
    ET.SubElement(cred, "tributo").text = ficha.credito.tributo.value
    ET.SubElement(cred, "periodoApuracao").text = _periodo_para_xml(
        ficha.credito.periodo_apuracao
    )
    ET.SubElement(cred, "valorCredito").text = _fmt_valor(ficha.credito.valor_credito)
    ET.SubElement(cred, "codigoReceita").text = ficha.credito.codigo_receita
    ET.SubElement(cred, "origem").text = ficha.credito.origem
    if ficha.credito.numero_processo:
        ET.SubElement(cred, "numeroProcesso").text = ficha.credito.numero_processo

    # Débitos (DCOMP)
    for deb in ficha.debitos:
        deb_el = ET.SubElement(root, "debitoCompensacao")
        ET.SubElement(deb_el, "tributo").text = deb.tributo.value
        ET.SubElement(deb_el, "periodoApuracao").text = _periodo_para_xml(
            deb.periodo_apuracao
        )
        ET.SubElement(deb_el, "valorDebito").text = _fmt_valor(deb.valor_debito)
        ET.SubElement(deb_el, "codigoReceita").text = deb.codigo_receita

    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def to_xml_b64(ficha: FichaPERDCOMP) -> str:
    """Retorna o XML codificado em base64 (para transporte via JSON)."""
    xml_str = to_xml(ficha)
    return base64.b64encode(xml_str.encode("utf-8")).decode()
