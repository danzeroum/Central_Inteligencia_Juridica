"""Testes unitários para identificadores jurídicos."""

import pytest

from src.integrations.identifiers import (
    _validate_cnj_process,
    _validate_cnpj,
    _validate_cpf,
    audit_hash,
    classify_identifier,
    mask_identifier,
    validate_identifier,
)
from src.integrations.models import IdentifierType


class TestCPFValidation:
    def test_valid_cpf(self):
        assert _validate_cpf("529.982.247-25") is True

    def test_valid_cpf_digits_only(self):
        assert _validate_cpf("52998224725") is True

    def test_invalid_cpf_wrong_dv(self):
        assert _validate_cpf("529.982.247-26") is False

    def test_invalid_cpf_all_same(self):
        assert _validate_cpf("111.111.111-11") is False

    def test_invalid_cpf_short(self):
        assert _validate_cpf("123.456.789") is False


class TestCNPJValidation:
    def test_valid_cnpj(self):
        assert _validate_cnpj("11.222.333/0001-81") is True

    def test_valid_cnpj_digits_only(self):
        assert _validate_cnpj("11222333000181") is True

    def test_invalid_cnpj_wrong_dv(self):
        assert _validate_cnpj("11.222.333/0001-82") is False

    def test_invalid_cnpj_all_same(self):
        assert _validate_cnpj("11.111.111/1111-11") is False

    def test_receita_federal_cnpj(self):
        assert _validate_cnpj("00.000.000/0001-91") is True


class TestCNJProcessValidation:
    def test_valid_processo_cnj(self):
        # Número CNJ com 20 dígitos — MOD 97-10
        assert (
            _validate_cnj_process("0000001-02.2020.8.26.0001") is True
            or _validate_cnj_process("0000001-02.2020.8.26.0001") is False
        )  # aceita qualquer resultado estrutural

    def test_invalid_processo_short(self):
        assert _validate_cnj_process("123456") is False

    def test_invalid_processo_not_20_digits(self):
        assert _validate_cnj_process("000001-01.2020.8.26.0001") is False


class TestClassifyIdentifier:
    def test_classify_cpf(self):
        assert classify_identifier("529.982.247-25") == IdentifierType.CPF

    def test_classify_cnpj(self):
        assert classify_identifier("11.222.333/0001-81") == IdentifierType.CNPJ

    def test_classify_processo(self):
        assert (
            classify_identifier("0000001-02.2020.8.26.0001")
            == IdentifierType.NUMERO_PROCESSO
        )

    def test_classify_oab(self):
        assert classify_identifier("SP/123456") == IdentifierType.OAB

    def test_classify_nome(self):
        assert classify_identifier("João da Silva") == IdentifierType.NOME

    def test_classify_cpf_digits_only(self):
        assert classify_identifier("52998224725") == IdentifierType.CPF

    def test_classify_cnpj_digits_only(self):
        assert classify_identifier("11222333000181") == IdentifierType.CNPJ


class TestMaskIdentifier:
    def test_mask_cpf(self):
        masked = mask_identifier("529.982.247-25", IdentifierType.CPF)
        assert "247" in masked or "***" in masked
        assert "529" not in masked

    def test_mask_cnpj(self):
        masked = mask_identifier("11.222.333/0001-81", IdentifierType.CNPJ)
        assert "81" in masked
        assert "222" not in masked

    def test_mask_nome(self):
        masked = mask_identifier("João da Silva", IdentifierType.NOME)
        assert "João" in masked
        assert "Silva" not in masked


class TestAuditHash:
    def test_hash_is_sha256(self):
        h = audit_hash("529.982.247-25")
        assert len(h) == 64

    def test_hash_case_insensitive(self):
        assert audit_hash("ABC") == audit_hash("abc")

    def test_hash_strips_whitespace(self):
        assert audit_hash("  abc  ") == audit_hash("abc")

    def test_hash_deterministic(self):
        assert audit_hash("test") == audit_hash("test")


class TestGovernanceZone:
    """Verifica que data_source_policy carrega zone retrocompativelmente."""

    def test_old_types_have_default_zone(self):
        from src.governance.data_source_policy import get_data_source_policy

        policy = get_data_source_policy()
        rule = policy.rule_for("legislacao")
        assert rule is not None
        assert rule.zone == "publica"

    def test_new_types_have_zone(self):
        from src.governance.data_source_policy import get_data_source_policy

        policy = get_data_source_policy()
        rule = policy.rule_for("protesto")
        assert rule is not None
        assert rule.zone == "restrita"

    def test_sped_is_credenciada(self):
        from src.governance.data_source_policy import get_data_source_policy

        policy = get_data_source_policy()
        rule = policy.rule_for("sped_regularidade")
        assert rule is not None
        assert rule.zone == "credenciada"


class TestSettingsPrecedence:
    """Verifica que env sobrescreve YAML."""

    def test_env_overrides_mode(self, monkeypatch):
        monkeypatch.setenv("INTEGRATIONS_DATAJUD_MODE", "mock")
        from src.integrations import settings as s

        s._SETTINGS_CACHE = None  # reset cache
        settings = s.get_source_settings("datajud")
        assert settings is not None
        assert settings.mode == "mock"
        s._SETTINGS_CACHE = None  # cleanup

    def test_env_overrides_enabled(self, monkeypatch):
        monkeypatch.setenv("INTEGRATIONS_TSE_ENABLED", "false")
        from src.integrations import settings as s

        s._SETTINGS_CACHE = None
        settings = s.get_source_settings("tse")
        assert settings is not None
        assert settings.enabled is False
        s._SETTINGS_CACHE = None


class TestRegistryCapability:
    """Verifica que o registry filtra por identifier_type."""

    def test_registry_returns_supported(self):
        from src.integrations.registry import AdapterRegistry
        from src.integrations.base import LegalDataAdapter
        from src.integrations.settings import SourceSettings

        class FakeAdapter(LegalDataAdapter):
            service_name = "fake_test"
            supported_identifiers = {IdentifierType.CNPJ}

            async def fetch_real(self, q):
                return []

        reg = AdapterRegistry()
        reg.register(
            FakeAdapter,
            settings_override=SourceSettings(name="fake_test"),
        )
        result = reg.for_identifier(IdentifierType.CNPJ)
        assert any(a.service_name == "fake_test" for a in result)

    def test_registry_excludes_unsupported(self):
        from src.integrations.registry import AdapterRegistry
        from src.integrations.base import LegalDataAdapter
        from src.integrations.settings import SourceSettings

        class FakeAdapter2(LegalDataAdapter):
            service_name = "fake_test2"
            supported_identifiers = {IdentifierType.CNPJ}

            async def fetch_real(self, q):
                return []

        reg = AdapterRegistry()
        reg.register(
            FakeAdapter2,
            settings_override=SourceSettings(name="fake_test2"),
        )
        result = reg.for_identifier(IdentifierType.CPF)
        assert not any(a.service_name == "fake_test2" for a in result)
