"""Testes do TribunalIdentifier (roteamento de domínio orientado a config).

Estes testes cobrem dois objetivos:
1. Paridade comportamental com a lógica antes embutida no SupervisorAgent.
2. A propriedade de EXTENSIBILIDADE que viabiliza o crescimento do produto:
   adicionar um novo tribunal/domínio é editar SÓ a configuração YAML, sem
   alterar uma linha de código de produção.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.routing.tribunal_identifier import (
    DEFAULT_CONFIG_PATH,
    TribunalIdentifier,
)


@pytest.fixture()
def identifier() -> TribunalIdentifier:
    """Identifier carregado da configuração real do projeto."""

    return TribunalIdentifier.from_config()


class TestDefaultConfig:
    """Paridade com o comportamento legado do SupervisorAgent."""

    def test_config_file_exists(self) -> None:
        assert DEFAULT_CONFIG_PATH.exists()

    def test_identify_single_tribunal(self, identifier: TribunalIdentifier) -> None:
        assert identifier.identify_all("Status do TJSP") == ["TJSP"]

    def test_identify_multiple_ordered(self, identifier: TribunalIdentifier) -> None:
        assert identifier.identify_all("Status TJRS e consulta processo STF") == [
            "TJRS",
            "STF",
        ]

    def test_identify_three_tribunals(self, identifier: TribunalIdentifier) -> None:
        assert identifier.identify_all("Verificar TJSP, TJMG e TJRJ") == [
            "TJSP",
            "TJMG",
            "TJRJ",
        ]

    def test_identify_dedupes(self, identifier: TribunalIdentifier) -> None:
        assert identifier.identify_all("TJSP e também TJSP") == ["TJSP"]

    def test_primary_defaults_to_tjsp(self, identifier: TribunalIdentifier) -> None:
        assert identifier.identify_primary("Tribunal qualquer") == "TJSP"

    def test_extended_tribunal_only_in_relevant(
        self, identifier: TribunalIdentifier
    ) -> None:
        # STJ é 'core: false' -> não aparece em identify_all, mas sim em relevant.
        assert "STJ" not in identifier.identify_all("Consulta no STJ")
        assert "STJ" in identifier.identify_relevant("Consulta no STJ")

    def test_relevant_expands_region(self, identifier: TribunalIdentifier) -> None:
        relevant = identifier.identify_relevant("Jurisprudência do sudeste")
        assert {"TJSP", "TJMG", "TJRJ"}.issubset(set(relevant))

    def test_relevant_ignores_unknown_region_tribunals(
        self, identifier: TribunalIdentifier
    ) -> None:
        # Nordeste mapeia para TJBA/TJPE/TJCE, que não têm spec -> ignorados.
        assert identifier.identify_relevant("casos do nordeste") == ["TJSP"]

    def test_extract_from_reasoning(self, identifier: TribunalIdentifier) -> None:
        reasoning = {
            "recommendation": "Consultar o TJSP",
            "problem_analysis": "Caso em Minas Gerais",
            "identified_tribunals": ["stf"],
        }
        detected = identifier.extract_from_reasoning(reasoning)
        assert set(detected) == {"TJSP", "TJMG", "STF"}


class TestExtensibility:
    """Adicionar um novo domínio deve exigir apenas configuração."""

    def test_new_tribunal_via_config_only(self, tmp_path: Path) -> None:
        config = tmp_path / "tribunals.yaml"
        config.write_text(
            textwrap.dedent(
                """
                default_tribunal: TJSP
                tribunals:
                  TJSP:
                    core: true
                    keywords: [tjsp]
                  TJPR:
                    core: true
                    keywords: [tjpr, paraná, parana]
                    aliases: [paranaense]
                regions:
                  sul: [TJPR]
                """
            ),
            encoding="utf-8",
        )

        identifier = TribunalIdentifier.from_config(config)

        # O novo tribunal é reconhecido sem nenhuma mudança de código.
        assert identifier.identify_all("Processo no TJPR") == ["TJPR"]
        assert identifier.identify_primary("caso no Paraná") == "TJPR"
        assert "TJPR" in identifier.identify_relevant("tribunais do sul")
        assert "TJPR" in identifier.identify_relevant("questão paranaense")
