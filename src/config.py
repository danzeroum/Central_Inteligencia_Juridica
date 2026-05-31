"""Application configuration via environment variables."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # SECURITY: sem default hardcoded. A fonte de verdade do segredo JWT é
    # ``src/api/auth.py``, que EXIGE ``JWT_SECRET`` (mín. 32 chars, fail-fast)
    # fora de ``ENVIRONMENT=test``. Manter um default aqui seria enganoso.
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = ""
    db_password: str = ""
    db_name: str = "central_inteligencia"

    redis_url: str = "redis://localhost:6379/0"

    chroma_host: str = "localhost"
    chroma_port: int = 8000

    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
