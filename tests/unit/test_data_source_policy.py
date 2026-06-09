"""DMN-02 — política de fonte de dados (regra CJ-001) e guardrail no SafetyProtocol.

Frente F4: valida que as regras de fonte vivem em ``config/governance/data_sources.yaml``
e que o LLM jamais é a FONTE de um dado crítico (hard block).
"""

from __future__ import annotations

import textwrap

import pytest

from src.governance.data_source_policy import (
    DataSourcePolicy,
    DataSourceViolation,
    get_data_source_policy,
)
from src.protocols.safety_protocol import SafetyProtocol


# ── Carregamento da configuração real do repositório ─────────────────────────
def test_policy_carrega_config_real():
    policy = get_data_source_policy()
    # Tipos críticos esperados estão na DMN-02.
    criticos = set(policy.critical_data_types())
    assert {"legislacao", "jurisprudencia", "indice_economico"} <= criticos
    assert policy.authorized_source("jurisprudencia") == "CNJ DataJud"
    assert policy.cache_ttl("jurisprudencia") == "24h"


def test_interpretacao_nao_e_critica_e_llm_exclusivo():
    policy = get_data_source_policy()
    assert policy.is_critical("interpretacao") is False
    assert policy.is_llm_allowed_as_source("interpretacao") is True
    assert policy.rule_for("interpretacao").llm == "exclusivo"


# ── Hard block CJ-001 ────────────────────────────────────────────────────────
def test_llm_como_fonte_de_dado_critico_e_bloqueado():
    policy = get_data_source_policy()
    with pytest.raises(DataSourceViolation):
        policy.assert_source("jurisprudencia", "llm")
    with pytest.raises(DataSourceViolation):
        policy.assert_source("indice_economico", "LLM")  # case-insensitive


def test_fonte_real_para_dado_critico_e_permitida():
    policy = get_data_source_policy()
    # Não levanta: API real é a fonte autorizada.
    policy.assert_source("jurisprudencia", "CNJ DataJud")
    policy.assert_source("indice_economico", "BCB")


def test_llm_como_fonte_de_interpretacao_e_permitido():
    policy = get_data_source_policy()
    # interpretacao não é crítica → LLM pode ser a fonte.
    policy.assert_source("interpretacao", "llm")


def test_tipo_nao_governado_e_permitido():
    policy = get_data_source_policy()
    policy.assert_source("tipo_desconhecido", "llm")  # não levanta


# ── Carregamento a partir de YAML arbitrário (isolado) ───────────────────────
def test_from_config_le_arquivo_custom(tmp_path):
    cfg = tmp_path / "ds.yaml"
    cfg.write_text(
        textwrap.dedent("""
            data_types:
              x_critico:
                fonte: "API X"
                llm: nao
                critico: true
                cache_ttl: "1h"
            """),
        encoding="utf-8",
    )
    policy = DataSourcePolicy.from_config(cfg)
    assert policy.is_critical("x_critico") is True
    with pytest.raises(DataSourceViolation):
        policy.assert_source("x_critico", "llm")


# ── Guardrail integrado ao SafetyProtocol ────────────────────────────────────
def test_safety_protocol_enforce_data_source():
    sp = SafetyProtocol()
    with pytest.raises(DataSourceViolation):
        sp.enforce_data_source("legislacao", "llm")
    # API real é aceita.
    sp.enforce_data_source("legislacao", "Planalto")


def test_safety_protocol_is_data_source_allowed():
    sp = SafetyProtocol()
    assert sp.is_data_source_allowed("jurisprudencia", "llm") is False
    assert sp.is_data_source_allowed("jurisprudencia", "CNJ DataJud") is True
