"""Protocolo estrutural AgentInterface — contrato mínimo de todo agente da plataforma.

Usando ``typing.Protocol`` (PEP 544), agentes existentes satisfazem o contrato
sem herança explícita (duck typing verificável por mypy/pyright em análise estática).
``@runtime_checkable`` permite ``isinstance(obj, AgentInterface)`` em tempo de execução.

Nota Python 3.11: ``isinstance`` com ``@runtime_checkable`` verifica apenas membros
definidos no ``__dict__`` das classes (métodos e atributos de classe), não atributos
de instância definidos em ``__init__``. Os atributos ``agent_id``, ``agent_type``
e ``tools`` são esperados por convenção e verificados por análise estática.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class AgentInterface(Protocol):
    """Contrato mínimo que qualquer agente da plataforma deve satisfazer.

    Qualquer objeto que implemente ``execute()`` com a assinatura correta
    satisfaz este protocolo — sem herança necessária.

    Atributos esperados por convenção (não verificados por ``isinstance``):
        agent_id (str): Identificador único da instância.
        agent_type (str): Tipo/categoria do agente.
        tools (list[str]): Ferramentas disponíveis ao agente.
    """

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Executa a responsabilidade principal do agente."""
        ...
