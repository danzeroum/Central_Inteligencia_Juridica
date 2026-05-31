"""Safety protocol for agent interactions."""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.safety.pii import redact_pii

logger = logging.getLogger(__name__)


class SafetyProtocol:
    """Protocol for enforcing safety constraints on agent outputs.

    BUGFIX (CRÍTICO-14): ``validate_output`` era um no-op (retornava a saída
    inalterada, sem qualquer garantia de segurança). Agora aplica controles
    reais e recursivos sobre a saída dos agentes:

    * **Redação de PII** em todos os campos de texto (reutiliza o detector LGPD).
    * **Limite de tamanho** por campo, evitando saídas descontroladas.
    """

    MAX_FIELD_LENGTH: int = 10_000

    def validate_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(output, dict):
            return output
        return {key: self._sanitize_value(value) for key, value in output.items()}

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, str):
            redacted = redact_pii(value)
            if len(redacted) > self.MAX_FIELD_LENGTH:
                logger.warning(
                    "SafetyProtocol truncou um campo de %d para %d caracteres",
                    len(redacted),
                    self.MAX_FIELD_LENGTH,
                )
                redacted = redacted[: self.MAX_FIELD_LENGTH]
            return redacted
        if isinstance(value, dict):
            return {k: self._sanitize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        return value
