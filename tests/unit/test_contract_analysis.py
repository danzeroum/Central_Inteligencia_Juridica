"""Análise de contratos (Frente F.3) — detecção de cláusulas de risco.

Detecção determinística (sem LLM/rede): valida regras externalizadas, score,
nível de risco, disclaimer OAB, invariante HITL e o hook opcional de detector.
"""

from __future__ import annotations

import textwrap

from src.contracts.analyzer import ContractAnalyzer, register_contract_tools
from src.contracts.rules import ContractRuleSet, get_contract_rules
from src.contracts.schemas import Achado
from src.documents.schemas import DISCLAIMER_OAB
from src.tools.mcp_registry import MCPToolRegistry

_CONTRATO_RISCO = textwrap.dedent(
    """
    CLÁUSULA 1 - DO OBJETO
    O presente contrato tem por objeto a prestação de serviços.

    CLÁUSULA 2 - DA RESPONSABILIDADE
    A CONTRATADA não se responsabiliza por quaisquer danos decorrentes do uso.

    CLÁUSULA 3 - DO FORO
    As partes elegem o foro da Comarca de São Paulo para dirimir controvérsias.
    """
)

_CONTRATO_LIMPO = textwrap.dedent(
    """
    CLÁUSULA 1 - DO OBJETO
    Prestação de serviços de consultoria, com obrigações recíprocas e equilibradas.

    CLÁUSULA 2 - DO PAGAMENTO
    O pagamento será efetuado mensalmente conforme cronograma anexo.
    """
)


def test_regras_carregam_do_yaml():
    rules = get_contract_rules()
    assert len(rules) >= 5
    categorias = {r.categoria for r in rules}
    assert any("responsabilidade" in c.lower() for c in categorias)


def test_detecta_exoneracao_e_foro():
    result = ContractAnalyzer().analisar(_CONTRATO_RISCO)
    categorias = {a.categoria for a in result.achados}
    assert any("responsabilidade" in c.lower() for c in categorias)
    assert any("foro" in c.lower() for c in categorias)
    # Exoneração é severidade alta → nível alto.
    assert result.nivel_risco == "alto"
    assert result.score_risco >= 5


def test_achado_traz_base_legal():
    result = ContractAnalyzer().analisar(_CONTRATO_RISCO)
    exoneracao = next(
        a for a in result.achados if "responsabilidade" in a.categoria.lower()
    )
    assert "CDC" in exoneracao.base_legal
    assert exoneracao.severidade == "alta"
    assert exoneracao.clausula_indice >= 0


def test_contrato_limpo_sem_apontamentos():
    result = ContractAnalyzer().analisar(_CONTRATO_LIMPO)
    assert result.achados == []
    assert result.nivel_risco == "sem_apontamentos"
    assert result.score_risco == 0


def test_disclaimer_e_hitl_obrigatorios():
    result = ContractAnalyzer().analisar(_CONTRATO_LIMPO)
    assert result.disclaimer == DISCLAIMER_OAB
    assert result.requires_human_review is True


def test_total_clausulas_contado():
    result = ContractAnalyzer().analisar(_CONTRATO_RISCO)
    # 3 cláusulas (parágrafos separados por linha em branco).
    assert result.total_clausulas == 3


def test_detector_llm_opcional_substitui_regras():
    def _fake_detector(texto, clausulas):
        return [
            Achado(
                clausula_indice=0,
                trecho="trecho",
                categoria="Categoria LLM",
                base_legal="X",
                severidade="baixa",
                recomendacao="rec",
            )
        ]

    result = ContractAnalyzer().analisar("qualquer texto", detector=_fake_detector)
    assert len(result.achados) == 1
    assert result.achados[0].categoria == "Categoria LLM"
    assert result.nivel_risco == "baixo"
    assert result.score_risco == 1


def test_ruleset_custom_isolado(tmp_path):
    cfg = tmp_path / "regras.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
            regras:
              teste:
                categoria: "Cláusula de teste"
                base_legal: "Lei X"
                severidade: media
                recomendacao: "verificar"
                padroes:
                  - "palavra-gatilho"
            """
        ),
        encoding="utf-8",
    )
    analyzer = ContractAnalyzer(ruleset=ContractRuleSet.from_config(cfg))
    result = analyzer.analisar("Cláusula com palavra-gatilho presente.")
    assert result.nivel_risco == "medio"
    assert result.achados[0].categoria == "Cláusula de teste"


def test_registro_tool_mcp():
    mcp = MCPToolRegistry()
    register_contract_tools(mcp, ContractAnalyzer())
    assert "analisar_contrato" in mcp.tools
    result = mcp.execute("analisar_contrato", _CONTRATO_RISCO)
    assert result.requires_human_review is True
    assert result.nivel_risco == "alto"
