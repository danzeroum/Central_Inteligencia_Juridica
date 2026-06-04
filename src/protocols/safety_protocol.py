"""Safety protocol for agent interactions."""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.governance.data_source_policy import (
    DataSourceViolation,
    get_data_source_policy,
)
from src.safety.pii import redact_pii

logger = logging.getLogger(__name__)


class SafetyProtocol:
    """Protocol for enforcing safety constraints on agent interactions.

    BUGFIX (CRÍTICO-14): ``validate_output`` era um no-op (retornava a saída
    inalterada, sem qualquer garantia de segurança). Agora aplica controles
    reais e recursivos sobre a saída dos agentes:

    * **Redação de PII** em todos os campos de texto (reutiliza o detector LGPD).
    * **Limite de tamanho** por campo, evitando saídas descontroladas.

    DMN-02 (Frente F4): além da saída, o protocolo passa a aplicar a política de
    fonte de dados (regra CJ-001) — o LLM nunca é a fonte de dados normativos.
    """

    MAX_FIELD_LENGTH: int = 10_000

    def validate_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(output, dict):
            return output
        return {key: self._sanitize_value(value) for key, value in output.items()}

    def enforce_data_source(self, data_type: str, source: str) -> None:
        """Aplica a DMN-02: hard block se o LLM for fonte de dado crítico.

        Levanta :class:`DataSourceViolation` (regra CJ-001) quando violado.
        """

        get_data_source_policy().assert_source(data_type, source)

    def is_data_source_allowed(self, data_type: str, source: str) -> bool:
        """Versão não-lançadora de :meth:`enforce_data_source`."""

        try:
            self.enforce_data_source(data_type, source)
            return True
        except DataSourceViolation:
            return False

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
