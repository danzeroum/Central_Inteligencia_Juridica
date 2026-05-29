"""Basic Input Sanitizer for security purposes.

Phase 1 Fix: Keep HEAD version (full security) but fix the ordering bug
(strip chars BEFORE html.escape to prevent &amp; from being stripped).
"""

from __future__ import annotations

import html
import re
from typing import Dict


class InputSanitizer:
    """Provide protection against malicious input patterns.

    Sanitisation pipeline (order matters):
        1. Length truncation (prevent resource exhaustion)
        2. Strip disallowed characters
        3. Remove suspicious regex patterns
        4. HTML-escape remaining content
        5. Collapse whitespace
    """

    def __init__(self, max_length: int = 1000) -> None:
        self.max_length = max_length
        self.suspicious_patterns = [
            r"<script.*?>.*?</script>",
            r"javascript:",
            r"on\w+=",
            r"union.*select",
            r"drop\s+table",
            r"insert\s+into",
            r"delete\s+from",
            r"<\?php",
            r"\.\./",
            r"\.\.\\",
            r"(\\x[0-9a-fA-F]{2})+",
        ]
        self.allowed_chars = (
            r"a-zA-Z0-9"
            r"áéíóúâêîôûãõàèìòùç"
            r"ÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇ"
            r"\s\.,\-_:;?!@#\$%&\*\(\)\[\]\{\}\&;"
        )

    def sanitize_text(self, text: str) -> str:
        """Sanitize a text input removing suspicious patterns and limiting size."""

        if not text or not isinstance(text, str):
            return ""

        # 1. Truncate first to prevent DoS on regex
        sanitized = text[: self.max_length]

        # 2. Remove suspicious patterns FIRST (before char stripping)
        for pattern in self.suspicious_patterns:
            sanitized = re.sub(
                pattern, "[REMOVED]", sanitized, flags=re.IGNORECASE | re.DOTALL
            )

        # 3. Strip disallowed characters
        sanitized = re.sub(f"[^{self.allowed_chars}]", "", sanitized)

        # 4. HTML-escape remaining content
        sanitized = html.escape(sanitized)

        # 5. Collapse whitespace and trim
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized

    def is_safe_input(self, text: str) -> bool:
        """Check if input contains potentially dangerous patterns."""

        if not text or not isinstance(text, str):
            return True

        lowered = text.lower()
        for pattern in self.suspicious_patterns:
            if re.search(pattern, lowered, flags=re.IGNORECASE | re.DOTALL):
                return False

        if re.search(f"[^{self.allowed_chars}]", text):
            return False
        return True

    def validate_and_sanitize(self, text: str) -> Dict[str, str | bool]:
        """Validate input and return sanitized version with validation result."""

        sanitized = self.sanitize_text(text)
        is_safe = self.is_safe_input(text)
        return {
            "original": text,
            "sanitized": sanitized,
            "is_safe": is_safe,
            "was_modified": text != sanitized if text else False,
        }


__all__ = ["InputSanitizer"]
