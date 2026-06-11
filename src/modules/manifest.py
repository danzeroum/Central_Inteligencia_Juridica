"""Definição do manifesto de módulo — contrato declarativo de cada módulo da plataforma."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.modules.slots import FrontendSlot


@dataclass
class ModuleManifest:
    """Metadados declarativos de um módulo da plataforma."""

    module_id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    agent_types: List[str] = field(default_factory=list)
    endpoints: List[str] = field(default_factory=list)
    is_active: bool = True
    slot: Optional["FrontendSlot"] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
