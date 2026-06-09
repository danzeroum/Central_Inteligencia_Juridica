"""Teste de integração — fluxo sem perfil usa fallback genérico."""

from __future__ import annotations

import pytest

from src.agents.supervisor_agent import SupervisorAgent


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_task_without_profile():
    """process_task deve funcionar sem user_profile e usar fallbacks."""
    agent = SupervisorAgent()
    result = await agent.process_task(
        "Qual o prazo prescricional do direito civil?",
        user_profile=None,
        cliente_profile=None,
    )
    assert isinstance(result, dict)
    assert "status" in result


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_task_lgpd_no_consentimento():
    """cliente sem consentimento LGPD deve ser tratado como None (A9)."""
    from src.profiles.schemas import ClienteProfile

    agent = SupervisorAgent()
    cliente = ClienteProfile(
        cliente_id="c1",
        advogado_id="a1",
        nome="Teste",
        consentimento_lgpd=False,
    )
    result = await agent.process_task(
        "Questão sobre prazo.",
        user_profile=None,
        cliente_profile=cliente,
    )
    assert isinstance(result, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_task_with_profile():
    """process_task com perfil deve aceitar user_profile sem erro."""
    from src.profiles.schemas import AreaJuridica, GenericUserProfile

    agent = SupervisorAgent()
    profile = GenericUserProfile(
        user_id="adv1",
        name="Dr. Teste",
        especialidades=[AreaJuridica.TRABALHISTA],
        nivel_tecnicidade=4,
    )
    result = await agent.process_task(
        "Reclamatória trabalhista por horas extras.",
        user_profile=profile,
    )
    assert isinstance(result, dict)
    assert "status" in result
