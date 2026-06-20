"""Regressão de segurança do AuthManager (JWT) — lacuna apontada na auditoria.

A auditoria registrou ausência de testes para **token expirado** e **assinatura
inválida** (o ramo de expiração em ``auth.py`` chegava marcado como
``# pragma: no cover``). Estes testes fecham essa lacuna e travam a regressão.

São puros (jwt + fastapi, sem deps pesadas) e restauram o estado de classe do
AuthManager ao fim de cada caso (config global).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.api.auth import AuthManager

_SECRET = "a" * 48  # ≥ 32 chars (exigência do AuthManager)


@pytest.fixture(autouse=True)
def _restore_auth_state():
    """Snapshot/restore das configs de classe (evita poluir outros testes)."""

    snapshot = (
        AuthManager.SECRET_KEY,
        AuthManager.ALGORITHM,
        AuthManager.REQUIRED,
        AuthManager.EXPIRY_MINUTES,
    )
    AuthManager.configure(
        secret_key=_SECRET, algorithm="HS256", required=True, expiry_minutes=30
    )
    yield
    (
        AuthManager.SECRET_KEY,
        AuthManager.ALGORITHM,
        AuthManager.REQUIRED,
        AuthManager.EXPIRY_MINUTES,
    ) = snapshot


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_valid_token_roundtrip() -> None:
    token = AuthManager.create_token("user1", roles=["admin"])
    payload = AuthManager.verify_token_payload(_creds(token))
    assert payload["sub"] == "user1"
    assert payload["roles"] == ["admin"]


def test_expired_token_is_rejected() -> None:
    token = AuthManager.create_token("user1", expires_in_minutes=-1)
    with pytest.raises(HTTPException) as exc:
        AuthManager.verify_token_payload(_creds(token))
    assert exc.value.status_code == 401


def test_invalid_signature_is_rejected() -> None:
    token = AuthManager.create_token("user1")
    AuthManager.configure(secret_key="b" * 48)  # segredo diferente do emissor
    with pytest.raises(HTTPException) as exc:
        AuthManager.verify_token_payload(_creds(token))
    assert exc.value.status_code == 401


def test_garbage_token_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        AuthManager.verify_token_payload(_creds("not.a.valid.jwt"))
    assert exc.value.status_code == 401


def test_missing_credentials_when_required_raises_401() -> None:
    AuthManager.configure(required=True)
    with pytest.raises(HTTPException) as exc:
        AuthManager.verify_token_payload(None)
    assert exc.value.status_code == 401


def test_missing_credentials_when_optional_is_anonymous() -> None:
    AuthManager.configure(required=False)
    payload = AuthManager.verify_token_payload(None)
    assert payload["sub"] == "anonymous"
