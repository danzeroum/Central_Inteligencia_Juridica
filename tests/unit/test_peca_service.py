"""Geração de peças processuais (Frente F.2).

Cobre: seleção de template externalizado, preenchimento determinístico,
postcheck jurídico (campos obrigatórios), disclaimer OAB obrigatório, invariante
de revisão humana (HITL) e o hook opcional de LLM.
"""

from __future__ import annotations

import textwrap

import pytest

from src.documents.peca_service import PecaService, register_peca_tools
from src.documents.schemas import DISCLAIMER_OAB
from src.documents.templates import (
    PecaDesconhecidaError,
    PecaTemplateRegistry,
    get_template_registry,
)
from src.tools.mcp_registry import MCPToolRegistry

_DADOS_INICIAL = {
    "juizo": "1ª Vara Cível da Comarca de São Paulo",
    "qualificacao_autor": "Fulano de Tal, brasileiro, CPF ...",
    "qualificacao_reu": "Empresa XPTO Ltda., CNPJ ...",
    "fatos": "O autor contratou e não foi atendido.",
    "fundamentos": "CDC art. 14.",
    "pedido": "Condenação ao ressarcimento.",
    "valor_causa": "R$ 10.000,00",
}


@pytest.fixture
def service():
    return PecaService()


# ── Templates externalizados ─────────────────────────────────────────────────
def test_templates_disponiveis_do_yaml(service):
    disponiveis = service.available()
    assert {"peticao_inicial", "contestacao", "procuracao"} <= set(disponiveis)


def test_tipo_desconhecido_levanta(service):
    with pytest.raises(PecaDesconhecidaError):
        service.gerar("peca_inexistente", {})


# ── Geração + preenchimento ──────────────────────────────────────────────────
def test_gera_peticao_inicial_preenchida(service):
    result = service.gerar("peticao_inicial", _DADOS_INICIAL)
    assert result.tipo == "peticao_inicial"
    assert result.nome == "Petição Inicial"
    assert result.base_legal == "CPC art. 319"
    assert "R$ 10.000,00" in result.conteudo
    assert "[FALTANTE:" not in result.conteudo
    assert result.postcheck.ok is True
    assert result.postcheck.findings == []


# ── Postcheck pega campos obrigatórios faltando ──────────────────────────────
def test_postcheck_detecta_pedido_ausente(service):
    dados = dict(_DADOS_INICIAL)
    del dados["pedido"]
    result = service.gerar("peticao_inicial", dados)
    assert result.postcheck.ok is False
    assert any("pedido" in f for f in result.postcheck.findings)
    assert "[FALTANTE: pedido]" in result.conteudo


def test_postcheck_campo_vazio_conta_como_ausente(service):
    dados = dict(_DADOS_INICIAL, valor_causa="   ")
    result = service.gerar("peticao_inicial", dados)
    assert result.postcheck.ok is False
    assert any("valor_causa" in f for f in result.postcheck.findings)


# ── Disclaimer OAB + invariante HITL ─────────────────────────────────────────
def test_disclaimer_oab_obrigatorio(service):
    result = service.gerar(
        "procuracao",
        {
            "outorgante": "Fulano",
            "outorgado": "Dra. Beltrana (OAB/SP 123)",
            "poderes": "transigir, receber e dar quitação",
        },
    )
    assert result.disclaimer == DISCLAIMER_OAB
    assert "OAB" in result.disclaimer
    assert result.requires_human_review is True


# ── Integração HITL (fila injetada) ──────────────────────────────────────────
def test_enfileira_para_revisao_humana():
    class _FakeRequest:
        request_id = "req-123"

    captured = {}

    class _FakeQueue:
        def add_request(self, agent, action, context):
            captured["agent"] = agent
            captured["action"] = action
            return _FakeRequest()

    service = PecaService()
    result = service.gerar("peticao_inicial", _DADOS_INICIAL, hitl_queue=_FakeQueue())
    assert result.hitl_request_id == "req-123"
    assert captured["agent"] == "AgenteDocumentos"
    assert captured["action"]["type"] == "peca_review"


# ── Hook de LLM opcional ─────────────────────────────────────────────────────
def test_gerador_llm_substitui_preenchimento(service):
    def _fake_llm(template, dados):
        return f"PROSA GERADA PARA {template.nome}"

    result = service.gerar(
        "contestacao",
        {
            "juizo": "2ª Vara",
            "processo": "123",
            "qualificacao_reu": "Réu",
            "merito": "defesa",
            "pedido": "improcedência",
        },
        gerador=_fake_llm,
    )
    assert result.conteudo == "PROSA GERADA PARA Contestação"
    # Postcheck valida os DADOS (não o texto), então segue ok com campos presentes.
    assert result.postcheck.ok is True


# ── Carga de YAML custom isolado ─────────────────────────────────────────────
def test_registry_from_config_custom(tmp_path):
    cfg = tmp_path / "pecas.yaml"
    cfg.write_text(
        textwrap.dedent("""
            pecas:
              recurso:
                nome: "Recurso de Apelação"
                base_legal: "CPC art. 1.010"
                campos_obrigatorios: [razoes]
                template: "RAZÕES: {razoes}"
            """),
        encoding="utf-8",
    )
    registry = PecaTemplateRegistry.from_config(cfg)
    service = PecaService(registry=registry)
    result = service.gerar("recurso", {"razoes": "tempestivo e fundamentado"})
    assert result.base_legal == "CPC art. 1.010"
    assert "tempestivo" in result.conteudo
    assert result.postcheck.ok is True


# ── Registro de tool MCP ─────────────────────────────────────────────────────
def test_registro_tool_mcp():
    mcp = MCPToolRegistry()
    register_peca_tools(mcp, PecaService())
    assert "gerar_peca" in mcp.tools
    result = mcp.execute(
        "gerar_peca",
        "procuracao",
        {"outorgante": "A", "outorgado": "B", "poderes": "p"},
    )
    assert result.tipo == "procuracao"
    assert result.requires_human_review is True


def test_singleton_registry_carrega():
    assert get_template_registry().get("peticao_inicial").nome == "Petição Inicial"
