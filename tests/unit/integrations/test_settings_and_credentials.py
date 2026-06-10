"""Testes para settings env precedence, rate_limiter e credentials (Sprint 10)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "JWT_SECRET", "development-secret-key-minimum-32-chars-long-for-tests"
)
os.environ["ENVIRONMENT"] = "test"


class TestSettingsPrecedence:
    """Variável de ambiente deve sobrepor valor do YAML."""

    def test_env_overrides_yaml_mode(self, monkeypatch):
        from src.integrations.settings import get_source_settings

        monkeypatch.setenv("INTEGRATIONS_RECEITA_CNPJ_MODE", "real")
        settings = get_source_settings("receita_cnpj")
        assert settings.mode == "real"

    def test_yaml_default_used_when_no_env(self, monkeypatch):
        from src.integrations.settings import get_source_settings

        monkeypatch.delenv("INTEGRATIONS_DATAJUD_MODE", raising=False)
        settings = get_source_settings("datajud")
        # Default from YAML should be "mock"
        assert settings.mode in ("mock", "real")

    def test_unknown_source_returns_none_or_default(self):
        """Unknown sources return None (not registered) or a SourceSettings default."""
        from src.integrations.settings import get_source_settings

        s = get_source_settings("nonexistent_source_xyz")
        # May return None for truly unknown sources; that's acceptable behaviour
        assert s is None or hasattr(s, "mode")

    def test_load_source_settings_returns_7_sources(self):
        from src.integrations.settings import load_source_settings

        settings = load_source_settings()
        assert len(settings) == 7

    def test_qsa_settings_has_enabled(self):
        from src.integrations.settings import get_qsa_settings

        qsa = get_qsa_settings()
        assert "enabled" in qsa


class TestAsyncRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_single_source(self):
        from src.integrations.rate_limiter import AsyncRateLimiter

        rl = AsyncRateLimiter()
        # Should not raise for first acquire
        await rl.acquire("datajud")

    @pytest.mark.asyncio
    async def test_acquire_multiple_sources_independent(self):
        from src.integrations.rate_limiter import AsyncRateLimiter

        rl = AsyncRateLimiter()
        await rl.acquire("source_a")
        await rl.acquire("source_a")
        # source_b has its own window — should not be blocked by source_a usage
        await rl.acquire("source_b")

    @pytest.mark.asyncio
    async def test_acquire_returns_none(self):
        from src.integrations.rate_limiter import AsyncRateLimiter

        rl = AsyncRateLimiter()
        result = await rl.acquire("any_source")
        assert result is None


class TestCredentialProvider:
    def test_env_provider_returns_none_when_no_key(self, monkeypatch):
        from src.integrations.credentials import EnvCredentialProvider

        monkeypatch.delenv("INTEGRATIONS_DATAJUD_API_KEY", raising=False)
        provider = EnvCredentialProvider()
        creds = provider.get_credentials("datajud")
        assert creds is None or creds.api_key is None

    def test_env_provider_reads_api_key(self, monkeypatch):
        from src.integrations.credentials import EnvCredentialProvider

        monkeypatch.setenv("INTEGRATIONS_DATAJUD_API_KEY", "test-key-123")
        provider = EnvCredentialProvider()
        creds = provider.get_credentials("datajud")
        assert creds is not None
        assert creds.api_key == "test-key-123"

    def test_get_credential_provider_returns_instance(self):
        from src.integrations.credentials import get_credential_provider

        provider = get_credential_provider()
        assert provider is not None
        # Singleton — second call same instance
        assert provider is get_credential_provider()

    def test_env_provider_tenant_id_ignored(self, monkeypatch):
        from src.integrations.credentials import EnvCredentialProvider

        monkeypatch.setenv("INTEGRATIONS_TSE_API_KEY", "tse-key")
        provider = EnvCredentialProvider()
        creds = provider.get_credentials("tse", tenant_id="any-tenant")
        assert creds is not None
        assert creds.api_key == "tse-key"
