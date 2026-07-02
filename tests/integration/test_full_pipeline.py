"""Teste de integração do fluxo central da Central de Inteligência Jurídica.

Exercita código *real* (sem chamadas externas a tribunais ou Ollama):

    identificação de tribunais  ->  consenso ponderado  ->  resiliência

Módulos cobertos:
    - ``src.routing.tribunal_identifier.TribunalIdentifier``
    - ``src.consensus.weighted_voting.WeightedConsensusEngine``
    - ``src.tools.circuit_breaker.CircuitBreaker``

Convenções do repositório: imports absolutos a partir de ``src`` e
``asyncio_mode = "auto"`` (testes async não precisam de marcador explícito).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict

import pytest

from src.consensus.weighted_voting import WeightedConsensusEngine
from src.routing.tribunal_identifier import TribunalIdentifier
from src.tools.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

CONSULTA_MULTI = "Consulta sobre dano moral no TJSP, TJMG e STF"


@pytest.fixture
def identifier() -> TribunalIdentifier:
    """Identificador carregado da configuração real (config/routing/tribunals.yaml)."""

    return TribunalIdentifier.from_config()


@pytest.fixture
def engine() -> WeightedConsensusEngine:
    return WeightedConsensusEngine()


def _proposta(confianca: float, decisao: str = "Ação procedente") -> Dict[str, Any]:
    """Monta uma proposta no formato consumido por ``reach_consensus``."""

    return {"confidence": confianca, "proposal": {"decisao": decisao}}


class TestIdentificacaoTribunal:
    """A identificação de tribunais deve funcionar a partir do texto da consulta."""

    def test_identify_primary_retorna_tribunal_citado(
        self, identifier: TribunalIdentifier
    ) -> None:
        assert (
            identifier.identify_primary("Consulta no TJSP sobre dano moral") == "TJSP"
        )

    def test_identify_all_extrai_multiplos_na_ordem_de_aparicao(
        self, identifier: TribunalIdentifier
    ) -> None:
        assert identifier.identify_all(CONSULTA_MULTI) == ["TJSP", "TJMG", "STF"]

    def test_identify_primary_usa_default_sem_match(
        self, identifier: TribunalIdentifier
    ) -> None:
        assert (
            identifier.identify_primary("Análise de um contrato de locação")
            == identifier.default_tribunal
        )


class TestConsensoPonderado:
    """O consenso deve ponderar confiança por peso e reportar métricas."""

    def test_reach_consensus_escolhe_maior_score_ponderado(
        self, engine: WeightedConsensusEngine
    ) -> None:
        proposals = {
            "STF": _proposta(0.95, decisao="Ação procedente"),
            "TJSP": _proposta(0.80, decisao="Ação improcedente"),
        }
        resultado = engine.reach_consensus(proposals, "jurisprudencia")

        # STF: 0.95 * 1.1 = 1.045 supera TJSP: 0.80 * 1.0 = 0.80
        assert resultado["decision_maker"] == "STF"
        assert 0.0 <= resultado["consensus_strength"] <= 1.0
        assert resultado["participant_count"] == 2

    def test_reach_consensus_agrega_quando_tribunais_concordam(
        self, engine: WeightedConsensusEngine
    ) -> None:
        proposals = {
            t: _proposta(0.85, decisao="Dano moral configurado")
            for t in ["TJSP", "TJMG", "STF"]
        }
        resultado = engine.reach_consensus(proposals, "jurisprudencia")

        assert resultado["agreement_ratio"] == 1.0
        assert resultado["single_source"] is False


class TestPipelineCompleto:
    """Fluxo E2E: consulta -> tribunais -> consenso -> estrutura de saída."""

    def test_identificacao_ate_consenso(
        self, identifier: TribunalIdentifier, engine: WeightedConsensusEngine
    ) -> None:
        tribunais = identifier.identify_all(CONSULTA_MULTI)
        assert tribunais, "esperava ao menos um tribunal identificado"

        confiancas = {"TJSP": 0.89, "TJMG": 0.84, "STF": 0.95}
        proposals = {
            t: _proposta(confiancas[t], decisao="Dano moral configurado")
            for t in tribunais
        }
        resultado = engine.reach_consensus(proposals, "jurisprudencia")

        # Estrutura mínima consumida pela API REST.
        assert resultado["decision_maker"] in tribunais
        assert isinstance(resultado["consensus_strength"], float)
        assert 0.0 <= resultado["consensus_strength"] <= 1.0
        assert resultado["participant_count"] == len(tribunais)


class TestResiliencia:
    """Uma falha de tribunal deve ser isolada sem derrubar o pipeline."""

    def test_circuit_breaker_isola_tribunal_e_mantem_quorum(
        self, engine: WeightedConsensusEngine
    ) -> None:
        breaker = CircuitBreaker(failure_threshold=2, name="tjsp")

        def tribunal_indisponivel() -> Dict[str, Any]:
            raise ConnectionError("TJSP indisponível")

        # Duas falhas consecutivas abrem o circuito.
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(tribunal_indisponivel)
        assert breaker.is_open

        # Com o circuito aberto, novas chamadas são rejeitadas de imediato
        # (fail-fast) em vez de aguardar o tribunal indisponível.
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(tribunal_indisponivel)

        # O sistema segue operando com o quórum restante (TJMG + STF).
        proposals = {
            "TJMG": _proposta(0.84),
            "STF": _proposta(0.95),
        }
        resultado = engine.reach_consensus(proposals, "jurisprudencia")
        assert resultado["participant_count"] == 2
        assert resultado["decision_maker"] in {"TJMG", "STF"}


class TestParalelismo:
    """As consultas por tribunal devem poder rodar concorrentemente."""

    async def test_consulta_tribunais_em_paralelo(self) -> None:
        async def consulta_simulada(_tribunal: str) -> Dict[str, Any]:
            await asyncio.sleep(0.1)
            return {"ok": True}

        tribunais = ["TJSP", "TJMG", "STF"]
        inicio = time.monotonic()
        resultados = await asyncio.gather(*(consulta_simulada(t) for t in tribunais))
        duracao = time.monotonic() - inicio

        assert len(resultados) == 3
        # Paralelo (~0.1s) deve ficar bem abaixo do sequencial (~0.3s).
        assert duracao < 0.29, f"execução levou {duracao:.2f}s — pode não ser paralela"
