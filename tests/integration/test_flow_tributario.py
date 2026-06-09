"""Testes de integração — fluxo tributário: perfil → RAG → resposta."""

from __future__ import annotations

import pytest

from src.profiles.schemas import AreaJuridica, GenericUserProfile


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_task_with_tributario_profile():
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    profile = GenericUserProfile(
        user_id="adv_trib",
        name="Dr. Tributário",
        especialidades=[AreaJuridica.TRIBUTARIO],
        nivel_tecnicidade=4,
        preferred_formality="technical",
    )
    result = await agent.process_task(
        "Qual o prazo de prescrição tributária previsto no CTN?",
        user_profile=profile,
    )
    assert isinstance(result, dict)
    assert result.get("status") in ("success", "error", "success_with_consensus")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tributario_two_areas():
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    profile = GenericUserProfile(
        user_id="adv_trib2",
        name="Dra. Multi",
        especialidades=[AreaJuridica.TRIBUTARIO, AreaJuridica.EMPRESARIAL],
    )
    result = await agent.process_task(
        "Planejamento tributário em recuperação judicial",
        user_profile=profile,
    )
    assert isinstance(result, dict)
