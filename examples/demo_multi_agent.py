"""Demo script for multi-agent collaboration system."""

from __future__ import annotations

import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.agents.supervisor_agent import SupervisorAgent
from src.utils.ledger import DecisionLedger


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("logs/demo.log")],
    )


def run_demo() -> None:
    print("🚀 INICIANDO DEMONSTRAÇÃO DO SISTEMA MULTI-AGENT\n")

    setup_logging()
    ledger = DecisionLedger("logs/demo_ledger.json")
    supervisor = SupervisorAgent(ledger)

    test_scenarios = [
        {"name": "Consulta de Status TJSP", "task": "Verificar status do tribunal de São Paulo"},
        {
            "name": "Consulta de Processo TJMG",
            "task": "Consultar processo número 1234567-89.2024.8.26.1234 no TJMG",
        },
        {"name": "Status Múltiplos Tribunais", "task": "Preciso do status do TJRS e também do STF"},
        {"name": "Consulta Genérica", "task": "Informações sobre andamento processual"},
        {"name": "Teste Segurança", "task": "<script>alert('test')</script>Status do sistema"},
    ]

    print("📋 CENÁRIOS DE TESTE:")
    print("-" * 50)

    for index, scenario in enumerate(test_scenarios, 1):
        print(f"\n{index}. {scenario['name']}")
        print(f"   Tarefa: {scenario['task']}")
        print("   " + "=" * 40)

        result = supervisor.process_task(scenario["task"])

        print(f"   ✅ Status: {result['status']}")
        print(f"   🏛️  Tribunal: {result['tribunal_used']}")
        print(f"   📊 Operação: {result.get('supervisor_result', {}).get('operation', 'N/A')}")

        if result["status"] == "success":
            data = result.get("supervisor_result", {}).get("data", {})
            if "status" in data:
                print(f"   🔧 Status Sistema: {data['status']}")
            if "numero_processo" in data:
                print(f"   📄 Processo: {data['numero_processo']}")

    print("\n" + "=" * 60)
    print("📈 ESTATÍSTICAS FINAIS:")
    print("=" * 60)

    agent_stats = supervisor.get_agent_stats()
    ledger_stats = ledger.get_agent_stats()

    print(f"🤖 Agentes Ativos: {agent_stats['total_delegates']}")
    print(f"📋 Tribunais: {', '.join(agent_stats['active_tribunals'])}")
    print(f"📊 Tarefas Processadas: {agent_stats['total_tasks_processed']}")
    print(f"📒 Entradas no Ledger: {ledger_stats.get('total_entries', 0)}")

    report_file = ledger.export_report()
    print(f"📄 Relatório Exportado: {report_file}")

    print("\n🎯 DEMONSTRAÇÃO CONCLUÍDA COM SUCESSO!")


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    try:
        run_demo()
    except Exception as exc:  # pragma: no cover - demonstration safety
        print(f"❌ Erro durante demonstração: {exc}")
        raise
