"""Demonstração prática de colaboração A2A entre agentes."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agents.tribunal_agent import TribunalAgent
from src.protocols.a2a_channel import get_a2a_channel

console = Console()


async def scenario_1_basic_communication() -> None:
    """Cenário 1: Comunicação básica entre dois tribunais."""
    console.print("\n[bold cyan]📡 CENÁRIO 1: Comunicação Básica A2A[/bold cyan]\n")
    
    tjsp = TribunalAgent("TJSP")
    tjmg = TribunalAgent("TJMG")
    
    # TJSP envia mensagem para TJMG
    console.print("🔹 TJSP enviando mensagem para TJMG...")
    await tjsp.send_to_agent(
        target_agent_id="tjmg_agent",
        message_type="greeting",
        payload={"message": "Olá de São Paulo!", "from": "TJSP"},
        priority=2,
    )
    
    # TJMG verifica mensagens
    console.print("🔹 TJMG verificando mensagens...")
    messages = await tjmg.check_messages()
    
    if messages:
        table = Table(title="📬 Mensagens Recebidas")
        table.add_column("Sender", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Payload", style="green")
        
        for msg in messages:
            table.add_row(
                msg.sender_id,
                msg.message_type,
                str(msg.payload),
            )
        
        console.print(table)
    
    console.print("[bold green]✓ Cenário 1 concluído![/bold green]\n")


async def scenario_2_data_collaboration() -> None:
    """Cenário 2: Colaboração para compartilhamento de dados."""
    console.print("\n[bold cyan]🤝 CENÁRIO 2: Colaboração de Dados[/bold cyan]\n")
    
    tjsp = TribunalAgent("TJSP")
    tjrs = TribunalAgent("TJRS")
    
    # TJSP precisa de dados do TJRS
    console.print("🔹 TJSP solicitando dados do TJRS...")
    
    # Primeiro, processar mensagens no TJRS para registrar handlers
    await tjrs.process_messages()
    
    # TJSP faz requisição
    response = await tjsp.collaborate_with_tribunal(
        target_tribunal="TJRS",
        query="Consulta processo 123456",
        process_number="123456-78.2024.8.21.0001",
    )
    
    # Processar mensagens no TJRS para responder
    await tjrs.process_messages()
    
    console.print(Panel(
        f"[bold]Requisição enviada![/bold]\n"
        f"TJSP → TJRS\n"
        f"Processo: 123456-78.2024.8.21.0001",
        title="📤 Colaboração Iniciada",
        border_style="cyan",
    ))
    
    console.print("[bold green]✓ Cenário 2 concluído![/bold green]\n")


async def scenario_3_broadcast() -> None:
    """Cenário 3: Broadcast para múltiplos agentes."""
    console.print("\n[bold cyan]📢 CENÁRIO 3: Broadcast Multi-Agent[/bold cyan]\n")
    
    supervisor = TribunalAgent("SUPERVISOR")
    
    # Broadcast de atualização de status
    console.print("🔹 Supervisor enviando broadcast...")
    
    message_ids = await supervisor.broadcast_to_agents(
        agent_ids=["tjsp_agent", "tjmg_agent", "tjrs_agent", "tjrj_agent"],
        message_type="system_update",
        payload={
            "update": "Manutenção programada",
            "scheduled_time": "2024-01-20 02:00:00",
            "duration": "2 horas",
        },
        priority=3,
    )
    
    console.print(Panel(
        f"[bold]Broadcast enviado![/bold]\n"
        f"Destinatários: 4 tribunais\n"
        f"Mensagens enviadas: {len(message_ids)}\n"
        f"Prioridade: ALTA",
        title="✅ Broadcast Completo",
        border_style="green",
    ))
    
    console.print("[bold green]✓ Cenário 3 concluído![/bold green]\n")


async def scenario_4_custom_handlers() -> None:
    """Cenário 4: Handlers customizados."""
    console.print("\n[bold cyan]⚙️  CENÁRIO 4: Handlers Customizados[/bold cyan]\n")
    
    tjsp = TribunalAgent("TJSP")
    
    # Registrar handler customizado
    console.print("🔹 Registrando handler customizado...")
    
    async def custom_alert_handler(message):
        console.print(f"\n[bold yellow]🚨 ALERTA RECEBIDO![/bold yellow]")
        console.print(f"De: {message.sender_id}")
        console.print(f"Payload: {message.payload}\n")
        return {"alert_processed": True, "timestamp": message.timestamp}
    
    tjsp.register_handler("custom_alert", custom_alert_handler)
    
    # Enviar alerta para si mesmo (demonstração)
    await tjsp.send_to_agent(
        target_agent_id="tjsp_agent",
        message_type="custom_alert",
        payload={"alert": "Teste de handler customizado"},
    )
    
    # Processar mensagens
    await tjsp.process_messages()
    
    console.print("[bold green]✓ Cenário 4 concluído![/bold green]\n")


async def scenario_5_message_history() -> None:
    """Cenário 5: Histórico de mensagens."""
    console.print("\n[bold cyan]📊 CENÁRIO 5: Histórico A2A[/bold cyan]\n")
    
    channel = get_a2a_channel()
    
    # Obter histórico global
    history = channel.get_message_history(limit=20)
    
    if history:
        table = Table(title="📜 Histórico de Mensagens A2A")
        table.add_column("Sender", style="cyan")
        table.add_column("Receiver", style="magenta")
        table.add_column("Type", style="yellow")
        table.add_column("Timestamp", style="green")
        
        for msg in history[-10:]:  # Últimas 10
            table.add_row(
                msg.sender_id,
                msg.receiver_id,
                msg.message_type,
                msg.timestamp[-12:-4],  # Simplified timestamp
            )
        
        console.print(table)
    else:
        console.print("[yellow]Nenhuma mensagem no histórico ainda.[/yellow]")
    
    console.print("[bold green]✓ Cenário 5 concluído![/bold green]\n")


async def main() -> None:
    """Executa todos os cenários de demonstração."""
    console.print("\n" + "="*60)
    console.print("[bold cyan]🤖 DEMO: AGENT-TO-AGENT COLLABORATION[/bold cyan]")
    console.print("="*60)
    
    await scenario_1_basic_communication()
    await scenario_2_data_collaboration()
    await scenario_3_broadcast()
    await scenario_4_custom_handlers()
    await scenario_5_message_history()
    
    # Health check
    console.print("\n[bold cyan]🏥 Status do Canal A2A:[/bold cyan]")
    channel = get_a2a_channel()
    health = await channel.health_check()
    
    console.print(Panel(
        f"[bold]Backend:[/bold] {health['backend']}\n"
        f"[bold]Status:[/bold] {health['status']}\n"
        f"[bold]Histórico:[/bold] {health.get('message_history_size', 0)} mensagens",
        title="✅ A2A Health",
        border_style="green",
    ))
    
    console.print("\n" + "="*60)
    console.print("[bold green]🎉 Demo A2A concluída com sucesso![/bold green]")
    console.print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
