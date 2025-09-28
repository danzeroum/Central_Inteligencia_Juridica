"""JWT-based authentication helpers for the public API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


class AuthManager:
    """Utility class to create and validate JWT tokens."""

    SECRET_KEY = "change-me-in-production"
    ALGORITHM = "HS256"
    REQUIRED = False

    @classmethod
    def configure(
        cls,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        required: Optional[bool] = None,
    ) -> None:
        if secret_key:
            cls.SECRET_KEY = secret_key
        if algorithm:
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
        except jwt.ExpiredSignatureError as exc:  # pragma: no cover - depends on time
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
