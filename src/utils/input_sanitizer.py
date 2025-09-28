"""Basic Input Sanitizer for security purposes."""

from __future__ import annotations

import html
import re
from typing import Dict


class InputSanitizer:
    """Provide minimal protection against malicious input patterns."""

    def __init__(self) -> None:
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
            r"(\b)(select|insert|update|delete|drop|create)(\b)",
            r"(\\x[0-9a-fA-F]{2})+",
        ]
        self.allowed_chars = (
            r"a-zA-Z0-9áéíóúâêîôûãõàèìòùçÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇ\s\.,\-_:\\;\?\!@#\$%&\*\(\)\[\]\{\}&;"
        )

    def sanitize_text(self, text: str) -> str:
        """Sanitize a text input removing suspicious patterns and limiting size."""

        if not text or not isinstance(text, str):
            return ""

        sanitized = text
        for pattern in self.suspicious_patterns:
            sanitized = re.sub(pattern, "[REMOVED]", sanitized, flags=re.IGNORECASE | re.DOTALL)

        sanitized = html.escape(sanitized)
        sanitized = re.sub(f"[^{self.allowed_chars}]", "", sanitized)
        sanitized = sanitized[:1000]
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


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    sanitizer = InputSanitizer()
    for sample in [
        "Normal text without issues",
        "<script>alert('xss')</script>Malicious text",
        "SELECT * FROM users; DROP TABLE users",
        "Texto com acentuação: áéíóú",
        "Path traversal: ../../../etc/passwd",
    ]:
        result = sanitizer.validate_and_sanitize(sample)
        print(sample)
        print(result)
