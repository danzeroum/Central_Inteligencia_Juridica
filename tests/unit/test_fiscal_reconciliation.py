"""Testes unitários para reconciliação cross-file de documentos fiscais."""

from __future__ import annotations

import pytest

from src.fiscal.reconciliation import (
    ReconciliationIssue,
    ReconciliationResult,
    Severidade,
    _diff_doc,
    _diff_valor,
    _normaliza_doc,
    _normaliza_valor,
    reconciliar_a100_nfse,
    reconciliar_c100_nfe,
    reconciliar_d100_cte,
    reconciliar_m200_totais,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def test_normaliza_doc_cnpj():
    assert _normaliza_doc("12.345.678/0001-95") == "12345678000195"


def test_normaliza_doc_cpf():
    assert _normaliza_doc("123.456.789-09") == "12345678909"


def test_normaliza_doc_vazio():
    assert _normaliza_doc("") == ""
    assert _normaliza_doc(None) == ""


def test_normaliza_valor_virgula():
    assert _normaliza_valor("1.234,56") == pytest.approx(1234.56)


def test_normaliza_valor_ponto():
    assert _normaliza_valor("1234.56") == pytest.approx(1234.56)


def test_normaliza_valor_invalido():
    assert _normaliza_valor("N/A") is None
    assert _normaliza_valor("") is None


def test_diff_valor_sem_divergencia():
    issues = []
    _diff_valor(issues, "vl_doc", "1000,00", "1000,00")
    assert issues == []


def test_diff_valor_aviso_pequeno():
    issues = []
    _diff_valor(issues, "vl_doc", "1000,50", "1000,00")
    assert len(issues) == 1
    assert issues[0].severidade == Severidade.AVISO


def test_diff_valor_erro_grande():
    issues = []
    _diff_valor(issues, "vl_doc", "2000,00", "1000,00")
    assert len(issues) == 1
    assert issues[0].severidade == Severidade.ERRO


def test_diff_doc_igual():
    issues = []
    _diff_doc(issues, "cnpj", "12.345.678/0001-95", "12345678000195")
    assert issues == []


def test_diff_doc_divergente():
    issues = []
    _diff_doc(issues, "cnpj", "12.345.678/0001-95", "98.765.432/0001-55")
    assert len(issues) == 1
    assert issues[0].severidade == Severidade.ERRO


# ─────────────────────────────────────────────────────────────────────────────
# ReconciliationResult
# ─────────────────────────────────────────────────────────────────────────────


def test_reconciliation_result_defaults():
    r = ReconciliationResult(aprovado=True)
    assert r.aprovado is True
    assert r.issues == []
    assert r.resumo == ""
    assert r.erros == []
    assert r.avisos == []


def test_reconciliation_result_filter_erros():
    issue_erro = ReconciliationIssue(
        severidade=Severidade.ERRO,
        campo="x",
        valor_a="a",
        valor_b="b",
        descricao="erro",
    )
    issue_aviso = ReconciliationIssue(
        severidade=Severidade.AVISO,
        campo="y",
        valor_a="c",
        valor_b="d",
        descricao="aviso",
    )
    r = ReconciliationResult(aprovado=False, issues=[issue_erro, issue_aviso])
    assert r.erros == [issue_erro]
    assert r.avisos == [issue_aviso]


# ─────────────────────────────────────────────────────────────────────────────
# reconciliar_c100_nfe
# ─────────────────────────────────────────────────────────────────────────────

_CHAVE_NFE = "35250112345678000195550010000000421234567890"

_C100_OK = {
    "chv_nfe": _CHAVE_NFE,
    "cod_part": "12345678000195",
    "vl_doc": "1000,00",
    "vl_icms": "120,00",
    "vl_pis": "6,50",
    "vl_cofins": "30,00",
}

_NFE_CAMPOS_OK = {
    "chave_nfe": _CHAVE_NFE,
    "emit_cnpj": "12345678000195",
    "vnf": "1000.00",
    "vicms": "120.00",
    "vpis": "6.50",
    "vcofins": "30.00",
}


def test_c100_nfe_aprovado_sem_divergencias():
    r = reconciliar_c100_nfe(_C100_OK, _NFE_CAMPOS_OK)
    assert r.aprovado is True
    assert r.issues == []
    assert "aprovada" in r.resumo


def test_c100_nfe_chave_divergente():
    nfe = {**_NFE_CAMPOS_OK, "chave_nfe": "9" * 44}
    r = reconciliar_c100_nfe(_C100_OK, nfe)
    erros = [i for i in r.issues if i.campo == "chv_nfe"]
    assert len(erros) == 1
    assert erros[0].severidade == Severidade.ERRO
    assert r.aprovado is False


def test_c100_nfe_valor_divergente_erro():
    c100 = {**_C100_OK, "vl_doc": "2000,00"}
    r = reconciliar_c100_nfe(c100, _NFE_CAMPOS_OK)
    issues_doc = [i for i in r.issues if i.campo == "vl_doc"]
    assert len(issues_doc) == 1
    assert issues_doc[0].severidade == Severidade.ERRO
    assert r.aprovado is False


def test_c100_nfe_cnpj_divergente():
    nfe = {**_NFE_CAMPOS_OK, "emit_cnpj": "99.999.999/0001-99"}
    c100 = {**_C100_OK, "cod_part": "11111111000111"}
    r = reconciliar_c100_nfe(c100, nfe)
    cnpj_issues = [i for i in r.issues if i.campo == "cnpj_emit"]
    assert len(cnpj_issues) == 1


def test_c100_nfe_sem_chave_nao_gera_erro():
    c100 = {**_C100_OK, "chv_nfe": ""}
    nfe = {**_NFE_CAMPOS_OK, "chave_nfe": ""}
    r = reconciliar_c100_nfe(c100, nfe)
    chave_issues = [i for i in r.issues if i.campo == "chv_nfe"]
    assert chave_issues == []


def test_c100_nfe_pis_aviso_pequena_diff():
    c100 = {**_C100_OK, "vl_pis": "6,51"}
    r = reconciliar_c100_nfe(c100, _NFE_CAMPOS_OK)
    pis_issues = [i for i in r.issues if i.campo == "vl_pis"]
    assert len(pis_issues) == 1
    assert pis_issues[0].severidade == Severidade.AVISO


# ─────────────────────────────────────────────────────────────────────────────
# reconciliar_d100_cte
# ─────────────────────────────────────────────────────────────────────────────

_CHAVE_CTE = "35250112345678000395570010000000011234567890"

_D100_OK = {
    "chv_cte": _CHAVE_CTE,
    "vl_doc": "500,00",
    "vl_icms": "60,00",
}

_CTE_CAMPOS_OK = {
    "chave_cte": _CHAVE_CTE,
    "vl_tprest": "500.00",
    "v_icms": "60.00",
}


def test_d100_cte_aprovado():
    r = reconciliar_d100_cte(_D100_OK, _CTE_CAMPOS_OK)
    assert r.aprovado is True
    assert r.issues == []


def test_d100_cte_chave_divergente():
    cte = {**_CTE_CAMPOS_OK, "chave_cte": "1" * 44}
    r = reconciliar_d100_cte(_D100_OK, cte)
    assert r.aprovado is False
    assert any(i.campo == "chv_cte" for i in r.issues)


def test_d100_cte_valor_divergente():
    d100 = {**_D100_OK, "vl_doc": "800,00"}
    r = reconciliar_d100_cte(d100, _CTE_CAMPOS_OK)
    assert any(i.campo == "vl_doc" for i in r.issues)


def test_d100_cte_icms_divergente():
    d100 = {**_D100_OK, "vl_icms": "100,00"}
    r = reconciliar_d100_cte(d100, _CTE_CAMPOS_OK)
    assert any(i.campo == "vl_icms" for i in r.issues)


# ─────────────────────────────────────────────────────────────────────────────
# reconciliar_a100_nfse
# ─────────────────────────────────────────────────────────────────────────────

_A100_OK = {
    "chv_nfse": "42",
    "num_doc": "42",
    "vl_doc": "3000,00",
    "vl_pis": "19,50",
    "vl_cofins": "90,00",
}

_NFSE_CAMPOS_OK = {
    "numero": "42",
    "vl_servicos": "3000.00",
    "vl_pis": "19.50",
    "vl_cofins": "90.00",
}


def test_a100_nfse_aprovado():
    r = reconciliar_a100_nfse(_A100_OK, _NFSE_CAMPOS_OK)
    assert r.aprovado is True


def test_a100_nfse_valor_divergente():
    a100 = {**_A100_OK, "vl_doc": "5000,00"}
    r = reconciliar_a100_nfse(a100, _NFSE_CAMPOS_OK)
    assert any(i.campo == "vl_doc" for i in r.issues)


def test_a100_nfse_numero_divergente_aviso():
    a100 = {**_A100_OK, "chv_nfse": "99"}
    r = reconciliar_a100_nfse(a100, _NFSE_CAMPOS_OK)
    num_issues = [i for i in r.issues if i.campo == "num_nfse"]
    assert len(num_issues) == 1
    assert num_issues[0].severidade == Severidade.AVISO


# ─────────────────────────────────────────────────────────────────────────────
# reconciliar_m200_totais
# ─────────────────────────────────────────────────────────────────────────────

_M200_OK = {"vl_tot_cont_nc_per": "36,67"}

_REGISTROS_C100_OK = [
    {"vl_pis": "6,50"},
    {"vl_pis": "19,50"},
    {"vl_pis": "10,67"},
]


def test_m200_totais_aprovado():
    r = reconciliar_m200_totais(_M200_OK, _REGISTROS_C100_OK)
    assert r.aprovado is True
    assert r.issues == []


def test_m200_totais_divergencia_grande():
    m200 = {"vl_tot_cont_nc_per": "100,00"}
    r = reconciliar_m200_totais(m200, _REGISTROS_C100_OK)
    assert any(i.campo == "vl_pis_apuracao" for i in r.issues)


def test_m200_totais_lista_vazia():
    r = reconciliar_m200_totais(_M200_OK, [])
    # Soma zero vs M200 diverge mas não é ERRO
    issues_apuracao = [i for i in r.issues if i.campo == "vl_pis_apuracao"]
    # Se divergência > 1.0 → AVISO
    if issues_apuracao:
        assert issues_apuracao[0].severidade == Severidade.AVISO


def test_m200_sem_valor_nao_gera_issue():
    r = reconciliar_m200_totais({}, _REGISTROS_C100_OK)
    assert r.aprovado is True
    assert r.issues == []


# ─────────────────────────────────────────────────────────────────────────────
# Severidade Enum
# ─────────────────────────────────────────────────────────────────────────────


def test_severidade_valores():
    assert Severidade.ERRO == "erro"
    assert Severidade.AVISO == "aviso"
    assert Severidade.INFO == "info"
