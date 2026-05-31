"""Security headers middleware.

Adiciona cabeçalhos de segurança recomendados (OWASP Secure Headers). O HSTS é
condicional: só é emitido quando ``ENABLE_HSTS=true`` (i.e., quando há
terminação TLS à frente — um proxy reverso/ingress na nuvem), evitando quebrar
o desenvolvimento local em HTTP puro.
"""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# CSP padrão compatível com a SPA servida pela mesma origem. Ajustável por env
# para cenários com CDN/origens adicionais na nuvem.
_DEFAULT_CSP = (
    "default-src 'self'; img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; script-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injeta cabeçalhos de segurança em todas as respostas."""

    def __init__(self, app, *, enable_hsts: bool | None = None, csp: str | None = None):
        super().__init__(app)
        self._enable_hsts = (
            enable_hsts if enable_hsts is not None else _env_flag("ENABLE_HSTS", False)
        )
        self._csp = csp or os.getenv("CONTENT_SECURITY_POLICY", _DEFAULT_CSP)

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Content-Security-Policy", self._csp)
        headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        if self._enable_hsts:
            headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


__all__ = ["SecurityHeadersMiddleware"]
