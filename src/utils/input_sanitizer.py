from __future__ import annotations

import re
from typing import Any


class InputSanitizer:
    """Utility helper to normalize user input before processing."""

    _whitespace_re = re.compile(r"\s+")

    def sanitize_text(self, value: Any) -> str:
        """Return a normalized string representation of *value*.

        The sanitizer lowercases repeated whitespace and strips leading/trailing
        spaces while preserving accentuated characters.
        """

        if value is None:
            return ""
        text = str(value)
        text = text.strip()
        text = self._whitespace_re.sub(" ", text)
        return text
