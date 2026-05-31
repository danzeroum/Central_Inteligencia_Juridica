"""Matriz de autenticação/autorização dos endpoints sensíveis.

Cobre, de uma só vez, os achados de AuthZ da auditoria (Onda 1):
CRÍTICO-01..04, H02, H03, H04, M02, M11. Um único teste parametrizado varre
todas as rotas que antes operavam sem proteção e valida o contrato de
segurança em três cenários (V&V — verificação *e* validação):

* **Sem token** → 401 (a porta de autenticação existe e fecha).
* **Token com papel insuficiente** → 403 (a autorização RBAC é exigida).
* **Token com papel correto** → nem 401 nem 403 (não há regressão de acesso).

Os testes rodam com a autenticação LIGADA (``enforce_auth``); por padrão a
suíte roda com ``AuthManager.REQUIRED == False`` (dev/testes), quando estas
checagens são relaxadas de propósito.

BDD (aceitação):
  Given um usuário sem a permissão ``agents:manage``
  When ele chama POST /api/v1/training/train
  Then a API responde 403 (Forbidden).
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from src.api.auth import AuthManager  # noqa: E402
from src.api.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture
def enforce_auth():
    """Liga a exigência de JWT (com secret de teste) e restaura ao final."""

    AuthManager.configure(secret_key="x" * 40, required=True)
    yield
    AuthManager.configure(required=False)


def _token(roles):
    return AuthManager.create_token("tester", roles=roles)


# Matriz de endpoints sensíveis. ``perm`` = permissão exigida (None => apenas
# autenticação). ``external`` marca rotas que disparam chamadas de rede no
# caminho feliz — para essas só validamos o caso negativo (401), que ocorre na
# resolução da dependência, antes de o handler rodar.
#
# (id, method, path, perm, json, params, external)
MATRIX = [
    (
        "training_feedback",
        "POST",
        "/api/v1/training/feedback",
        "agents:manage",
        {"agent_type": "TJSP", "task_result": {"ok": True}},
        None,
        False,
    ),
    (
        "training_train",
        "POST",
        "/api/v1/training/train",
        "agents:manage",
        {"agent_type": "TJSP"},
        None,
        False,
    ),
    (
        "training_abtest",
        "POST",
        "/api/v1/training/ab-test",
        "agents:manage",
        {"agent_a_type": "A", "agent_b_type": "B", "test_cases": [{"x": 1}]},
        None,
        False,
    ),
    (
        "training_stats",
        "GET",
        "/api/v1/training/stats",
        "agents:read",
        None,
        None,
        False,
    ),
    (
        "training_sessions",
        "GET",
        "/api/v1/training/active-sessions",
        "agents:read",
        None,
        None,
        False,
    ),
    (
        "training_history",
        "GET",
        "/api/v1/training/history",
        "agents:read",
        None,
        None,
        False,
    ),
    (
        "training_reset",
        "POST",
        "/api/v1/training/reset/TJSP",
        "config:write",
        None,
        None,
        False,
    ),
    (
        "autonomy_update",
        "PUT",
        "/api/v1/autonomy/config",
        "config:write",
        {"consensus_threshold": 0.5},
        None,
        False,
    ),
    ("ledger_list", "GET", "/api/v1/ledger", "ledger:read", None, None, False),
    (
        "ledger_export",
        "GET",
        "/api/v1/ledger/export.csv",
        "ledger:read",
        None,
        None,
        False,
    ),
    ("hitl_pending", "GET", "/api/v1/hitl/pending", "hitl:write", None, None, False),
    ("hitl_stats", "GET", "/api/v1/hitl/stats", "hitl:write", None, None, False),
    ("a2a_messages", "GET", "/api/v1/a2a/messages/agent_a", None, None, None, False),
    ("a2a_history", "GET", "/api/v1/a2a/history/agent_a", None, None, None, False),
    ("agents_caps", "GET", "/api/v1/agents/capabilities", None, None, None, False),
    ("agents_list", "GET", "/api/v1/agents", None, None, None, False),
    ("agent_details", "GET", "/api/v1/agents/supervisor", None, None, None, False),
    (
        "agents_by_cap",
        "GET",
        "/api/v1/agents/by-capability/search",
        None,
        None,
        None,
        False,
    ),
    ("history", "GET", "/api/v1/history", None, None, None, False),
    (
        "consultar",
        "GET",
        "/consultar-projetos-lei/",
        None,
        None,
        {"q": "reforma"},
        True,
    ),
    ("analise", "POST", "/analise-legislativa/", None, {"tema": "reforma"}, None, True),
]

# Papel que concede cada permissão para validar o caminho feliz. ``admin`` cobre
# tudo; usamos ele para os endpoints com permissão específica.
SUFFICIENT_ROLE = ["admin"]
INSUFFICIENT_ROLE = ["readonly"]  # só possui monitoring:read


def _call(method, path, token=None, json=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.request(method, path, headers=headers, json=json, params=params)


@pytest.mark.parametrize("case", MATRIX, ids=[c[0] for c in MATRIX])
def test_requires_authentication(case, enforce_auth):
    """Sem token → 401 em TODA rota sensível (CRÍTICO-01..04, H02/H03, M02/M11)."""

    _id, method, path, _perm, json, params, _external = case
    resp = _call(method, path, token=None, json=json, params=params)
    assert resp.status_code == 401, f"{_id}: esperado 401, veio {resp.status_code}"


@pytest.mark.parametrize(
    "case", [c for c in MATRIX if c[3] is not None], ids=[c[0] for c in MATRIX if c[3]]
)
def test_insufficient_role_is_forbidden(case, enforce_auth):
    """Token sem a permissão exigida → 403 (autorização RBAC efetiva)."""

    _id, method, path, _perm, json, params, _external = case
    token = _token(INSUFFICIENT_ROLE)
    resp = _call(method, path, token=token, json=json, params=params)
    assert resp.status_code == 403, f"{_id}: esperado 403, veio {resp.status_code}"


@pytest.mark.parametrize(
    "case", [c for c in MATRIX if not c[6]], ids=[c[0] for c in MATRIX if not c[6]]
)
def test_correct_role_is_allowed(case, enforce_auth):
    """Papel correto → nem 401 nem 403 (sem regressão de acesso legítimo)."""

    _id, method, path, perm, json, params, _external = case
    role = SUFFICIENT_ROLE if perm is not None else INSUFFICIENT_ROLE
    resp = _call(method, path, token=_token(role), json=json, params=params)
    assert resp.status_code not in (
        401,
        403,
    ), f"{_id}: acesso legítimo bloqueado ({resp.status_code})"


class TestWebSocketAuth:
    """H04: o handshake do WebSocket HITL exige JWT válido com hitl:write."""

    def test_ws_without_token_is_rejected(self, enforce_auth):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/v1/hitl/ws"):
                pass

    def test_ws_with_valid_token_connects(self, enforce_auth):
        token = _token(["operator"])  # operator possui hitl:write
        with client.websocket_connect(f"/api/v1/hitl/ws?token={token}"):
            pass  # conexão aceita; encerramento limpo ao sair do contexto


def test_no_token_when_auth_disabled_is_open():
    """Sanidade: com auth desligada (default da suíte) os endpoints abrem.

    Garante que a Onda 1 não quebrou o modo dev/teste relaxado.
    """

    assert AuthManager.REQUIRED is False
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
