"""JWT-based authentication helpers for the public API.

SECURITY: JWT_SECRET environment variable is REQUIRED (min 32 chars).
The application will raise RuntimeError if JWT_SECRET is not set.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

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

    # Load secret from environment (no fallback default)
    _raw_secret: str = os.environ.get("JWT_SECRET", "")
    if len(_raw_secret) < 32 and os.environ.get("ENVIRONMENT", "") != "test":
        raise RuntimeError(
            "JWT_SECRET environment variable must be set (min 32 characters). "
            'Generate: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    SECRET_KEY: str = _raw_secret

    @classmethod
    def configure(
        cls,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        required: Optional[bool] = None,
    ) -> None:
        """Override class-level settings. Primarily used for testing."""
        if secret_key is not None:
            cls.SECRET_KEY = secret_key
        if algorithm is not None:
            cls.ALGORITHM = algorithm
        if required is not None:
            cls.REQUIRED = required

    @classmethod
    def create_token(cls, user_id: str, expires_in_hours: int = 24) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "exp": now + timedelta(hours=expires_in_hours),
            "iat": now,
        }
        return jwt.encode(payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    async def verify_token(
        cls, credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> str:
        if credentials is None:
            if cls.REQUIRED:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication credentials were not provided",
                )
            return "anonymous"

        token = credentials.credentials
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return str(payload["sub"])
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


__all__ = ["AuthManager", "security"]
