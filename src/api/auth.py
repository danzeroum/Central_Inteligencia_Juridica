"""JWT-based authentication helpers for the public API.

SECURITY: JWT_SECRET environment variable is REQUIRED (min 32 chars).
The application will raise RuntimeError if JWT_SECRET is not set.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Sequence

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class AuthManager:
    """Utility class to create and validate JWT tokens.

    IMPORTANT: ``SECRET_KEY`` is loaded from the ``JWT_SECRET``
    environment variable. If not set (and not in test env), RuntimeError
    is raised to prevent accidental insecure deployment.
    """

    ALGORITHM: str = "HS256"
    REQUIRED: bool = True  # SECURITY: Changed from False to True

    # SECURITY (BACEN 4.658): timeout de sessão JWT. O padrão de 24h era alto
    # demais; o BACEN recomenda 15-30 min para operações privilegiadas. O default
    # cai para 30 min, configurável via ``JWT_EXPIRY_MINUTES``.
    EXPIRY_MINUTES: int = int(os.environ.get("JWT_EXPIRY_MINUTES", "30"))

    # SECURITY: ``RLock`` (reentrante) serializa leituras/escritas das
    # configurações de classe, evitando race conditions ao reconfigurar o
    # ``SECRET_KEY`` em ambientes multi-thread (ex.: uvicorn workers/threadpool).
    _lock: threading.RLock = threading.RLock()

    # Load secret from environment (no fallback default).
    _raw_secret: str = os.environ.get("JWT_SECRET", "")
    if len(_raw_secret) < 32:
        if os.environ.get("ENVIRONMENT", "") != "test":
            raise RuntimeError(
                "JWT_SECRET environment variable must be set (min 32 characters). "
                'Generate: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        # SECURITY (H01): mesmo em ``ENVIRONMENT=test`` o segredo NUNCA é vazio.
        # Antes, definir ENVIRONMENT=test em produção deixava ``SECRET_KEY=""``,
        # permitindo forjar tokens. Agora geramos um segredo efêmero aleatório —
        # a suíte que precisa de um valor conhecido chama ``configure()``.
        _raw_secret = secrets.token_urlsafe(48)
    SECRET_KEY: str = _raw_secret

    @classmethod
    def configure(
        cls,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        required: Optional[bool] = None,
        expiry_minutes: Optional[int] = None,
    ) -> None:
        """Override class-level settings. Primarily used for testing."""
        with cls._lock:
            if secret_key is not None:
                cls.SECRET_KEY = secret_key
            if algorithm is not None:
                cls.ALGORITHM = algorithm
            if required is not None:
                cls.REQUIRED = required
            if expiry_minutes is not None:
                cls.EXPIRY_MINUTES = expiry_minutes

    @classmethod
    def create_token(
        cls,
        user_id: str,
        expires_in_hours: Optional[int] = None,
        roles: Optional[Sequence[str]] = None,
        expires_in_minutes: Optional[int] = None,
    ) -> str:
        # Precedência: minutos explícitos > horas explícitas > default (env/30min).
        if expires_in_minutes is not None:
            delta = timedelta(minutes=expires_in_minutes)
        elif expires_in_hours is not None:
            delta = timedelta(hours=expires_in_hours)
        else:
            delta = timedelta(minutes=cls.EXPIRY_MINUTES)

        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "sub": user_id,
            "exp": now + delta,
            "iat": now,
        }
        # RBAC: papéis viajam no próprio token (autorização stateless). Tokens
        # sem ``roles`` recebem papéis padrão em src/api/rbac.py.
        if roles is not None:
            payload["roles"] = list(roles)
        with cls._lock:
            secret, algorithm = cls.SECRET_KEY, cls.ALGORITHM
        return jwt.encode(payload, secret, algorithm=algorithm)

    @classmethod
    def verify_token_payload(
        cls, credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> Dict[str, Any]:
        """Valida o JWT e retorna o payload completo (incl. ``roles``).

        Base compartilhada por :meth:`verify_token` (que devolve só o ``sub``) e
        pela camada de RBAC (que precisa dos papéis). Mantém o mesmo contrato de
        erro: 401 quando exigido e ausente/ inválido; ``anonymous`` quando a
        autenticação está desligada e nenhuma credencial é enviada.
        """

        with cls._lock:
            secret, algorithm, required = cls.SECRET_KEY, cls.ALGORITHM, cls.REQUIRED

        if credentials is None:
            if required:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication credentials were not provided",
                )
            return {"sub": "anonymous"}

        token = credentials.credentials
        try:
            return jwt.decode(token, secret, algorithms=[algorithm])
        except jwt.ExpiredSignatureError as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado",
            ) from exc
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            ) from exc

    @classmethod
    async def verify_token(
        cls, credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> str:
        payload = cls.verify_token_payload(credentials)
        return str(payload.get("sub", "anonymous"))


__all__ = ["AuthManager", "security"]
