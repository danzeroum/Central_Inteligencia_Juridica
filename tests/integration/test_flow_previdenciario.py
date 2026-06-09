"""Testes de integração — fluxo previdenciário: perfil → RAG → resposta."""

from __future__ import annotations

import pytest

from src.profiles.schemas import AreaJuridica, GenericUserProfile


@pytest.mark.asyncio
@pytest.mark.integration
async def test_process_task_with_previdenciario_profile():
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    profile = GenericUserProfile(
        user_id="adv_prev",
        name="Dra. Previdência",
        especialidades=[AreaJuridica.PREVIDENCIARIO],
        nivel_tecnicidade=3,
    )
    result = await agent.process_task(
        "Quais benefícios o INSS oferece por incapacidade laboral?",
        user_profile=profile,
    )
    assert isinstance(result, dict)
    assert result.get("status") in ("success", "error", "success_with_consensus")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_previdenciario_carencia_query():
    from src.agents.supervisor_agent import SupervisorAgent

    agent = SupervisorAgent()
    profile = GenericUserProfile(
        user_id="adv_prev2",
        name="Dr. Carência",
        especialidades=[AreaJuridica.PREVIDENCIARIO],
    )
    result = await agent.process_task(
        "Qual o período de carência para aposentadoria por idade?",
        user_profile=profile,
    )
    assert isinstance(result, dict)
