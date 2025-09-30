"""Exemplo prático de uso do MCP para descoberta e invocação de agentes."""

from __future__ import annotations

import json

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

BASE_URL = "http://localhost:8000"


def discover_agents() -> None:
    """Descobre todos os agentes disponíveis via MCP."""
    console.print("\n[bold cyan]🔍 Descobrindo agentes via MCP...[/bold cyan]\n")

    response = httpx.get(f"{BASE_URL}/api/v1/agents/capabilities")
    data = response.json()

    console.print(Panel(
        f"[bold]Protocolo:[/bold] {data['protocol']}\n"
        f"[bold]Serviço:[/bold] {data['service']}\n"
        f"[bold]Total de Agentes:[/bold] {data['total_agents']}",
        title="📡 MCP Discovery",
        border_style="cyan",
    ))

    table = Table(title="🤖 Agentes Disponíveis")
    table.add_column("Agent ID", style="cyan", no_wrap=True)
    table.add_column("Nome", style="magenta")
    table.add_column("Tipo", style="green")
    table.add_column("Especialização", style="yellow")
    table.add_column("Status", style="bold")

    for agent in data["agents"]:
        table.add_row(
            agent["agent_id"],
            agent["name"],
            agent["agent_type"],
            agent["specialization"],
            agent["status"],
        )

    console.print(table)

    console.print("\n[bold]📋 Resumo de Capacidades:[/bold]")
    console.print(f"  • Capacidades únicas: {len(data['capabilities_summary']['capabilities'])}")
    console.print(f"  • Tools disponíveis: {len(data['capabilities_summary']['tools'])}")


def get_agent_details(agent_id: str) -> None:
    """Obtém detalhes completos de um agente específico."""
    console.print(f"\n[bold cyan]📊 Detalhes do agente '{agent_id}':[/bold cyan]\n")

    response = httpx.get(f"{BASE_URL}/api/v1/agents/{agent_id}")
    agent = response.json()

    console.print(Panel(
        f"[bold]Nome:[/bold] {agent['name']}\n"
        f"[bold]Tipo:[/bold] {agent['agent_type']}\n"
        f"[bold]Descrição:[/bold] {agent['description']}\n"
        f"[bold]Especialização:[/bold] {agent['specialization']}\n"
        f"[bold]Endpoint:[/bold] {agent['endpoint']}",
        title=f"🤖 {agent['name']}",
        border_style="magenta",
    ))

    console.print("\n[bold yellow]⚡ Capacidades:[/bold yellow]")
    for cap in agent["capabilities"]:
        console.print(f"  • {cap}")

    console.print("\n[bold green]🔧 Ferramentas:[/bold green]")
    for tool in agent["tools"]:
        console.print(f"  • {tool}")

    if agent.get("metadata"):
        console.print("\n[bold blue]📌 Metadados:[/bold blue]")
        for key, value in agent["metadata"].items():
            console.print(f"  • {key}: {value}")


def search_by_capability(capability: str) -> None:
    """Busca agentes que possuem determinada capacidade."""
    console.print(f"\n[bold cyan]🔍 Buscando agentes com capacidade '{capability}':[/bold cyan]\n")

    response = httpx.get(f"{BASE_URL}/api/v1/agents/by-capability/{capability}")
    data = response.json()

    if data["total_matches"] == 0:
        console.print(f"[yellow]⚠️  Nenhum agente encontrado com a capacidade '{capability}'[/yellow]")
        return

    console.print(f"[bold green]✓ Encontrados {data['total_matches']} agente(s):[/bold green]\n")

    for agent in data["agents"]:
        console.print(f"  • [cyan]{agent['agent_id']}[/cyan] - {agent['name']}")
        console.print(f"    Endpoint: {agent['endpoint']}\n")


def invoke_agent_directly(agent_id: str, task: str) -> None:
    """Invoca um agente diretamente sem passar pelo supervisor."""
    console.print(f"\n[bold cyan]🚀 Invocando '{agent_id}' diretamente:[/bold cyan]\n")
    console.print(f"[bold]Tarefa:[/bold] {task}\n")

    response = httpx.post(
        f"{BASE_URL}/api/v1/agents/{agent_id}/invoke",
        json={"task_description": task},
        timeout=30.0,
    )

    data = response.json()

    if data["status"] == "success":
        console.print(Panel(
            f"[bold green]✓ Invocação bem-sucedida![/bold green]\n\n"
            f"[bold]Agente:[/bold] {data['agent_invoked']}\n"
            f"[bold]Timestamp:[/bold] {data['timestamp']}",
            title="✅ Resultado",
            border_style="green",
        ))

        result_json = Syntax(
            json.dumps(data["result"], ensure_ascii=False, indent=2),
            "json",
            theme="monokai",
            line_numbers=False,
        )
        console.print("\n[bold]Resposta do Agente:[/bold]")
        console.print(result_json)
    else:
        console.print(f"[bold red]✗ Erro na invocação[/bold red]")


def demo_workflow() -> None:
    """Demonstra um workflow completo usando MCP."""
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]🎯 DEMO: Workflow Completo MCP[/bold cyan]")
    console.print("=" * 60)

    discover_agents()
    get_agent_details("supervisor_agent")
    search_by_capability("task_routing")
    invoke_agent_directly("supervisor_agent", "Status do tribunal TJSP")

    console.print("\n" + "=" * 60)
    console.print("[bold green]✅ Demo concluída![/bold green]")
    console.print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        demo_workflow()
    except httpx.ConnectError:
        console.print(
            "\n[bold red]❌ Erro de conexão![/bold red]\n\n"
            "Certifique-se de que a API está rodando:\n"
            "  • docker-compose up -d\n"
            "  • OU uvicorn src.api.main:app --reload\n",
            style="yellow",
        )
    except Exception as exc:  # pragma: no cover - manual usage helper
        console.print(f"\n[bold red]❌ Erro:[/bold red] {exc}\n")
