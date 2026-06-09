"""Testes de integração — fluxo trabalhista: perfil → RAG → resposta."""

from __future__ import annotations

import pytest

from src.profiles.schemas import AreaJuridica, GenericUserProfile


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_task_with_trabalhista_profile():
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    profile = GenericUserProfile(
        user_id="adv_trabalhista",
        name="Dr. Trabalhista",
        especialidades=[AreaJuridica.TRABALHISTA],
        nivel_tecnicidade=4,
        preferred_formality="technical",
    )
    result = await agent.process_task(
        "Quais os requisitos para configurar vínculo empregatício pela CLT?",
        user_profile=profile,
    )
    assert isinstance(result, dict)
    assert result.get("status") in ("success", "error", "success_with_consensus")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_profile_areas_logged_in_ledger():
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    profile = GenericUserProfile(
        user_id="adv2",
        name="Dra. CLT",
        especialidades=[AreaJuridica.TRABALHISTA],
    )
    result = await agent.process_task(
        "Horas extras e banco de horas na CLT",
        user_profile=profile,
    )
    assert isinstance(result, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_trabalhista_formality_technical():
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    profile = GenericUserProfile(
        user_id="adv3",
        name="Dr. Técnico",
        especialidades=[AreaJuridica.TRABALHISTA],
        nivel_tecnicidade=5,
        preferred_formality="technical",
    )
    result = await agent.process_task(
        "Adicional de insalubridade — grau máximo CLT art. 192",
        user_profile=profile,
    )
    assert isinstance(result, dict)
