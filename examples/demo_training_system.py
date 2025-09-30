"""Demonstração do Sistema de Treinamento Contínuo."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.training.learning_metrics import get_metrics_collector
from src.training.training_manager import TrainingManager


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


async def demo_basic_training() -> None:
    """Demonstra ciclo básico de treinamento."""

    print("\n" + "=" * 60)
    print("🎓 DEMO 1: Ciclo Básico de Treinamento")
    print("=" * 60)

    manager = TrainingManager()
    agent_type = "TJSP"

    print(f"\n📊 Submetendo feedback para {agent_type}...")

    feedback_scenarios = [
        {"success": True, "latency": 0.45, "rating": 0.9, "desc": "Status check rápido"},
        {"success": True, "latency": 0.52, "rating": 0.85, "desc": "Consulta processual"},
        {"success": True, "latency": 0.48, "rating": 0.88, "desc": "Movimentações"},
        {"success": False, "latency": 1.20, "rating": 0.50, "desc": "Timeout na API"},
        {"success": True, "latency": 0.43, "rating": 0.92, "desc": "Status check OK"},
        {"success": True, "latency": 0.47, "rating": 0.87, "desc": "Consulta rápida"},
        {"success": True, "latency": 0.51, "rating": 0.86, "desc": "Dados completos"},
        {"success": True, "latency": 0.44, "rating": 0.91, "desc": "Resposta precisa"},
        {"success": True, "latency": 0.49, "rating": 0.89, "desc": "Processo encontrado"},
        {"success": True, "latency": 0.46, "rating": 0.90, "desc": "Informação correta"},
    ]

    for idx, scenario in enumerate(feedback_scenarios, 1):
        await manager.process_feedback(
            agent_type=agent_type,
            task_result={
                "success": scenario["success"],
                "latency": scenario["latency"],
                "route": "default",
            },
            user_rating=scenario["rating"],
        )
        print(f"  [{idx}/10] ✓ {scenario['desc']} - Rating: {scenario['rating']}")

    pending = len(manager.feedback_queue[agent_type])
    print(f"\n✅ Total de {pending} feedbacks na fila")

    print("\n🚀 Iniciando sessão de treinamento...")
    result = await manager.train_agent(agent_type)

    print(f"\n📈 Resultado do Treinamento:")
    print(f"  Status: {result['status']}")
    print(f"  Feedback Processado: {result['feedback_processed']}")
    print("\n  Métricas:")
    for metric, value in result["metrics"].items():
        print(f"    {metric}: {value:.4f}")

    if result["improvements"]:
        print("\n  Melhorias:")
        for metric, improvement in result["improvements"].items():
            sign = "+" if improvement >= 0 else ""
            print(f"    {metric}: {sign}{improvement:.2f}%")
    else:
        print("\n  (Primeira sessão - baseline estabelecido)")

    stats = manager.get_training_stats(agent_type)
    print(f"\n📊 Estatísticas Atualizadas:")
    print(f"  Total de Sessões: {stats['total_sessions']}")
    print(f"  Total de Feedback: {stats['total_feedback']}")
    print(f"  Última Sessão: {stats['last_training']}")


async def demo_metrics_analysis() -> None:
    """Demonstra análise de métricas de aprendizado."""

    print("\n" + "=" * 60)
    print("📊 DEMO 2: Análise de Métricas de Aprendizado")
    print("=" * 60)

    collector = get_metrics_collector()
    agent = "TJMG"

    print(f"\n📝 Registrando métricas para {agent}...")

    accuracy_values = [0.75, 0.76, 0.78, 0.79, 0.81, 0.83, 0.84, 0.85, 0.87, 0.88]
    latency_values = [0.55, 0.54, 0.52, 0.51, 0.49, 0.48, 0.47, 0.46, 0.45, 0.44]

    for idx, (acc, lat) in enumerate(zip(accuracy_values, latency_values), 1):
        collector.record(agent, "accuracy", acc, metadata={"iteration": idx})
        collector.record(agent, "latency", lat, metadata={"iteration": idx})
        print(f"  [{idx}/10] Accuracy: {acc:.2f} | Latency: {lat:.2f}s")

    print("\n📈 Análise de Accuracy:")
    summary = collector.get_metric_summary(agent, "accuracy")
    print(f"  Média: {summary['statistics']['mean']:.4f}")
    print(f"  Desvio Padrão: {summary['statistics']['std']:.4f}")
    print(f"  P95: {summary['statistics']['p95']:.4f}")
    print(f"  Tendência: {summary['trend']}")

    learning_rate = collector.calculate_learning_rate(agent, "accuracy", time_window_hours=24)
    if learning_rate:
        print(f"  Taxa de Aprendizado: {learning_rate:.4f} por hora")

    print("\n⚡ Análise de Latência:")
    summary = collector.get_metric_summary(agent, "latency")
    print(f"  Média: {summary['statistics']['mean']:.4f}s")
    print(f"  P50: {summary['statistics']['p50']:.4f}s")
    print(f"  P95: {summary['statistics']['p95']:.4f}s")
    print(f"  Tendência: {summary['trend']}")

    print("\n🔍 Detecção de Anomalias:")
    collector.record(agent, "latency", 2.5, metadata={"anomaly": True})
    anomalies = collector.detect_anomalies(agent, "latency", threshold_std=2.0)

    if anomalies:
        print(f"  ⚠️  {len(anomalies)} anomalia(s) detectada(s):")
        for anomaly in anomalies:
            print(
                f"    Valor: {anomaly['value']:.2f}s "
                f"(Desvio: {anomaly['deviation_percent']:.1f}%, "
                f"Z-score: {anomaly['z_score']:.2f})"
            )
    else:
        print("  ✓ Nenhuma anomalia detectada")


async def demo_agent_comparison() -> None:
    """Demonstra comparação entre agentes."""

    print("\n" + "=" * 60)
    print("⚖️  DEMO 3: Comparação Entre Agentes")
    print("=" * 60)

    collector = get_metrics_collector()

    agents_data = {
        "TJSP": [0.85, 0.86, 0.87, 0.88, 0.89, 0.90, 0.91, 0.92],
        "TJRS": [0.80, 0.81, 0.82, 0.83, 0.84, 0.85, 0.86, 0.87],
    }

    print("\n📊 Registrando métricas de accuracy...")
    for agent, values in agents_data.items():
        for value in values:
            collector.record(agent, "accuracy", value)
        print(f"  ✓ {agent}: {len(values)} registros")

    print("\n🔬 Comparação de Accuracy:")
    comparison = collector.compare_agents("TJSP", "TJRS", "accuracy")

    print(f"\n  {comparison['agent_a']['name']}:")
    print(f"    Média: {comparison['agent_a']['mean']:.4f}")
    print(f"    Tendência: {comparison['agent_a']['trend']}")

    print(f"\n  {comparison['agent_b']['name']}:")
    print(f"    Média: {comparison['agent_b']['mean']:.4f}")
    print(f"    Tendência: {comparison['agent_b']['trend']}")

    print("\n  📊 Resultado:")
    print(
        f"    Diferença Absoluta: {comparison['comparison']['absolute_difference']:.4f}"
    )
    print(
        f"    Diferença Percentual: {comparison['comparison']['percent_difference']:.2f}%"
    )
    print(
        f"    Melhor Performante: {comparison['comparison']['better_performer']}"
    )


async def demo_ab_testing() -> None:
    """Demonstra teste A/B entre variantes."""

    print("\n" + "=" * 60)
    print("🧪 DEMO 4: Teste A/B de Variantes")
    print("=" * 60)

    manager = TrainingManager()

    test_cases = [
        {"task": "status_check"},
        {"task": "process_query"},
        {"task": "get_movements"},
        {"task": "validate_data"},
        {"task": "check_availability"},
    ]

    print(f"\n🔬 Executando teste A/B com {len(test_cases)} casos...")
    print("  Variante A: TJSP_current")
    print("  Variante B: TJSP_optimized")

    result = await manager.run_ab_test(
        agent_a_type="TJSP_current",
        agent_b_type="TJSP_optimized",
        test_cases=test_cases,
    )

    print(f"\n📊 Resultados:")
    print(f"  Vencedor: Variante {result['winner']}")
    print(f"  Significância Estatística: {result['statistical_significance']:.2f}")
    print(f"\n  Scores:")
    print(f"    Variante A: {result['scores']['A']:.4f}")
    print(f"    Variante B: {result['scores']['B']:.4f}")

    if result["statistical_significance"] > 0.8:
        print(
            f"\n  ✅ Resultado estatisticamente significativo! "
            f"Variante {result['winner']} recomendada para produção."
        )
    else:
        print(
            f"\n  ⚠️  Significância baixa. Considere rodar mais testes antes de decidir."
        )


async def demo_complete_workflow() -> None:
    """Demonstra workflow completo de treinamento."""

    print("\n" + "=" * 60)
    print("🔄 DEMO 5: Workflow Completo de Treinamento")
    print("=" * 60)

    manager = TrainingManager()
    collector = get_metrics_collector()
    agent = "STF"

    print(f"\n🚀 Iniciando workflow completo para {agent}...")

    print("\n📝 Fase 1: Coleta de Feedback Inicial (10 amostras)...")
    for idx in range(10):
        await manager.process_feedback(
            agent_type=agent,
            task_result={
                "success": True,
                "latency": 0.5 + (idx * 0.02),
                "route": "default",
            },
            user_rating=0.75 + (idx * 0.015),
        )
        collector.record(agent, "accuracy", 0.75 + (idx * 0.015))

    print("  ✓ Feedback coletado")

    print("\n🎓 Fase 2: Primeiro Ciclo de Treinamento...")
    result1 = await manager.train_agent(agent)
    print(f"  ✓ Sessão concluída - Status: {result1['status']}")
    print("  ✓ Baseline estabelecido")

    print("\n📊 Fase 3: Nova Coleta de Feedback (melhorado)...")
    for idx in range(10):
        await manager.process_feedback(
            agent_type=agent,
            task_result={
                "success": True,
                "latency": 0.45 + (idx * 0.01),
                "route": "default",
            },
            user_rating=0.85 + (idx * 0.01),
        )
        collector.record(agent, "accuracy", 0.85 + (idx * 0.01))

    print("  ✓ Feedback melhorado coletado")

    print("\n🎓 Fase 4: Segundo Ciclo de Treinamento...")
    result2 = await manager.train_agent(agent)
    print(f"  ✓ Sessão concluída - Status: {result2['status']}")

    if result2["improvements"]:
        print("  📈 Melhorias detectadas:")
        for metric, improvement in result2["improvements"].items():
            sign = "+" if improvement >= 0 else ""
            print(f"    {metric}: {sign}{improvement:.2f}%")

    print("\n📊 Fase 5: Análise Final...")
    stats = manager.get_training_stats(agent)
    print(f"  Total de Sessões: {stats['total_sessions']}")
    print(f"  Total de Feedback: {stats['total_feedback']}")

    summary = collector.get_metric_summary(agent, "accuracy")
    print(f"  Accuracy Média: {summary['statistics']['mean']:.4f}")
    print(f"  Tendência: {summary['trend']}")

    print("\n✅ Workflow completo executado com sucesso!")


async def main() -> None:
    """Executa todas as demonstrações."""

    setup_logging()

    print("\n" + "=" * 60)
    print("🎓 SISTEMA DE TREINAMENTO CONTÍNUO - DEMONSTRAÇÃO")
    print("   BuildToFlip v6.1 - Reality Check")
    print("=" * 60)
    print(f"\n⏰ Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    demos = [
        ("Ciclo Básico", demo_basic_training),
        ("Análise de Métricas", demo_metrics_analysis),
        ("Comparação de Agentes", demo_agent_comparison),
        ("Teste A/B", demo_ab_testing),
        ("Workflow Completo", demo_complete_workflow),
    ]

    for idx, (name, demo_func) in enumerate(demos, 1):
        try:
            await demo_func()
            await asyncio.sleep(1)
        except Exception as exc:  # pragma: no cover - saída amigável
            print(f"\n❌ Erro na demo '{name}': {exc}")
            raise

    print("\n" + "=" * 60)
    print("✅ TODAS AS DEMONSTRAÇÕES CONCLUÍDAS COM SUCESSO!")
    print("=" * 60)
    print("\n📚 Próximos Passos:")
    print("  1. Acesse o Training Dashboard: http://localhost:8000/training-dashboard")
    print("  2. Experimente os endpoints REST: /api/v1/training/*")
    print("  3. Rode os testes: pytest tests/integration/test_training_system.py")
    print("  4. Leia a documentação completa: docs/training-system.md")
    print()


if __name__ == "__main__":
    asyncio.run(main())
