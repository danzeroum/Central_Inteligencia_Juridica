"""Demo interativo da Central de Inteligência Jurídica.

Executa uma consulta jurídica completa e exibe o pipeline em tempo real:

    SupervisorAgent (identificação)  ->  TribunalAgents (paralelo)
        ->  WeightedConsensusEngine (consenso)  ->  resposta final

As etapas de *identificação* e *consenso* usam código REAL do projeto
(``TribunalIdentifier`` e ``WeightedConsensusEngine``). A consulta a cada
tribunal é simulada — não há chamadas externas a tribunais ou ao Ollama —,
o que mantém o demo executável offline.

Uso:
    python examples/demo_consulta.py
    python examples/demo_consulta.py --consulta "sua consulta aqui"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Any, Dict, List

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.consensus.weighted_voting import WeightedConsensusEngine
from src.routing.tribunal_identifier import TribunalIdentifier

# Threshold mínimo de confiança para entrega autônoma (abaixo disso -> HITL).
HITL_THRESHOLD = 0.75

# Fundamentos simulados por tribunal (substituiriam a consulta real ao tribunal).
FUNDAMENTOS_SIMULADOS: Dict[str, Dict[str, Any]] = {
    "TJSP": {"fundamento": "Súmula 385 TJSP", "confianca": 0.89},
    "TJMG": {"fundamento": "Art. 186 c/c 927 CC", "confianca": 0.84},
    "TJRS": {"fundamento": "Enunciado 44 TJRS", "confianca": 0.82},
    "TJRJ": {"fundamento": "Súmula 75 TJRJ", "confianca": 0.86},
    "STF": {"fundamento": "RE 1.010.606 — Tema 533", "confianca": 0.95},
}
FUNDAMENTO_PADRAO = {"fundamento": "Jurisprudência consolidada", "confianca": 0.80}


# ── Helpers de apresentação ──────────────────────────────────────────────────
def banner() -> None:
    print("\n" + "═" * 60)
    print("  Central de Inteligência Jurídica — Demo")
    print("═" * 60 + "\n")


def etapa(nome: str, inicio: float) -> None:
    elapsed = (time.monotonic() - inicio) * 1000
    print(f"  ✓ {nome:<45} [{elapsed:>6.0f}ms]")


def secao(titulo: str) -> None:
    print(f"\n── {titulo} {'─' * max(0, 54 - len(titulo))}")


# ── Estágios do pipeline ─────────────────────────────────────────────────────
def identificar_tribunais(identifier: TribunalIdentifier, consulta: str) -> List[str]:
    """Estágio 1 — identificação real via ``TribunalIdentifier``."""

    tribunais = identifier.identify_all(consulta)
    return tribunais or [identifier.identify_primary(consulta)]


async def consultar_tribunal(tribunal: str) -> Dict[str, Any]:
    """Estágio 2 — consulta simulada a um tribunal (sem rede)."""

    await asyncio.sleep(0.15)
    dados = FUNDAMENTOS_SIMULADOS.get(tribunal, FUNDAMENTO_PADRAO)
    return {"tribunal": tribunal, **dados}


def consolidar_consenso(
    engine: WeightedConsensusEngine, respostas: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Estágio 3 — consenso ponderado real via ``WeightedConsensusEngine``."""

    proposals = {
        resposta["tribunal"]: {
            "confidence": resposta["confianca"],
            "proposal": {"fundamento": resposta["fundamento"]},
        }
        for resposta in respostas
    }
    return engine.reach_consensus(proposals, "jurisprudencia")


# ── Fluxo principal ──────────────────────────────────────────────────────────
async def executar_pipeline(consulta: str) -> None:
    banner()
    print(f'  Consulta: "{consulta}"\n')

    identifier = TribunalIdentifier.from_config()
    engine = WeightedConsensusEngine()
    t0 = time.monotonic()

    # 1. Identificação (SupervisorAgent / TribunalIdentifier)
    secao("1. SupervisorAgent — Identificação de Tribunais")
    t = time.monotonic()
    tribunais = identificar_tribunais(identifier, consulta)
    etapa(f"Tribunais: {', '.join(tribunais)}", t)

    # 2. TribunalAgents em paralelo
    secao("2. TribunalAgents — Execução Paralela")
    t = time.monotonic()
    respostas = await asyncio.gather(*(consultar_tribunal(tri) for tri in tribunais))
    for r in respostas:
        etapa(f"{r['tribunal']}: {r['fundamento']} (conf: {r['confianca']})", t)

    # 3. WeightedConsensusEngine
    secao("3. WeightedConsensusEngine — Consenso Ponderado")
    t = time.monotonic()
    consenso = consolidar_consenso(engine, respostas)
    strength = consenso["consensus_strength"]
    requer_hitl = strength < HITL_THRESHOLD
    fundamento_principal = consenso["decision"]["proposal"]["fundamento"]
    etapa(f"Tribunal decisor: {consenso['decision_maker']}", t)
    etapa(f"Força do consenso: {strength}", t)
    etapa(f"Concordância: {consenso['agreement_ratio']}", t)
    etapa(f"HITL necessário: {'Sim' if requer_hitl else 'Não'}", t)

    # 4. Resultado final
    secao("4. Resultado Final")
    total = (time.monotonic() - t0) * 1000
    print(f"""
  ┌─────────────────────────────────────────────────────┐
  │  Decisor:    {consenso['decision_maker']:<40}│
  │  Confiança:  {strength:<40}│
  │  Fundamento: {fundamento_principal:<40}│
  │  HITL:       {('Requer aprovação humana' if requer_hitl else 'Autônomo'):<40}│
  │  Tempo total:{f'{total:.0f}ms':<40}│
  └─────────────────────────────────────────────────────┘
    """)

    if requer_hitl:
        print("  ⚠️  Encaminhado para fila HITL — aguarda revisão humana\n")
    else:
        print(
            "  ✅ Resposta entregue autonomamente " "(confiança acima do threshold)\n"
        )


# ── Entry point ──────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo da Central de Inteligência Jurídica"
    )
    parser.add_argument(
        "--consulta",
        default="Jurisprudência sobre dano moral por negativação indevida "
        "no TJSP, TJMG e STF",
        help="Consulta jurídica a ser processada",
    )
    args = parser.parse_args()
    asyncio.run(executar_pipeline(args.consulta))


if __name__ == "__main__":
    main()
