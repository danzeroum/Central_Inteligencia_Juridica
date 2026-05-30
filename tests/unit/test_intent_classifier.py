"""Testes unitários do classificador de intenção (caminho de fallback).

O ``_keyword_classify`` é a heurística usada quando não há LLM disponível
(sem ``OPENAI_API_KEY``) — exatamente o cenário da suíte de testes e de muitos
deploys. É determinístico e rápido de testar, mas estava sem cobertura.

Inclui um teste de regressão para o bug em que ``process_keywords`` era
referenciado sem ser definido, derrubando (``NameError``) toda consulta que não
fosse de comparação/status/movimentação — inclusive buscas de jurisprudência e
consultas genéricas.
"""

from __future__ import annotations

import pytest

from src.routing.intent_classifier import IntentClassifier


@pytest.fixture
def classifier() -> IntentClassifier:
    return IntentClassifier()


class TestKeywordClassifyOperations:
    """Cada grupo de palavra-chave deve mapear para a operação correta."""

    @pytest.mark.parametrize(
        "texto, operacao, confianca",
        [
            ("Comparar jurisprudência entre STF e TJSP", "jurisprudence_comparison", 0.85),
            ("Qual o status do TJSP agora?", "status_check", 0.8),
            ("Últimas movimentações do processo", "process_movements", 0.8),
            ("Preciso processar uma ação nova", "process_query", 0.75),
            ("Buscar jurisprudência sobre dano moral", "jurisprudence_search", 0.75),
        ],
    )
    def test_operacao_e_confianca(self, classifier, texto, operacao, confianca) -> None:
        intent = classifier._keyword_classify(texto)
        assert intent.operacao == operacao
        assert intent.confidence == pytest.approx(confianca)

    def test_consulta_vaga_e_generica_com_baixa_confianca(self, classifier) -> None:
        """Sem palavra-chave forte e sem tribunal: genérico com confiança <= 0,5."""
        intent = classifier._keyword_classify("Olá, pode me ajudar?")
        assert intent.operacao == "generic"
        assert intent.confidence <= 0.5

    @pytest.mark.parametrize(
        "texto",
        [
            "Buscar jurisprudência sobre LGPD no STF",  # cai no ramo jurisprudence
            "Preciso de ajuda com um processo",         # cai no ramo process
            "Mensagem qualquer sem palavra-chave",       # cai no ramo genérico
        ],
    )
    def test_regressao_process_keywords_nao_derruba_classificacao(self, classifier, texto) -> None:
        """Regressão: ramos após 'movimentações' não podem lançar NameError."""
        intent = classifier._keyword_classify(texto)  # não deve levantar
        assert intent.operacao in {
            "jurisprudence_search",
            "process_query",
            "generic",
        }


class TestTribunalExtraction:
    """Extração de tribunais por sigla, apelido e desduplicação."""

    @pytest.mark.parametrize(
        "texto, esperado",
        [
            ("Status do TJSP", ["TJSP"]),
            ("Decisões em São Paulo", ["TJSP"]),
        ],
    )
    def test_extrai_tribunal_unico(self, classifier, texto, esperado) -> None:
        assert classifier._extract_tribunals(texto) == esperado

    def test_extrai_multiplos_tribunais(self, classifier) -> None:
        # A ordem de retorno segue o registro interno, não o texto; comparamos
        # como conjunto para asserir presença sem acoplar à ordem do dicionário.
        assert set(classifier._extract_tribunals("Comparar STF e Minas Gerais")) == {"STF", "TJMG"}

    def test_desduplica_mantendo_ordem(self, classifier) -> None:
        # "TJSP" e "São Paulo" referem-se ao mesmo tribunal -> uma entrada só.
        assert classifier._extract_tribunals("TJSP e também São Paulo") == ["TJSP"]

    def test_sigla_curta_exige_limite_de_palavra(self, classifier) -> None:
        """'sp' isolado casa, mas não dentro de outra palavra (ex.: 'esperando')."""
        assert classifier._extract_tribunals("processo em SP") == ["TJSP"]
        assert "TJSP" not in classifier._extract_tribunals("estou esperando resposta")


class TestProcessNumberHandling:
    """Número CNJ: extração por regex e inferência do tribunal."""

    def test_extrai_numero_processo(self, classifier) -> None:
        intent = classifier._keyword_classify(
            "Andamento do processo 1234567-89.2024.8.26.1234"
        )
        assert intent.parametros["numero_processo"] == "1234567-89.2024.8.26.1234"

    @pytest.mark.parametrize(
        "numero, tribunal",
        [
            ("1234567-89.2024.8.26.1234", "TJSP"),
            ("1234567-89.2024.8.13.1234", "TJMG"),
            ("1234567-89.2024.8.21.1234", "TJRS"),
            ("1234567-89.2024.4.03.1234", None),
        ],
    )
    def test_infere_tribunal_pelo_numero(self, classifier, numero, tribunal) -> None:
        assert classifier._infer_tribunal_from_process(numero) == tribunal

    def test_tribunal_inferido_quando_nao_mencionado(self, classifier) -> None:
        """Número .8.26 sem citar 'TJSP' deve inferir TJSP na classificação."""
        intent = classifier._keyword_classify(
            "Movimentações do 1234567-89.2024.8.26.1234"
        )
        assert intent.tribunais == ["TJSP"]


class TestExtractParameters:
    def test_extrai_tema_ate_o_delimitador(self, classifier) -> None:
        # "sobre <tema> em ..." -> o delimitador " em " encerra o tema.
        params = classifier._keyword_classify(
            "Decisões sobre dano moral em relações de consumo"
        ).parametros
        assert params.get("tema") == "dano moral"

    def test_extrai_periodo(self, classifier) -> None:
        params = classifier._keyword_classify(
            "Jurisprudência dos últimos 5 anos"
        ).parametros
        assert params.get("periodo") == "últimos 5 anos"
