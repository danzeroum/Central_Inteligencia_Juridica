"""Carregador de regras fiscais a partir de YAML (Bloco C — S-C.3).

Mini-DSL segura: sem eval, sem exec, operadores enumerados.
YAML inválido → falha explícita na carga (nunca silêncio).

Operadores de check:
  Simples: negative, positive, zero_not_none, missing, not_missing,
           gt, lt, eq_str, ne_str, in_set, not_in_set,
           starts_with, not_starts_with, starts_with_any, not_starts_with_any,
           str_len_ne, gt_field, lt_field, not_in_numeric_list, pct_divergence
  Compostos: all, any, not
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set

import yaml

from .reconciliation import Severidade, _normaliza_valor

logger = logging.getLogger(__name__)

_RULES_DIR = Path(__file__).parent.parent.parent / "config" / "fiscal" / "rules"

_SEVERITY_MAP = {
    "erro": Severidade.ERRO,
    "aviso": Severidade.AVISO,
    "info": Severidade.INFO,
}
_VALID_REGIMES: FrozenSet[str] = frozenset(
    {"lucro_real", "lucro_presumido", "simples_nacional"}
)


class RuleCompileError(ValueError):
    """Raised when a rule YAML definition is invalid."""


def _v(campos: Dict[str, Any], campo: str) -> Optional[float]:
    return _normaliza_valor(str(campos.get(campo) or ""))


def _s(campos: Dict[str, Any], campo: str) -> str:
    return str(campos.get(campo) or "").strip()


def _compile_check(check_def: Any) -> Callable[[Dict[str, Any]], bool]:
    """Compile a check definition dict into a callable (no eval)."""
    if not isinstance(check_def, dict):
        raise RuleCompileError(
            f"'check' deve ser um dict, não {type(check_def).__name__}: {check_def!r}"
        )

    # ── Compound operators ─────────────────────────────────────────────────────
    if "all" in check_def:
        if not isinstance(check_def["all"], list):
            raise RuleCompileError("'all' deve ser uma lista de condições")
        conditions = [_compile_check(c) for c in check_def["all"]]
        return lambda c, conds=conditions: all(f(c) for f in conds)

    if "any" in check_def:
        if not isinstance(check_def["any"], list):
            raise RuleCompileError("'any' deve ser uma lista de condições")
        conditions = [_compile_check(c) for c in check_def["any"]]
        return lambda c, conds=conditions: any(f(c) for f in conds)

    op = check_def.get("operator")
    if not op:
        raise RuleCompileError(f"'check' sem 'operator': {check_def!r}")

    field = str(check_def.get("field", ""))

    # ── not (inversion) ───────────────────────────────────────────────────────
    if op == "not":
        if "condition" not in check_def:
            raise RuleCompileError("operador 'not' requer chave 'condition'")
        inner = _compile_check(check_def["condition"])
        return lambda c, fn=inner: not fn(c)

    # ── Single-field simple operators ─────────────────────────────────────────
    if op == "negative":
        return lambda c, f=field: (v := _v(c, f)) is not None and v < 0

    if op == "positive":
        return lambda c, f=field: (v := _v(c, f)) is not None and v > 0

    if op == "zero_not_none":
        return lambda c, f=field: (v := _v(c, f)) is not None and v == 0.0

    if op == "missing":
        return lambda c, f=field: str(c.get(f) or "").strip() == ""

    if op == "not_missing":
        return lambda c, f=field: str(c.get(f) or "").strip() != ""

    if op == "gt":
        if "value" not in check_def:
            raise RuleCompileError("operador 'gt' requer 'value'")
        value = float(check_def["value"])
        return lambda c, f=field, v=value: (n := _v(c, f)) is not None and n > v

    if op == "lt":
        if "value" not in check_def:
            raise RuleCompileError("operador 'lt' requer 'value'")
        value = float(check_def["value"])
        return lambda c, f=field, v=value: (n := _v(c, f)) is not None and n < v

    if op == "eq_str":
        if "value" not in check_def:
            raise RuleCompileError("operador 'eq_str' requer 'value'")
        value = str(check_def["value"])
        return lambda c, f=field, v=value: str(c.get(f) or "").strip() == v

    if op == "ne_str":
        if "value" not in check_def:
            raise RuleCompileError("operador 'ne_str' requer 'value'")
        value = str(check_def["value"])
        return lambda c, f=field, v=value: str(c.get(f) or "").strip() != v

    if op == "in_set":
        if "values" not in check_def:
            raise RuleCompileError("operador 'in_set' requer 'values'")
        values: Set[str] = {str(v) for v in check_def["values"]}
        return lambda c, f=field, vs=values: str(c.get(f) or "").strip() in vs

    if op == "not_in_set":
        if "values" not in check_def:
            raise RuleCompileError("operador 'not_in_set' requer 'values'")
        values = {str(v) for v in check_def["values"]}
        return lambda c, f=field, vs=values: str(c.get(f) or "").strip() not in vs

    if op == "starts_with":
        if "prefix" not in check_def:
            raise RuleCompileError("operador 'starts_with' requer 'prefix'")
        prefix = str(check_def["prefix"])
        return lambda c, f=field, p=prefix: str(c.get(f) or "").strip().startswith(p)

    if op == "not_starts_with":
        if "prefix" not in check_def:
            raise RuleCompileError("operador 'not_starts_with' requer 'prefix'")
        prefix = str(check_def["prefix"])
        return lambda c, f=field, p=prefix: (
            not str(c.get(f) or "").strip().startswith(p)
        )

    if op == "starts_with_any":
        if "prefixes" not in check_def:
            raise RuleCompileError("operador 'starts_with_any' requer 'prefixes'")
        prefixes = [str(p) for p in check_def["prefixes"]]
        return lambda c, f=field, ps=prefixes: any(
            str(c.get(f) or "").strip().startswith(p) for p in ps
        )

    if op == "not_starts_with_any":
        if "prefixes" not in check_def:
            raise RuleCompileError("operador 'not_starts_with_any' requer 'prefixes'")
        prefixes = [str(p) for p in check_def["prefixes"]]
        return lambda c, f=field, ps=prefixes: (
            not any(str(c.get(f) or "").strip().startswith(p) for p in ps)
        )

    if op == "str_len_ne":
        if "length" not in check_def:
            raise RuleCompileError("operador 'str_len_ne' requer 'length'")
        length = int(check_def["length"])
        return lambda c, f=field, lg=length: (
            (s := str(c.get(f) or "").strip()) != "" and len(s) != lg
        )

    # ── Two-field operators ───────────────────────────────────────────────────
    if op == "gt_field":
        if "ref_field" not in check_def:
            raise RuleCompileError("operador 'gt_field' requer 'ref_field'")
        ref = str(check_def["ref_field"])
        return lambda c, f=field, r=ref: (
            (v1 := _v(c, f)) is not None and (v2 := _v(c, r)) is not None and v1 > v2
        )

    if op == "lt_field":
        if "ref_field" not in check_def:
            raise RuleCompileError("operador 'lt_field' requer 'ref_field'")
        ref = str(check_def["ref_field"])
        return lambda c, f=field, r=ref: (
            (v1 := _v(c, f)) is not None and (v2 := _v(c, r)) is not None and v1 < v2
        )

    if op == "not_in_numeric_list":
        if "values" not in check_def:
            raise RuleCompileError("operador 'not_in_numeric_list' requer 'values'")
        values_list = [float(v) for v in check_def["values"]]
        tolerance = float(check_def.get("tolerance", 0.1))
        return lambda c, f=field, vs=values_list, tol=tolerance: (
            (n := _v(c, f)) is not None
            and n > 0
            and not any(abs(n - v) <= tol for v in vs)
        )

    if op == "pct_divergence":
        for req in ("base_field", "rate_field"):
            if req not in check_def:
                raise RuleCompileError(f"operador 'pct_divergence' requer '{req}'")
        base_field = str(check_def["base_field"])
        rate_field = str(check_def["rate_field"])
        threshold = float(check_def.get("threshold", 0.01))
        return lambda c, f=field, bf=base_field, rf=rate_field, t=threshold: (
            (vb := _v(c, bf)) is not None
            and (vi := _v(c, f)) is not None
            and (al := _v(c, rf)) is not None
            and al > 0
            and vb > 0
            and abs(vi - vb * al / 100.0) / (vb * al / 100.0) > t
        )

    raise RuleCompileError(f"Operador desconhecido: {op!r}")


def _validate_rule_def(rule_def: Dict[str, Any], source: str) -> None:
    """Validate required fields in a rule definition dict."""
    for key in ("id", "tipo_registro", "campo", "descricao", "severidade", "check"):
        if key not in rule_def:
            raise RuleCompileError(
                f"Regra em {source!r} sem campo obrigatório {key!r}: {rule_def}"
            )
    sev = str(rule_def["severidade"]).lower()
    if sev not in _SEVERITY_MAP:
        raise RuleCompileError(
            f"Severidade inválida {sev!r} em regra {rule_def['id']!r}. "
            f"Valores válidos: {list(_SEVERITY_MAP)}"
        )
    if "regimes" in rule_def:
        for r in rule_def["regimes"]:
            if r not in _VALID_REGIMES:
                raise RuleCompileError(
                    f"Regime inválido {r!r} em regra {rule_def['id']!r}"
                )


def _rule_from_def(
    rule_def: Dict[str, Any], source: str, uf: Optional[str] = None
) -> "FiscalRuleYaml":
    """Build a FiscalRuleYaml from a validated rule definition dict."""
    from .rules_engine import FiscalRule

    _validate_rule_def(rule_def, source)

    regimes_raw = rule_def.get("regimes", list(_VALID_REGIMES))
    regimes: FrozenSet[str] = frozenset(regimes_raw)

    check_fn = _compile_check(rule_def["check"])

    rule_uf = rule_def.get("uf") or uf

    return FiscalRule(
        id=str(rule_def["id"]),
        tipo_registro=str(rule_def["tipo_registro"]),
        campo=str(rule_def["campo"]),
        descricao=str(rule_def["descricao"]),
        severidade=_SEVERITY_MAP[str(rule_def["severidade"]).lower()],
        check=check_fn,
        dica=str(rule_def.get("dica", "")),
        regimes=regimes,
        uf=rule_uf,
    )


# Alias for type clarity
FiscalRuleYaml = object  # actual type is FiscalRule, imported lazily


def load_rules_from_file(yaml_path: Path) -> List[Any]:
    """Load and compile rules from a single YAML file.

    Raises RuleCompileError on any validation failure (never silent).
    """
    if not yaml_path.exists():
        raise RuleCompileError(f"Arquivo de regras não encontrado: {yaml_path}")

    try:
        content = yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise RuleCompileError(f"YAML inválido em {yaml_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuleCompileError(
            f"YAML em {yaml_path} deve ser um dict com chave 'rules'"
        )

    if "rules" not in data:
        raise RuleCompileError(f"YAML em {yaml_path} sem chave 'rules'")

    rules_raw = data["rules"]
    if not isinstance(rules_raw, list):
        raise RuleCompileError(f"'rules' em {yaml_path} deve ser uma lista")

    uf = data.get("uf")
    rules = []
    for rule_def in rules_raw:
        if not isinstance(rule_def, dict):
            raise RuleCompileError(
                f"Definição de regra inválida em {yaml_path}: {rule_def!r}"
            )
        rules.append(_rule_from_def(rule_def, str(yaml_path), uf=uf))

    logger.debug("Carregadas %d regras de %s", len(rules), yaml_path)
    return rules


def load_all_rules(uf: Optional[str] = None) -> List[Any]:
    """Load base rules + optional UF-specific rules.

    Args:
        uf: Two-letter UF code (e.g. "SP", "RJ"). If None, loads base rules only.

    Raises:
        RuleCompileError: On any YAML or structural error (fails fast, never silent).
    """
    base_path = _RULES_DIR / "base.yaml"
    rules = load_rules_from_file(base_path)

    if uf:
        uf_upper = uf.upper()
        uf_path = _RULES_DIR / "uf" / f"{uf_upper}.yaml"
        if uf_path.exists():
            uf_rules = load_rules_from_file(uf_path)
            rules.extend(uf_rules)
            logger.debug(
                "Carregadas %d regras UF-%s (total: %d)",
                len(uf_rules),
                uf_upper,
                len(rules),
            )
        else:
            logger.debug("Sem regras específicas para UF %s em %s", uf_upper, uf_path)

    return rules
