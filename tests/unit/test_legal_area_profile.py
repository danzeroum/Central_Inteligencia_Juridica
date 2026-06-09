"""Testes unitários — carregamento de personas YAML."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.profiles.legal_areas import load_legal_area, list_legal_areas
from src.profiles.schemas import AreaJuridica


def test_load_existing_legal_area():
    profile = load_legal_area("trabalhista")
    if profile is None:
        pytest.skip("YAML de personas não disponível no ambiente de teste")
    assert profile.area_key == AreaJuridica.TRABALHISTA
    assert profile.name
    assert profile.persona_prompt


def test_load_nonexistent_area_returns_none():
    profile = load_legal_area("area_inexistente_xyz")
    assert profile is None


def test_list_legal_areas_returns_dict():
    areas = list_legal_areas()
    # Should be dict (empty if YAML not loaded, or populated)
    assert isinstance(areas, dict)


def test_load_legal_area_graceful_fallback(tmp_path, monkeypatch):
    """Fallback gracioso quando diretório de personas não existe."""
    import src.profiles.legal_areas as la

    la._loaded = False
    la._cache.clear()

    # Aponta para diretório vazio
    monkeypatch.setattr(la, "_PERSONAS_DIR", tmp_path / "nonexistent")
    profile = la.load_legal_area("trabalhista")
    assert profile is None
    # Reseta para não afetar outros testes
    la._loaded = False
    la._cache.clear()


def test_legal_area_profile_has_persona_prompt():
    profile = load_legal_area("previdenciario")
    if profile is None:
        pytest.skip("YAML de personas não disponível")
    assert len(profile.persona_prompt) > 20
    assert profile.tribunal_preferencial is not None
