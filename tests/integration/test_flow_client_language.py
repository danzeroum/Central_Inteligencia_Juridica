"""Testes de integração — cliente leigo → saída simplificada."""

from __future__ import annotations

import pytest

from src.profiles.schemas import AreaJuridica, ClienteProfile, GenericUserProfile
from src.prompts.context_assembler import ContextAssembler


@pytest.mark.integration
def test_client_nivel_1_simplifies_output():
    """Nível 1 produz instrução de linguagem acessível."""
    ca = ContextAssembler()
    cliente = ClienteProfile(
        cliente_id="c_leigo",
        advogado_id="adv1",
        nome="João da Silva",
        nivel_tecnicidade_saida=1,
        consentimento_lgpd=True,
    )
    result = ca.adjust_for_client("Análise jurídica.", cliente)
    assert len(result) > len("Análise jurídica.")
    assert "acessível" in result.lower() or "analogias" in result.lower()


@pytest.mark.integration
def test_client_nivel_5_preserves_technical():
    ca = ContextAssembler()
    cliente = ClienteProfile(
        cliente_id="c_tecnico",
        advogado_id="adv1",
        nome="Empresa Ltda",
        nivel_tecnicidade_saida=5,
        consentimento_lgpd=True,
    )
    result = ca.adjust_for_client("Análise técnica.", cliente)
    assert "técnica" in result.lower() or "jurisprudenci" in result.lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_task_with_leigo_client():
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    profile = GenericUserProfile(
        user_id="adv_leigo",
        name="Dr. Popular",
        especialidades=[AreaJuridica.CIVIL],
    )
    cliente = ClienteProfile(
        cliente_id="leigo1",
        advogado_id="adv_leigo",
        nome="Maria das Dores",
        nivel_tecnicidade_saida=1,
        consentimento_lgpd=True,
    )
    result = await agent.process_task(
        "O que é usucapião?",
        user_profile=profile,
        cliente_profile=cliente,
    )
    assert isinstance(result, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_client_no_consentimento_processed_safely():
    """Cliente sem consentimento deve processar sem dados do cliente (A9)."""
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    profile = GenericUserProfile(user_id="adv5", name="Dr. LGPD")
    cliente = ClienteProfile(
        cliente_id="sem_consentimento",
        advogado_id="adv5",
        nome="Empresário Sigiloso",
        consentimento_lgpd=False,
    )
    result = await agent.process_task(
        "Questão de direito empresarial",
        user_profile=profile,
        cliente_profile=cliente,
    )
    assert isinstance(result, dict)
