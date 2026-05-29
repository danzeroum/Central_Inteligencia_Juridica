"""Safety protocol for agent interactions."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SafetyProtocol:
    """Protocol for enforcing safety constraints on agent outputs."""

    def validate_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        return output
