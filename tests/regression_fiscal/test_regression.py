"""Suíte de regressão tributária — Bloco C (S-C.3).

Cada cenário em tests/regression_fiscal/scenarios/*.yaml descreve:
  - registros inline (tipo_registro + campos)
  - regime + uf opcional
  - esperado: quais regra_ids devem violar, quais não devem, e aprovado

Executa na suíte normal (pytest tests/regression_fiscal/), rápido, sem DB.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml

from src.fiscal.parser.base import SpedRecord
from src.fiscal.rules_engine import get_rules_engine

_SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def _load_scenarios():
    """Descobre todos os arquivos de cenário YAML."""
    scenarios = list(_SCENARIOS_DIR.glob("*.yaml"))
    if not scenarios:
        pytest.fail(f"Nenhum cenário encontrado em {_SCENARIOS_DIR}")
    return scenarios


def _build_records(registros_def: List[Dict[str, Any]]) -> List[SpedRecord]:
    """Constrói SpedRecords a partir de definições inline."""
    records = []
    for i, r in enumerate(registros_def):
        records.append(
            SpedRecord(
                bloco=str(r.get("bloco", r.get("tipo_registro", "X")[0])),
                tipo_registro=str(r["tipo_registro"]),
                campos=dict(r.get("campos", {})),
                numero_linha=int(r.get("numero_linha", i + 1)),
                raw="",
            )
        )
    return records


@pytest.mark.parametrize(
    "scenario_file",
    _load_scenarios(),
    ids=lambda p: p.stem,
)
def test_regression_scenario(scenario_file: Path) -> None:
    """Executa um cenário de regressão tributária e valida o resultado."""
    try:
        data = yaml.safe_load(scenario_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        pytest.fail(f"YAML inválido em {scenario_file.name}: {exc}")

    # ── Campos obrigatórios ───────────────────────────────────────────────────
    for key in ("registros", "esperado"):
        assert key in data, f"Cenário {scenario_file.name} sem chave '{key}'"

    regime = str(data.get("regime", "lucro_real"))
    uf: Optional[str] = data.get("uf")

    registros_def = data["registros"]
    assert isinstance(
        registros_def, list
    ), f"'registros' deve ser lista em {scenario_file.name}"

    esperado = data["esperado"]
    assert isinstance(
        esperado, dict
    ), f"'esperado' deve ser dict em {scenario_file.name}"

    # ── Execução ──────────────────────────────────────────────────────────────
    engine = get_rules_engine(regime, uf=uf)
    records = _build_records(registros_def)
    result = engine.validate(records)

    found_ids = {r.regra_id for r in result.resultados}

    # ── Asserções ─────────────────────────────────────────────────────────────
    for regra_id in esperado.get("regra_ids_violadas", []):
        assert regra_id in found_ids, (
            f"[{scenario_file.stem}] Regra '{regra_id}' deveria ter disparado, "
            f"mas não disparou. Violações encontradas: {sorted(found_ids)}"
        )

    for regra_id in esperado.get("regra_ids_ausentes", []):
        assert regra_id not in found_ids, (
            f"[{scenario_file.stem}] Regra '{regra_id}' não deveria ter disparado, "
            f"mas disparou. Violações encontradas: {sorted(found_ids)}"
        )

    if "aprovado" in esperado:
        assert result.aprovado == esperado["aprovado"], (
            f"[{scenario_file.stem}] aprovado={result.aprovado} != "
            f"esperado={esperado['aprovado']}. Erros: {[r.regra_id for r in result.erros]}"
        )
