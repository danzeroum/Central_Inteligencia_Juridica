"""Testes da redação de PII no armazenamento da VectorMemory (LGPD).

``_redact_obj`` é puro (sem ChromaDB): garante que o resultado persistido no
snapshot/documento de longo prazo não retém PII de terceiros, preservando a
estrutura e os valores não-string.
"""

from __future__ import annotations

from src.memory.vector_memory import VectorMemory
from src.safety.pii import redact_pii


def test_redact_obj_redacts_nested_pii_preserves_structure() -> None:
    obj = {
        "parte": "Fulano CPF 123.456.789-09",
        "contato": {"email": "a@b.com"},
        "movimentos": ["Intimação 11.222.333/0001-44", "sem pii"],
        "score": 7,
        "ativo": True,
    }
    out = VectorMemory._redact_obj(obj, redact_pii)

    assert "123.456.789-09" not in out["parte"]
    assert "[REDACTED:CPF]" in out["parte"]
    assert out["contato"]["email"] == "[REDACTED:EMAIL]"
    assert "[REDACTED:CNPJ]" in out["movimentos"][0]
    assert out["movimentos"][1] == "sem pii"
    # valores não-string preservados
    assert out["score"] == 7
    assert out["ativo"] is True


def test_redact_obj_non_pii_unchanged() -> None:
    obj = {"r": "ok", "list": [1, 2, "tudo certo"]}
    assert VectorMemory._redact_obj(obj, redact_pii) == obj
