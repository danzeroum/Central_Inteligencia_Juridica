"""Testes unitários — schemas de perfil."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.profiles.schemas import (
    AreaJuridica,
    ClienteProfile,
    GenericUserProfile,
    LegalAreaProfile,
    Role,
)


def test_area_juridica_enum_values():
    assert AreaJuridica.TRABALHISTA == "trabalhista"
    assert AreaJuridica.SERVIDOR_PUBLICO == "servidor_publico"
    assert len(list(AreaJuridica)) == 16


def test_generic_user_profile_defaults():
    p = GenericUserProfile(user_id="u1", name="João")
    assert p.profile_version == 1
    assert p.preferred_language == "pt-BR"
    assert p.preferred_formality == "accessible"
    assert p.nivel_tecnicidade == 3
    assert p.privacidade_enviar_llm is False
    assert p.especialidades == []


def test_generic_user_profile_tecnicidade_validation():
    with pytest.raises(Exception):
        GenericUserProfile(user_id="u1", name="X", nivel_tecnicidade=0)
    with pytest.raises(Exception):
        GenericUserProfile(user_id="u1", name="X", nivel_tecnicidade=6)


def test_generic_user_profile_especialidades():
    p = GenericUserProfile(
        user_id="u1",
        name="Maria",
        especialidades=[AreaJuridica.TRABALHISTA, AreaJuridica.CIVIL],
    )
    assert len(p.especialidades) == 2
    assert AreaJuridica.TRABALHISTA in p.especialidades


def test_cliente_profile_defaults():
    c = ClienteProfile(cliente_id="c1", advogado_id="a1", nome="Empresa X")
    assert c.consentimento_lgpd is False
    assert c.nivel_tecnicidade_saida == 3
    assert c.tipo_pessoa == "fisica"


def test_cliente_profile_tecnicidade_validation():
    with pytest.raises(Exception):
        ClienteProfile(
            cliente_id="c1", advogado_id="a1", nome="X", nivel_tecnicidade_saida=6
        )


def test_legal_area_profile():
    lap = LegalAreaProfile(
        area_key=AreaJuridica.TRABALHISTA,
        name="Trabalhista",
        persona_prompt="Você é especialista...",
        tribunal_preferencial="TST",
    )
    assert lap.area_key == AreaJuridica.TRABALHISTA
    assert lap.tribunal_preferencial == "TST"
    assert lap.interaction_style_default == "detailed"


def test_role_enum():
    assert Role.ADVOGADO == "advogado"
    assert Role.ADMIN == "admin"


def test_profile_version_field():
    p = GenericUserProfile(user_id="u1", name="X", profile_version=2)
    assert p.profile_version == 2
