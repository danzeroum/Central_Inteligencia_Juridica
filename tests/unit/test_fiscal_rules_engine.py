"""Testes unitários para o motor de regras fiscais declarativo (S-C.1)."""

from __future__ import annotations

import pytest

from src.fiscal.parser.base import SpedRecord
from src.fiscal.reconciliation import Severidade
from src.fiscal.rules_engine import (
    ApuracaoResult,
    FiscalRule,
    FiscalRulesEngine,
    RuleResult,
    get_rules_engine,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _c100(**kwargs) -> SpedRecord:
    """SpedRecord C100 com campos válidos por padrão + overrides."""
    defaults = {
        "ind_oper": "0",
        "ind_emit": "0",
        "cod_part": "12345678000195",
        "cod_mod": "55",
        "cod_sit": "0",
        "ser": "1",
        "num_doc": "42",
        "chv_nfe": "3" * 44,
        "dt_doc": "2025-01-01",
        "dt_e_s": "2025-01-01",
        "vl_doc": "1000,00",
        "vl_desc": "0,00",
        "vl_bc_icms": "1000,00",
        "aliq_icms": "12,00",
        "vl_icms": "120,00",
        "vl_pis": "6,50",
        "vl_cofins": "30,00",
    }
    defaults.update(kwargs)
    return SpedRecord(
        bloco="C", tipo_registro="C100", campos=defaults, numero_linha=10, raw=""
    )


def _d100(**kwargs) -> SpedRecord:
    defaults = {
        "cod_sit": "0",
        "ser": "1",
        "num_doc": "1",
        "dt_doc": "2025-01-01",
        "vl_doc": "500,00",
        "vl_bc_icms": "500,00",
        "aliq_icms": "12,00",
        "vl_icms": "60,00",
    }
    defaults.update(kwargs)
    return SpedRecord(
        bloco="D", tipo_registro="D100", campos=defaults, numero_linha=20, raw=""
    )


def _m200(**kwargs) -> SpedRecord:
    defaults = {"vl_tot_cont_nc_per": "36,67"}
    defaults.update(kwargs)
    return SpedRecord(
        bloco="M", tipo_registro="M200", campos=defaults, numero_linha=100, raw=""
    )


def _e110(**kwargs) -> SpedRecord:
    defaults = {"vl_tot_debitos": "5000,00", "vl_tot_creditos": "4800,00"}
    defaults.update(kwargs)
    return SpedRecord(
        bloco="E", tipo_registro="E110", campos=defaults, numero_linha=50, raw=""
    )


def _violations(record: SpedRecord, regime: str = "lucro_real") -> list:
    return FiscalRulesEngine(regime).apply_rules(record)


def _vids(record: SpedRecord, regime: str = "lucro_real") -> set:
    return {r.regra_id for r in _violations(record, regime)}


# ─────────────────────────────────────────────────────────────────────────────
# RuleResult / ApuracaoResult
# ─────────────────────────────────────────────────────────────────────────────


def test_rule_result_campos():
    r = RuleResult(
        regra_id="ICMS-001",
        severidade=Severidade.ERRO,
        campo="vl_bc_icms",
        descricao="Base negativa",
        tipo_registro="C100",
        numero_linha=5,
    )
    assert r.regra_id == "ICMS-001"
    assert r.dica == ""
    assert r.valor_encontrado is None


def test_apuracao_result_defaults():
    r = ApuracaoResult(aprovado=True)
    assert r.resultados == []
    assert r.erros == []
    assert r.avisos == []
    assert r.infos == []
    assert r.total_registros == 0
    assert r.resumo == ""


def test_apuracao_result_filtros():
    err = RuleResult("X-001", Severidade.ERRO, "x", "e", "C100", 1)
    warn = RuleResult("X-002", Severidade.AVISO, "y", "w", "C100", 2)
    info = RuleResult("X-003", Severidade.INFO, "z", "i", "C100", 3)
    r = ApuracaoResult(aprovado=False, resultados=[err, warn, info])
    assert r.erros == [err]
    assert r.avisos == [warn]
    assert r.infos == [info]


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


def test_get_rules_engine_lucro_real():
    e = get_rules_engine("lucro_real")
    assert isinstance(e, FiscalRulesEngine)
    assert e.regime == "lucro_real"


def test_get_rules_engine_lucro_presumido():
    assert get_rules_engine("lucro_presumido").regime == "lucro_presumido"


def test_get_rules_engine_simples_nacional():
    assert get_rules_engine("simples_nacional").regime == "simples_nacional"


def test_get_rules_engine_padrao_lucro_real():
    assert get_rules_engine().regime == "lucro_real"


def test_get_rules_engine_regime_invalido():
    with pytest.raises(ValueError, match="Regime inválido"):
        get_rules_engine("mei")


def test_get_rules_engine_instancias_independentes():
    assert get_rules_engine() is not get_rules_engine()


# ─────────────────────────────────────────────────────────────────────────────
# C100 — válido sem violações
# ─────────────────────────────────────────────────────────────────────────────


def test_c100_valido_sem_violacoes():
    assert _violations(_c100()) == []


# ─────────────────────────────────────────────────────────────────────────────
# C100 — Regras ICMS
# ─────────────────────────────────────────────────────────────────────────────


def test_icms_001_base_negativa():
    assert "ICMS-001" in _vids(_c100(vl_bc_icms="-100,00"))


def test_icms_001_base_zero_ok():
    assert "ICMS-001" not in _vids(_c100(vl_bc_icms="0,00", vl_icms="0,00"))


def test_icms_002_valor_negativo():
    assert "ICMS-002" in _vids(_c100(vl_icms="-10,00"))


def test_icms_002_valor_zero_ok():
    assert "ICMS-002" not in _vids(_c100(vl_icms="0,00", aliq_icms="0,00"))


def test_icms_003_valor_excede_base():
    assert "ICMS-003" in _vids(_c100(vl_bc_icms="100,00", vl_icms="200,00"))


def test_icms_003_valor_igual_base_ok():
    # vl_icms == vl_bc_icms → not strictly greater, no ICMS-003
    r = _c100(vl_bc_icms="100,00", vl_icms="100,00", aliq_icms="100,00")
    assert "ICMS-003" not in _vids(r)


def test_icms_003_base_zero_nao_dispara():
    # base=0 — condition vb > 0 not met
    assert "ICMS-003" not in _vids(_c100(vl_bc_icms="0,00", vl_icms="0,00"))


def test_icms_004_base_excede_doc():
    assert "ICMS-004" in _vids(_c100(vl_doc="500,00", vl_bc_icms="600,00"))


def test_icms_004_base_igual_doc_ok():
    assert "ICMS-004" not in _vids(_c100(vl_doc="1000,00", vl_bc_icms="1000,00"))


def test_icms_005_aliq_inconsistente():
    # base=1000, aliq=12 → esperado=120, actual=200, diff≈67% > 1%
    assert "ICMS-005" in _vids(
        _c100(vl_bc_icms="1000,00", aliq_icms="12,00", vl_icms="200,00")
    )


def test_icms_005_aliq_consistente_ok():
    # exact match
    assert "ICMS-005" not in _vids(
        _c100(vl_bc_icms="1000,00", aliq_icms="12,00", vl_icms="120,00")
    )


def test_icms_005_aliq_zero_nao_dispara():
    assert "ICMS-005" not in _vids(_c100(aliq_icms="0,00", vl_icms="0,00"))


def test_icms_005_base_zero_nao_dispara():
    assert "ICMS-005" not in _vids(
        _c100(vl_bc_icms="0,00", vl_icms="0,00", aliq_icms="12,00")
    )


# ─────────────────────────────────────────────────────────────────────────────
# C100 — Regras PIS / COFINS
# ─────────────────────────────────────────────────────────────────────────────


def test_pis_001_negativo():
    assert "PIS-001" in _vids(_c100(vl_pis="-1,00"))


def test_pis_001_zero_ok():
    assert "PIS-001" not in _vids(_c100(vl_pis="0,00"))


def test_cofins_001_negativo():
    assert "COFINS-001" in _vids(_c100(vl_cofins="-0,50"))


def test_cofins_001_zero_ok():
    assert "COFINS-001" not in _vids(_c100(vl_cofins="0,00"))


def test_pis_002_excede_doc():
    assert "PIS-002" in _vids(_c100(vl_doc="100,00", vl_pis="200,00"))


def test_pis_002_igual_doc_ok():
    # edge: vl_pis == vl_doc is not strictly greater → no violation
    assert "PIS-002" not in _vids(_c100(vl_doc="100,00", vl_pis="100,00"))


def test_cofins_002_excede_doc():
    assert "COFINS-002" in _vids(_c100(vl_doc="100,00", vl_cofins="150,00"))


# ─────────────────────────────────────────────────────────────────────────────
# C100 — cod_sit cancelado
# ─────────────────────────────────────────────────────────────────────────────


def test_cod_sit_001_cancelado_com_valor():
    assert "COD-SIT-001" in _vids(_c100(cod_sit="5", vl_doc="1000,00"))


def test_cod_sit_001_denegado_com_valor():
    assert "COD-SIT-001" in _vids(_c100(cod_sit="7", vl_doc="500,00"))


def test_cod_sit_001_cancelado_valor_zero_ok():
    r = _c100(
        cod_sit="5",
        vl_doc="0,00",
        vl_bc_icms="0,00",
        vl_icms="0,00",
        aliq_icms="0,00",
        vl_pis="0,00",
        vl_cofins="0,00",
    )
    assert "COD-SIT-001" not in _vids(r)


def test_cod_sit_001_normal_nao_dispara():
    assert "COD-SIT-001" not in _vids(_c100(cod_sit="0"))


# ─────────────────────────────────────────────────────────────────────────────
# D100 — CT-e
# ─────────────────────────────────────────────────────────────────────────────


def test_d100_valido():
    assert _violations(_d100()) == []


def test_icms_d_001_negativo():
    assert "ICMS-D-001" in _vids(_d100(vl_icms="-5,00"))


def test_icms_d_001_zero_ok():
    assert "ICMS-D-001" not in _vids(_d100(vl_icms="0,00"))


def test_icms_d_002_base_negativa():
    assert "ICMS-D-002" in _vids(_d100(vl_bc_icms="-10,00"))


def test_icms_d_002_base_zero_ok():
    assert "ICMS-D-002" not in _vids(_d100(vl_bc_icms="0,00", vl_icms="0,00"))


def test_icms_d_003_excede_base():
    assert "ICMS-D-003" in _vids(_d100(vl_bc_icms="100,00", vl_icms="200,00"))


def test_icms_d_003_igual_base_ok():
    r = _d100(vl_bc_icms="100,00", vl_icms="100,00")
    assert "ICMS-D-003" not in _vids(r)


# ─────────────────────────────────────────────────────────────────────────────
# M200 — PIS apuração
# ─────────────────────────────────────────────────────────────────────────────


def test_m200_valido():
    assert _violations(_m200()) == []


def test_pis_m_001_negativo():
    assert "PIS-M-001" in _vids(_m200(vl_tot_cont_nc_per="-10,00"))


def test_pis_m_001_zero_ok():
    assert "PIS-M-001" not in _vids(_m200(vl_tot_cont_nc_per="0,00"))


# ─────────────────────────────────────────────────────────────────────────────
# E110 — ICMS apuração
# ─────────────────────────────────────────────────────────────────────────────


def test_e110_valido():
    assert _violations(_e110()) == []


def test_icms_e_001_debitos_negativos():
    assert "ICMS-E-001" in _vids(_e110(vl_tot_debitos="-100,00"))


def test_icms_e_001_zero_ok():
    assert "ICMS-E-001" not in _vids(_e110(vl_tot_debitos="0,00"))


# ─────────────────────────────────────────────────────────────────────────────
# Validate em lote
# ─────────────────────────────────────────────────────────────────────────────


def test_validate_lista_vazia():
    r = get_rules_engine().validate([])
    assert r.aprovado is True
    assert r.resultados == []
    assert r.total_registros == 0
    assert r.resumo == "Apuração aprovada sem violações"


def test_validate_sem_violacoes():
    records = [_c100(), _d100(), _m200(), _e110()]
    r = get_rules_engine().validate(records)
    assert r.aprovado is True
    assert r.resultados == []
    assert r.resumo == "Apuração aprovada sem violações"


def test_validate_com_erros():
    records = [_c100(vl_icms="-10,00"), _d100()]
    r = get_rules_engine().validate(records)
    assert r.aprovado is False
    assert len(r.erros) >= 1


def test_validate_total_registros():
    records = [_c100(), _c100(), _d100()]
    r = get_rules_engine().validate(records)
    assert r.total_registros == 3


def test_validate_resumo_com_violacoes():
    records = [_c100(vl_bc_icms="-1,00")]
    r = get_rules_engine().validate(records)
    assert "violação" in r.resumo


def test_validate_multiplas_violacoes_acumuladas():
    # Um C100 com 2 erros (base e valor negativos)
    records = [_c100(vl_bc_icms="-100,00", vl_icms="-10,00")]
    r = get_rules_engine().validate(records)
    ids = {x.regra_id for x in r.resultados}
    assert "ICMS-001" in ids
    assert "ICMS-002" in ids


def test_validate_campos_ausentes_nao_geram_excecao():
    empty = SpedRecord(
        bloco="C", tipo_registro="C100", campos={}, numero_linha=1, raw=""
    )
    r = get_rules_engine().validate([empty])
    assert isinstance(r, ApuracaoResult)


def test_validate_tipo_registro_ignorado_quando_nao_match():
    # M200 rules não devem disparar para C100
    records = [_c100()]
    r = get_rules_engine().validate(records)
    ids = {x.regra_id for x in r.resultados}
    assert "PIS-M-001" not in ids


# ─────────────────────────────────────────────────────────────────────────────
# Regimes
# ─────────────────────────────────────────────────────────────────────────────


def test_todos_regimes_aplicam_c100():
    for regime in ("lucro_real", "lucro_presumido", "simples_nacional"):
        results = get_rules_engine(regime).apply_rules(_c100(vl_icms="-5,00"))
        assert any(x.regra_id == "ICMS-002" for x in results), regime


def test_numero_linha_preservado():
    record = _c100(vl_icms="-1,00")
    record.numero_linha = 99
    results = FiscalRulesEngine().apply_rules(record)
    assert all(r.numero_linha == 99 for r in results)


def test_valor_encontrado_preservado():
    record = _c100(vl_icms="-5,00")
    results = FiscalRulesEngine().apply_rules(record)
    icms_erros = [r for r in results if r.regra_id == "ICMS-002"]
    assert icms_erros[0].valor_encontrado == "-5,00"


def test_dica_presente_nas_violacoes():
    results = FiscalRulesEngine().apply_rules(_c100(vl_icms="-1,00"))
    icms = next(r for r in results if r.regra_id == "ICMS-002")
    assert icms.dica != ""
