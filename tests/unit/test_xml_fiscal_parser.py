"""Testes unitários para parsers XML (NF-e, CT-e, NFS-e)."""

from __future__ import annotations

import pytest

from src.fiscal.parser import (
    CTeParser,
    NFeParser,
    NFSeParser,
    XmlParseResult,
    get_xml_parser,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures XML
# ─────────────────────────────────────────────────────────────────────────────

_NFE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe35250100000000000100550010000000011234567890">
      <ide>
        <nNF>1</nNF>
        <serie>1</serie>
        <dhEmi>2025-01-01T00:00:00-03:00</dhEmi>
        <tpNF>1</tpNF>
        <natOp>VENDA</natOp>
        <tpAmb>2</tpAmb>
        <tpEmis>1</tpEmis>
        <cMunFG>3550308</cMunFG>
      </ide>
      <emit>
        <CNPJ>00000000000100</CNPJ>
        <xNome>EMPRESA EMISSORA LTDA</xNome>
        <IE>111111111111</IE>
        <CRT>3</CRT>
        <enderEmit>
          <UF>SP</UF>
        </enderEmit>
      </emit>
      <dest>
        <CNPJ>00000000000200</CNPJ>
        <xNome>CLIENTE DESTINATARIO SA</xNome>
        <IE>222222222222</IE>
        <enderDest>
          <UF>RJ</UF>
        </enderDest>
      </dest>
      <det nItem="1">
        <prod>
          <cProd>001</cProd>
          <xProd>PRODUTO TESTE</xProd>
          <NCM>12345678</NCM>
          <CFOP>5102</CFOP>
          <uCom>UN</uCom>
          <qCom>10.0000</qCom>
          <vUnCom>100.00</vUnCom>
          <vProd>1000.00</vProd>
          <CEST>1234567</CEST>
        </prod>
        <imposto>
          <ICMS>
            <ICMS00>
              <orig>0</orig>
              <CST>00</CST>
              <vBC>1000.00</vBC>
              <pICMS>12.00</pICMS>
              <vICMS>120.00</vICMS>
            </ICMS00>
          </ICMS>
          <PIS>
            <PISAliq>
              <CST>01</CST>
              <vBC>1000.00</vBC>
              <pPIS>0.65</pPIS>
              <vPIS>6.50</vPIS>
            </PISAliq>
          </PIS>
          <COFINS>
            <COFINSAliq>
              <CST>01</CST>
              <vBC>1000.00</vBC>
              <pCOFINS>3.00</pCOFINS>
              <vCOFINS>30.00</vCOFINS>
            </COFINSAliq>
          </COFINS>
        </imposto>
      </det>
      <total>
        <ICMSTot>
          <vNF>1000.00</vNF>
          <vProd>1000.00</vProd>
          <vDesc>0.00</vDesc>
          <vICMS>120.00</vICMS>
          <vICMSST>0.00</vICMSST>
          <vIPI>0.00</vIPI>
          <vPIS>6.50</vPIS>
          <vCOFINS>30.00</vCOFINS>
          <vFrete>0.00</vFrete>
          <vSeg>0.00</vSeg>
          <vOutro>0.00</vOutro>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>"""

_CTE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<cteProc xmlns="http://www.portalfiscal.inf.br/cte">
  <CTe>
    <infCte Id="CTe35250100000000000100570010000000011234567890">
      <ide>
        <nCT>1</nCT>
        <serie>1</serie>
        <dhEmi>2025-01-01T00:00:00-03:00</dhEmi>
        <modal>01</modal>
        <tpCTe>0</tpCTe>
        <CFOP>5353</CFOP>
        <natOp>PRESTACAO DE SERVICO</natOp>
        <tpAmb>2</tpAmb>
      </ide>
      <emit>
        <CNPJ>00000000000300</CNPJ>
        <xNome>TRANSPORTADORA TESTE LTDA</xNome>
        <IE>333333333333</IE>
      </emit>
      <rem>
        <CNPJ>00000000000100</CNPJ>
        <xNome>REMETENTE SA</xNome>
      </rem>
      <dest>
        <CNPJ>00000000000200</CNPJ>
        <xNome>DESTINATARIO FRETE SA</xNome>
      </dest>
      <vPrest>
        <vTPrest>500.00</vTPrest>
        <vRec>500.00</vRec>
      </vPrest>
      <imp>
        <ICMS>
          <ICMS00>
            <CST>00</CST>
            <vBC>500.00</vBC>
            <pICMS>12.00</pICMS>
            <vICMS>60.00</vICMS>
          </ICMS00>
        </ICMS>
      </imp>
    </infCte>
  </CTe>
</cteProc>"""

_NFSE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd">
  <Nfse>
    <InfNfse>
      <Numero>42</Numero>
      <Competencia>2025-01-01</Competencia>
      <DataEmissao>2025-01-15T10:00:00</DataEmissao>
      <Situacao>1</Situacao>
      <PrestadorServico>
        <IdentificacaoPrestador>
          <Cnpj>00000000000400</Cnpj>
          <InscricaoMunicipal>123456</InscricaoMunicipal>
        </IdentificacaoPrestador>
      </PrestadorServico>
      <TomadorServico>
        <IdentificacaoTomador>
          <CpfCnpj>
            <CnpjTomador>00000000000500</CnpjTomador>
          </CpfCnpj>
        </IdentificacaoTomador>
        <RazaoSocialTomador>TOMADOR DE SERVICO LTDA</RazaoSocialTomador>
      </TomadorServico>
      <Servico>
        <Discriminacao>CONSULTORIA TRIBUTARIA</Discriminacao>
        <CodigoServico>1701</CodigoServico>
        <Valores>
          <ValorServicos>3000.00</ValorServicos>
          <ValorDeducoes>0.00</ValorDeducoes>
          <BaseCalculo>3000.00</BaseCalculo>
          <Aliquota>0.05</Aliquota>
          <ValorIss>150.00</ValorIss>
          <ValorLiquidoNfse>2850.00</ValorLiquidoNfse>
          <ValorPis>19.50</ValorPis>
          <ValorCofins>90.00</ValorCofins>
          <ValorInss>0.00</ValorInss>
          <ValorIr>0.00</ValorIr>
          <ValorCsll>0.00</ValorCsll>
        </Valores>
      </Servico>
    </InfNfse>
  </Nfse>
</CompNfse>"""

_NFSE_NO_NS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<CompNfse>
  <Nfse>
    <InfNfse>
      <Numero>99</Numero>
      <Competencia>2025-02-01</Competencia>
      <Servico>
        <Discriminacao>SERVICO SEM NS</Discriminacao>
        <Valores>
          <ValorServicos>1000.00</ValorServicos>
          <ValorIss>50.00</ValorIss>
          <ValorLiquidoNfse>950.00</ValorLiquidoNfse>
        </Valores>
      </Servico>
    </InfNfse>
  </Nfse>
</CompNfse>"""


# ─────────────────────────────────────────────────────────────────────────────
# NF-e
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def nfe_result():
    return NFeParser().parse(_NFE_XML)


def test_nfe_tipo(nfe_result):
    assert nfe_result.tipo == "nfe"


def test_nfe_chave(nfe_result):
    assert nfe_result.chave == "35250100000000000100550010000000011234567890"


def test_nfe_emitente(nfe_result):
    assert nfe_result.campos["emit_cnpj"] == "00000000000100"
    assert nfe_result.campos["emit_nome"] == "EMPRESA EMISSORA LTDA"
    assert nfe_result.campos["emit_uf"] == "SP"
    assert nfe_result.campos["emit_crt"] == "3"


def test_nfe_destinatario(nfe_result):
    assert nfe_result.campos["dest_cnpj"] == "00000000000200"
    assert nfe_result.campos["dest_nome"] == "CLIENTE DESTINATARIO SA"
    assert nfe_result.campos["dest_uf"] == "RJ"


def test_nfe_ide(nfe_result):
    assert nfe_result.campos["n_nf"] == "1"
    assert nfe_result.campos["serie"] == "1"
    assert nfe_result.campos["tp_nf"] == "1"
    assert nfe_result.campos["nat_op"] == "VENDA"


def test_nfe_totais(nfe_result):
    assert nfe_result.campos["vnf"] == "1000.00"
    assert nfe_result.campos["vpis"] == "6.50"
    assert nfe_result.campos["vcofins"] == "30.00"
    assert nfe_result.campos["vicms"] == "120.00"


def test_nfe_itens_count(nfe_result):
    assert len(nfe_result.itens) == 1


def test_nfe_item_prod(nfe_result):
    item = nfe_result.itens[0]
    assert item["n_item"] == "1"
    assert item["c_prod"] == "001"
    assert item["x_prod"] == "PRODUTO TESTE"
    assert item["ncm"] == "12345678"
    assert item["cfop"] == "5102"
    assert item["v_prod"] == "1000.00"


def test_nfe_item_icms(nfe_result):
    item = nfe_result.itens[0]
    assert item["cst_icms"] == "00"
    assert item["v_bc_icms"] == "1000.00"
    assert item["aliq_icms"] == "12.00"
    assert item["v_icms"] == "120.00"


def test_nfe_item_pis(nfe_result):
    item = nfe_result.itens[0]
    assert item["cst_pis"] == "01"
    assert item["v_pis"] == "6.50"


def test_nfe_item_cofins(nfe_result):
    item = nfe_result.itens[0]
    assert item["cst_cofins"] == "01"
    assert item["v_cofins"] == "30.00"


def test_nfe_no_errors(nfe_result):
    assert nfe_result.erros == []


def test_nfe_invalid_xml():
    result = NFeParser().parse(b"<not-valid>xml<<")
    assert len(result.erros) == 1
    assert "XML inválido" in result.erros[0]


def test_nfe_missing_infnfe():
    result = NFeParser().parse(b"<root><child/></root>")
    assert any("infNFe" in e for e in result.erros)


# ─────────────────────────────────────────────────────────────────────────────
# CT-e
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def cte_result():
    return CTeParser().parse(_CTE_XML)


def test_cte_tipo(cte_result):
    assert cte_result.tipo == "cte"


def test_cte_chave(cte_result):
    assert cte_result.chave == "35250100000000000100570010000000011234567890"


def test_cte_ide(cte_result):
    assert cte_result.campos["n_ct"] == "1"
    assert cte_result.campos["modal"] == "01"
    assert cte_result.campos["cfop"] == "5353"
    assert cte_result.campos["tp_amb"] == "2"


def test_cte_emitente(cte_result):
    assert cte_result.campos["emit_cnpj"] == "00000000000300"
    assert cte_result.campos["emit_nome"] == "TRANSPORTADORA TESTE LTDA"


def test_cte_remetente(cte_result):
    assert cte_result.campos["rem_cnpj"] == "00000000000100"
    assert cte_result.campos["rem_nome"] == "REMETENTE SA"


def test_cte_destinatario(cte_result):
    assert cte_result.campos["dest_cnpj"] == "00000000000200"


def test_cte_valores_prestacao(cte_result):
    assert cte_result.campos["vl_tprest"] == "500.00"
    assert cte_result.campos["vl_rec"] == "500.00"


def test_cte_icms(cte_result):
    assert cte_result.campos["cst_icms"] == "00"
    assert cte_result.campos["v_bc"] == "500.00"
    assert cte_result.campos["aliq_icms"] == "12.00"
    assert cte_result.campos["v_icms"] == "60.00"


def test_cte_no_errors(cte_result):
    assert cte_result.erros == []


def test_cte_invalid_xml():
    result = CTeParser().parse(b"<broken")
    assert len(result.erros) == 1
    assert "XML inválido" in result.erros[0]


def test_cte_missing_infcte():
    result = CTeParser().parse(b"<root/>")
    assert any("infCte" in e for e in result.erros)


# ─────────────────────────────────────────────────────────────────────────────
# NFS-e
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def nfse_result():
    return NFSeParser().parse(_NFSE_XML)


def test_nfse_tipo(nfse_result):
    assert nfse_result.tipo == "nfse"


def test_nfse_numero(nfse_result):
    assert nfse_result.campos["numero"] == "42"
    assert nfse_result.chave == "42"


def test_nfse_competencia(nfse_result):
    assert nfse_result.campos["competencia"] == "2025-01-01"


def test_nfse_prestador(nfse_result):
    assert nfse_result.campos["prest_cnpj"] == "00000000000400"
    assert nfse_result.campos["prest_inscricao"] == "123456"


def test_nfse_tomador(nfse_result):
    assert nfse_result.campos["tom_nome"] == "TOMADOR DE SERVICO LTDA"


def test_nfse_servico(nfse_result):
    assert nfse_result.campos["discriminacao"] == "CONSULTORIA TRIBUTARIA"
    assert nfse_result.campos["cod_serv"] == "1701"


def test_nfse_valores(nfse_result):
    assert nfse_result.campos["vl_servicos"] == "3000.00"
    assert nfse_result.campos["aliq_iss"] == "0.05"
    assert nfse_result.campos["vl_iss"] == "150.00"
    assert nfse_result.campos["vl_liquido"] == "2850.00"


def test_nfse_retencoes(nfse_result):
    assert nfse_result.campos["vl_pis"] == "19.50"
    assert nfse_result.campos["vl_cofins"] == "90.00"


def test_nfse_no_errors(nfse_result):
    assert nfse_result.erros == []


def test_nfse_no_namespace():
    result = NFSeParser().parse(_NFSE_NO_NS_XML)
    assert result.campos["numero"] == "99"
    assert result.campos["vl_servicos"] == "1000.00"
    assert result.campos["vl_iss"] == "50.00"


def test_nfse_invalid_xml():
    result = NFSeParser().parse(b"<<<invalid")
    assert len(result.erros) == 1
    assert "XML inválido" in result.erros[0]


# ─────────────────────────────────────────────────────────────────────────────
# XmlParseResult dataclass
# ─────────────────────────────────────────────────────────────────────────────


def test_xml_parse_result_defaults():
    r = XmlParseResult(tipo="nfe")
    assert r.chave is None
    assert r.campos == {}
    assert r.itens == []
    assert r.erros == []


# ─────────────────────────────────────────────────────────────────────────────
# Registry get_xml_parser
# ─────────────────────────────────────────────────────────────────────────────


def test_get_xml_parser_nfe():
    parser = get_xml_parser("nfe")
    assert isinstance(parser, NFeParser)


def test_get_xml_parser_cte():
    parser = get_xml_parser("cte")
    assert isinstance(parser, CTeParser)


def test_get_xml_parser_nfse():
    parser = get_xml_parser("nfse")
    assert isinstance(parser, NFSeParser)


def test_get_xml_parser_unknown():
    with pytest.raises(ValueError, match="Parser XML não disponível"):
        get_xml_parser("boleto")


def test_get_xml_parser_returns_fresh_instance():
    p1 = get_xml_parser("nfe")
    p2 = get_xml_parser("nfe")
    assert p1 is not p2
