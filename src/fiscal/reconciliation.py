"""Reconciliação cross-file de documentos fiscais.

Compara e valida consistência entre:
- SPED EFD-ICMS/IPI ↔ NF-e XML
- SPED EFD-Contribuições ↔ NF-e (PIS/COFINS)
- CT-e XML ↔ SPED Bloco D
- NFS-e ↔ SPED Bloco A (EFD-Contrib)

Cada divergência é um ReconciliationIssue com severidade e descrição.
A reconciliação é stateless — recebe os dados já parseados e retorna resultado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Tipos
# ─────────────────────────────────────────────────────────────────────────────


class Severidade(str, Enum):
    ERRO = "erro"  # divergência que indica inconsistência real
    AVISO = "aviso"  # diferença tolerável (ex.: arredondamento)
    INFO = "info"  # observação sem impacto


@dataclass
class ReconciliationIssue:
    """Uma divergência encontrada na reconciliação."""

    severidade: Severidade
    campo: str
    valor_a: Any
    valor_b: Any
    descricao: str


@dataclass
class ReconciliationResult:
    """Resultado de uma operação de reconciliação."""

    aprovado: bool
    issues: List[ReconciliationIssue] = field(default_factory=list)
    resumo: str = ""

    @property
    def erros(self) -> List[ReconciliationIssue]:
        return [i for i in self.issues if i.severidade == Severidade.ERRO]

    @property
    def avisos(self) -> List[ReconciliationIssue]:
        return [i for i in self.issues if i.severidade == Severidade.AVISO]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _normaliza_doc(doc: str) -> str:
    """Remove pontuação de CNPJ/CPF para comparação."""
    return "".join(c for c in (doc or "") if c.isdigit())


def _normaliza_valor(v: str) -> Optional[float]:
    """Converte string decimal (vírgula ou ponto) para float, ou None."""
    v = (v or "").strip()
    if "," in v:
        # SPED format: "1.234,56" — dot=thousands separator, comma=decimal
        v = v.replace(".", "").replace(",", ".")
    # else: XML/PDF format "1000.00" — dot is already the decimal separator
    try:
        return float(v)
    except ValueError:
        return None


def _diff_valor(
    issues: List[ReconciliationIssue],
    campo: str,
    val_a: str,
    val_b: str,
    tolerancia: float = 0.005,
) -> None:
    """Registra AVISO se |a - b| <= tolerancia, ERRO caso contrário."""
    fa = _normaliza_valor(val_a)
    fb = _normaliza_valor(val_b)
    if fa is None or fb is None:
        if val_a != val_b:
            issues.append(
                ReconciliationIssue(
                    severidade=Severidade.AVISO,
                    campo=campo,
                    valor_a=val_a,
                    valor_b=val_b,
                    descricao=f"Valores de {campo!r} não comparáveis: {val_a!r} vs {val_b!r}",
                )
            )
        return
    diff = abs(fa - fb)
    if diff > tolerancia:
        sev = Severidade.AVISO if diff <= 1.0 else Severidade.ERRO
        issues.append(
            ReconciliationIssue(
                severidade=sev,
                campo=campo,
                valor_a=val_a,
                valor_b=val_b,
                descricao=f"Divergência em {campo!r}: {val_a} (SPED) vs {val_b} (XML), diff={diff:.2f}",
            )
        )


def _diff_doc(
    issues: List[ReconciliationIssue],
    campo: str,
    val_a: str,
    val_b: str,
) -> None:
    if _normaliza_doc(val_a) != _normaliza_doc(val_b):
        issues.append(
            ReconciliationIssue(
                severidade=Severidade.ERRO,
                campo=campo,
                valor_a=val_a,
                valor_b=val_b,
                descricao=f"Divergência em {campo!r}: {val_a!r} vs {val_b!r}",
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# Reconciliações específicas
# ─────────────────────────────────────────────────────────────────────────────


def reconciliar_c100_nfe(
    sped_c100: Dict[str, Any],
    nfe_campos: Dict[str, Any],
    nfe_itens: Optional[List[Dict[str, Any]]] = None,
) -> ReconciliationResult:
    """Reconcilia um registro C100 do SPED EFD-ICMS com uma NF-e XML.

    Args:
        sped_c100: Campos do registro C100 (saída de SpedEfdIcmsParser).
        nfe_campos: Campos do XmlParseResult.campos de NFeParser.
        nfe_itens: Lista de itens do XmlParseResult.itens (opcional).
    """
    issues: List[ReconciliationIssue] = []

    # Chave NF-e
    chave_sped = (sped_c100.get("chv_nfe") or "").strip()
    chave_xml = (nfe_campos.get("chave_nfe") or nfe_campos.get("_chave") or "").strip()
    if chave_sped and chave_xml and chave_sped != chave_xml:
        issues.append(
            ReconciliationIssue(
                severidade=Severidade.ERRO,
                campo="chv_nfe",
                valor_a=chave_sped,
                valor_b=chave_xml,
                descricao="Chave NF-e diverge entre SPED C100 e XML",
            )
        )

    # CNPJ emitente
    _diff_doc(
        issues,
        "cnpj_emit",
        sped_c100.get("cod_part", ""),
        nfe_campos.get("emit_cnpj", ""),
    )

    # Valor total do documento
    _diff_valor(
        issues, "vl_doc", sped_c100.get("vl_doc", ""), nfe_campos.get("vnf", "")
    )

    # ICMS
    _diff_valor(
        issues, "vl_icms", sped_c100.get("vl_icms", ""), nfe_campos.get("vicms", "")
    )

    # PIS/COFINS
    _diff_valor(
        issues, "vl_pis", sped_c100.get("vl_pis", ""), nfe_campos.get("vpis", "")
    )
    _diff_valor(
        issues,
        "vl_cofins",
        sped_c100.get("vl_cofins", ""),
        nfe_campos.get("vcofins", ""),
    )

    aprovado = not any(i.severidade == Severidade.ERRO for i in issues)
    n_issues = len(issues)
    resumo = (
        "Reconciliação C100/NF-e aprovada sem divergências"
        if not issues
        else f"Reconciliação C100/NF-e: {n_issues} issue(s) encontrada(s)"
    )
    return ReconciliationResult(aprovado=aprovado, issues=issues, resumo=resumo)


def reconciliar_d100_cte(
    sped_d100: Dict[str, Any],
    cte_campos: Dict[str, Any],
) -> ReconciliationResult:
    """Reconcilia um registro D100 do SPED EFD-ICMS com um CT-e XML."""
    issues: List[ReconciliationIssue] = []

    # Chave CT-e
    chave_sped = (sped_d100.get("chv_cte") or "").strip()
    chave_xml = (cte_campos.get("chave_cte") or cte_campos.get("_chave") or "").strip()
    if chave_sped and chave_xml and chave_sped != chave_xml:
        issues.append(
            ReconciliationIssue(
                severidade=Severidade.ERRO,
                campo="chv_cte",
                valor_a=chave_sped,
                valor_b=chave_xml,
                descricao="Chave CT-e diverge entre SPED D100 e XML",
            )
        )

    # Valor do documento
    _diff_valor(
        issues, "vl_doc", sped_d100.get("vl_doc", ""), cte_campos.get("vl_tprest", "")
    )

    # ICMS
    _diff_valor(
        issues, "vl_icms", sped_d100.get("vl_icms", ""), cte_campos.get("v_icms", "")
    )

    aprovado = not any(i.severidade == Severidade.ERRO for i in issues)
    resumo = (
        "Reconciliação D100/CT-e aprovada"
        if not issues
        else f"Reconciliação D100/CT-e: {len(issues)} issue(s)"
    )
    return ReconciliationResult(aprovado=aprovado, issues=issues, resumo=resumo)


def reconciliar_a100_nfse(
    sped_a100: Dict[str, Any],
    nfse_campos: Dict[str, Any],
) -> ReconciliationResult:
    """Reconcilia um registro A100 do SPED EFD-Contrib com uma NFS-e XML."""
    issues: List[ReconciliationIssue] = []

    # Número/chave NFS-e
    chave_sped = (sped_a100.get("chv_nfse") or sped_a100.get("num_doc") or "").strip()
    chave_xml = (nfse_campos.get("numero") or "").strip()
    if chave_sped and chave_xml and chave_sped != chave_xml:
        issues.append(
            ReconciliationIssue(
                severidade=Severidade.AVISO,
                campo="num_nfse",
                valor_a=chave_sped,
                valor_b=chave_xml,
                descricao="Número NFS-e diverge entre SPED A100 e XML",
            )
        )

    # Valor total
    _diff_valor(
        issues,
        "vl_doc",
        sped_a100.get("vl_doc", ""),
        nfse_campos.get("vl_servicos", ""),
    )

    # PIS/COFINS
    _diff_valor(
        issues, "vl_pis", sped_a100.get("vl_pis", ""), nfse_campos.get("vl_pis", "")
    )
    _diff_valor(
        issues,
        "vl_cofins",
        sped_a100.get("vl_cofins", ""),
        nfse_campos.get("vl_cofins", ""),
    )

    aprovado = not any(i.severidade == Severidade.ERRO for i in issues)
    resumo = (
        "Reconciliação A100/NFS-e aprovada"
        if not issues
        else f"Reconciliação A100/NFS-e: {len(issues)} issue(s)"
    )
    return ReconciliationResult(aprovado=aprovado, issues=issues, resumo=resumo)


def reconciliar_m200_totais(
    sped_m200: Dict[str, Any],
    registros_c100: List[Dict[str, Any]],
) -> ReconciliationResult:
    """Valida se M200 (apuração PIS) é consistente com soma dos C100.

    Compara vl_tot_cont_nc_per do M200 com a soma dos vl_pis dos C100
    (saída do SpedEfdContribParser).
    """
    issues: List[ReconciliationIssue] = []

    soma_pis = sum(_normaliza_valor(r.get("vl_pis", "")) or 0.0 for r in registros_c100)
    m200_total = _normaliza_valor(sped_m200.get("vl_tot_cont_nc_per", ""))

    if m200_total is not None:
        diff = abs(soma_pis - m200_total)
        if diff > 1.0:
            issues.append(
                ReconciliationIssue(
                    severidade=Severidade.AVISO,
                    campo="vl_pis_apuracao",
                    valor_a=str(soma_pis),
                    valor_b=str(m200_total),
                    descricao=(
                        f"Soma PIS dos C100 ({soma_pis:.2f}) difere de M200 "
                        f"vl_tot_cont_nc_per ({m200_total:.2f}), diff={diff:.2f}"
                    ),
                )
            )

    aprovado = not any(i.severidade == Severidade.ERRO for i in issues)
    resumo = (
        "Reconciliação M200/C100 PIS aprovada"
        if not issues
        else f"Reconciliação M200/C100: {len(issues)} issue(s)"
    )
    return ReconciliationResult(aprovado=aprovado, issues=issues, resumo=resumo)
