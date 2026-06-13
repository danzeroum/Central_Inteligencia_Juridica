"""FrontendSlot — metadados de navegação que cada módulo expõe para a SPA."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class FrontendSlot:
    """Configuração de um item de menu/slot de navegação para a SPA."""

    label: str
    icon: str
    route: str
    order: int = 0
    enabled: bool = True
    screen_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
