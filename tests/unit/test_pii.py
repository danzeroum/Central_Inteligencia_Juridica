"""Testes do detector/redator de PII e do guardrail de output (LGPD-005)."""

from __future__ import annotations

from src.safety.guardrails import GuardrailSystem
from src.safety.pii import PIIDetector, detect_pii, has_pii, pii_types, redact_pii


class TestDetection:
    def test_detects_formatted_cpf(self) -> None:
        assert pii_types("CPF 123.456.789-09") == ["CPF"]

    def test_detects_bare_cpf(self) -> None:
        assert "CPF" in pii_types("documento 12345678909")

    def test_detects_cnpj(self) -> None:
        assert pii_types("CNPJ 12.345.678/0001-95") == ["CNPJ"]

    def test_detects_email(self) -> None:
        assert "EMAIL" in pii_types("fale com joao@exemplo.com.br")

    def test_detects_oab(self) -> None:
        assert "OAB" in pii_types("Dr. Silva OAB/SP 123456")

    def test_detects_phone(self) -> None:
        assert "PHONE" in pii_types("telefone (11) 98765-4321")

    def test_detects_cep(self) -> None:
        assert "CEP" in pii_types("Av. Paulista, 01310-100")

    def test_clean_text_has_no_pii(self) -> None:
        assert not has_pii("Consulta sobre jurisprudência do TJSP")
        assert detect_pii("texto limpo") == []


class TestRedaction:
    def test_redacts_and_preserves_surrounding_text(self) -> None:
        out = redact_pii("Autor joao@x.com, réu 12.345.678/0001-95.")
        assert "joao@x.com" not in out
        assert "12.345.678/0001-95" not in out
        assert "[REDACTED:EMAIL]" in out and "[REDACTED:CNPJ]" in out
        assert out.startswith("Autor ") and out.endswith(".")

    def test_cnpj_takes_priority_over_embedded_cpf(self) -> None:
        # O CNPJ contém dígitos que poderiam casar parcialmente como telefone/CPF;
        # a resolução de sobreposição deve preferir um único match CNPJ.
        text = "12.345.678/0001-95"
        matches = PIIDetector().detect(text)
        assert len(matches) == 1 and matches[0].type == "CNPJ"

    def test_idempotent_on_clean_text(self) -> None:
        assert redact_pii("nada aqui") == "nada aqui"


class TestOutputGuardrail:
    def test_blocks_output_with_email(self) -> None:
        ok, violations = GuardrailSystem().validate_output(
            "resposta com email vazado: a@b.com", {}
        )
        assert not ok
        assert any("PII" in v for v in violations)

    def test_blocks_output_with_oab(self) -> None:
        passed, msg = GuardrailSystem().check_no_pii("advogado OAB/RJ 98765", {})
        assert not passed and "OAB" in msg

    def test_allows_clean_output(self) -> None:
        ok, violations = GuardrailSystem().validate_output(
            "Resposta jurídica sem dados pessoais.", {}
        )
        assert ok and violations == []
