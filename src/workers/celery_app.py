"""Instância Celery — broker Redis, backend Redis.

No-op quando ``CELERY_BROKER_URL`` não está definido (compatibilidade dev/test).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
_BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", _BROKER_URL)


def _make_celery():
    """Cria a instância Celery se o broker estiver configurado, senão retorna None."""
    if not _BROKER_URL:
        logger.info(
            "CELERY_BROKER_URL não definido — workers desativados (modo síncrono)."
        )
        return None
    try:
        from celery import Celery

        app = Celery(
            "cij",
            broker=_BROKER_URL,
            backend=_BACKEND_URL,
            include=["src.workers.tasks"],
        )
        app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            timezone="America/Sao_Paulo",
            enable_utc=True,
            task_track_started=True,
            result_expires=3600,
        )
        return app
    except ImportError:
        logger.warning("celery não instalado — workers desativados.")
        return None


celery_app = _make_celery()
