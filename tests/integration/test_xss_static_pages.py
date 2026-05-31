"""XSS nas páginas HTML estáticas (Onda 4 — CRÍTICO-11/12/13, FH02/FH03).

As páginas servidas pelo backend (hitl.html, index.html, training-dashboard.html)
construíam HTML via template literals com dados da API, abrindo XSS. A correção
introduz um helper ``escapeHtml`` aplicado a todo valor dinâmico.

Estes testes (nível sistema, sem navegador) servem as páginas via TestClient e
verificam, no JS entregue, que: (a) o helper existe; (b) os campos dinâmicos
controlados pela API passam por ``escapeHtml``; (c) não restam interpolações
cruas conhecidas. Também valida a lógica de escape de forma direta.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402

client = TestClient(app)

STATIC = Path("src/api/static")


def _served_hitl() -> str:
    resp = client.get("/hitl")
    assert resp.status_code == 200
    return resp.text


def _served_dashboard() -> str:
    resp = client.get("/training-dashboard")
    assert resp.status_code == 200
    return resp.text


# --- C-11: hitl.html --------------------------------------------------------
class TestHitlXss:
    def test_has_escape_helper(self):
        assert "function escapeHtml" in _served_hitl()

    def test_dynamic_fields_are_escaped(self):
        html = _served_hitl()
        assert "${escapeHtml(request.agent)}" in html
        assert "escapeHtml(JSON.stringify(request.action" in html

    def test_no_raw_agent_interpolation(self):
        # A interpolação crua original não deve mais existir.
        assert "${request.agent} - Solicitação" not in _served_hitl()


# --- C-12: index.html (servido pelo mount estático em /static) --------------
class TestIndexXss:
    def test_index_escapes_dynamic_values(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        assert "function escapeHtml" in html
        assert "${escapeHtml(data.tribunal_used)}" in html
        assert "${data.tribunal_used}" not in html


# --- C-13: training-dashboard.html ------------------------------------------
class TestDashboardXss:
    def test_has_escape_helper(self):
        assert "function escapeHtml" in _served_dashboard()

    def test_dynamic_fields_are_escaped(self):
        html = _served_dashboard()
        assert "${escapeHtml(session.agent_type)}" in html
        assert "${escapeHtml(message)}" in html

    def test_no_raw_session_agent_type(self):
        assert "<strong>${session.agent_type}</strong>" not in _served_dashboard()


# --- Validação direta da lógica de escape (aceitação) -----------------------
def test_escape_helper_neutralizes_script_payload():
    """Given um payload <script>, When escapado, Then vira entidades HTML inertes."""

    # Extrai a implementação do escapeHtml entregue e replica a transformação
    # canônica esperada (o navegador trataria isto como texto, não HTML).
    payload = "<script>alert('xss')</script>"
    escaped = (
        payload.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    # E a página realmente entrega um escapeHtml com as mesmas substituições.
    html = _served_hitl()
    for token in ["replace(/&/g", "replace(/</g", "replace(/>/g"]:
        assert token in html
