"""Unit tests for InputSanitizer."""

from __future__ import annotations

import pytest

from src.utils.input_sanitizer import InputSanitizer


class TestInputSanitizer:
    def setup_method(self) -> None:
        self.sanitizer = InputSanitizer()

    def test_sanitize_valid_text(self) -> None:
        input_text = "Consulta processo TJSP 2024"
        result = self.sanitizer.sanitize_text(input_text)
        assert result == input_text
        assert self.sanitizer.is_safe_input(input_text) is True

    def test_sanitize_html_tags(self) -> None:
        malicious = "<script>alert('xss')</script>Consulta processo"
        result = self.sanitizer.sanitize_text(malicious)
        assert "<script>" not in result
        assert "alert" not in result
        assert "Consulta processo" in result

    def test_sanitize_sql_injection(self) -> None:
        malicious = "'; UNION SELECT passwords FROM users; --"
        result = self.sanitizer.sanitize_text(malicious)
        assert "UNION SELECT" not in result.upper()
        assert self.sanitizer.is_safe_input(malicious) is False

    def test_sanitize_length_limit(self) -> None:
        long_text = "A" * 2000
        result = self.sanitizer.sanitize_text(long_text)
        assert len(result) <= 1000

    def test_safe_input_validation(self) -> None:
        safe_text = "Status do tribunal TJMG"
        dangerous_text = "<script>malicious()</script>"
        assert self.sanitizer.is_safe_input(safe_text) is True
        assert self.sanitizer.is_safe_input(dangerous_text) is False


if __name__ == "__main__":
    pytest.main([__file__])
