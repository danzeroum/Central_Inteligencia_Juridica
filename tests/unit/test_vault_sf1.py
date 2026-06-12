"""Testes unitários — S-F.1: Cofre de credenciais + Assinatura digital."""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")

import base64  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# CredentialVault — cifrar / decifrar / rotacionar
# ─────────────────────────────────────────────────────────────────────────────


class TestCredentialVault:
    def setup_method(self):
        from src.integrations import vault as _vault_mod

        _vault_mod._vault = None  # reset singleton
        from src.integrations.vault import CredentialVault

        self.vault = CredentialVault()

    def test_store_e_retrieve(self):
        payload = {"api_key": "chave-secreta", "client_id": "cid"}
        self.vault.store("ecac", "tenant1", payload)
        result = self.vault.retrieve("ecac", "tenant1")
        assert result is not None
        assert result["api_key"] == "chave-secreta"

    def test_retrieve_nao_existente_retorna_none(self):
        result = self.vault.retrieve("nao_existe", "tenant_x")
        assert result is None

    def test_store_diferente_tenant(self):
        self.vault.store("ecac", "t1", {"api_key": "k1"})
        self.vault.store("ecac", "t2", {"api_key": "k2"})
        assert self.vault.retrieve("ecac", "t1")["api_key"] == "k1"
        assert self.vault.retrieve("ecac", "t2")["api_key"] == "k2"

    def test_rotate_atualiza_payload(self):
        self.vault.store("ecac", "tenant1", {"api_key": "antiga"})
        existed = self.vault.rotate("ecac", "tenant1", {"api_key": "nova"})
        assert existed is True
        result = self.vault.retrieve("ecac", "tenant1")
        assert result["api_key"] == "nova"

    def test_rotate_sem_entrada_previa(self):
        existed = self.vault.rotate("sefaz", "novo_tenant", {"token": "abc"})
        assert existed is False
        assert self.vault.retrieve("sefaz", "novo_tenant") == {"token": "abc"}

    def test_delete_existente(self):
        self.vault.store("ecac", "tenant1", {"api_key": "k"})
        deleted = self.vault.delete("ecac", "tenant1")
        assert deleted is True
        assert self.vault.retrieve("ecac", "tenant1") is None

    def test_delete_nao_existente(self):
        deleted = self.vault.delete("x", "y")
        assert deleted is False

    def test_metadata_retorna_sem_payload(self):
        self.vault.store(
            "ecac", "tenant1", {"api_key": "segredo"}, cert_path="/run/cert.p12"
        )
        meta = self.vault.metadata("ecac", "tenant1")
        assert meta is not None
        assert "encrypted_payload" not in meta
        assert meta["has_cert_path"] is True
        assert meta["source"] == "ecac"

    def test_metadata_nao_existente(self):
        assert self.vault.metadata("x", "y") is None

    def test_cert_path_muito_longo_rejeitado(self):
        with pytest.raises(ValueError, match="caminho"):
            self.vault.store("ecac", "t1", {"api_key": "k"}, cert_path="A" * 513)

    def test_payload_cifrado_ilegivel_sem_chave(self):
        self.vault.store("ecac", "t1", {"secret": "valor"})
        entry = self.vault._mem[self.vault._slot_id("ecac", "t1")]
        assert "valor" not in entry.encrypted_payload


# ─────────────────────────────────────────────────────────────────────────────
# VaultCredentialProvider
# ─────────────────────────────────────────────────────────────────────────────


class TestVaultCredentialProvider:
    def setup_method(self):
        from src.integrations import vault as _vault_mod, credentials as _cred_mod

        _vault_mod._vault = None
        _cred_mod._provider = None

    def test_retorna_credencial_do_vault(self):
        from src.integrations.vault import get_vault
        from src.integrations.credentials import VaultCredentialProvider

        get_vault().store("ecac", "default", {"api_key": "abc123"})
        provider = VaultCredentialProvider()
        creds = provider.get_credentials("ecac")
        assert creds is not None
        assert creds.api_key == "abc123"

    def test_fallback_env_quando_nao_no_vault(self, monkeypatch):
        from src.integrations.credentials import VaultCredentialProvider

        monkeypatch.setenv("INTEGRATIONS_SEFAZ_API_KEY", "env-key")
        provider = VaultCredentialProvider()
        creds = provider.get_credentials("sefaz")
        assert creds is not None
        assert creds.api_key == "env-key"

    def test_sem_credencial_retorna_none(self):
        from src.integrations.credentials import VaultCredentialProvider

        provider = VaultCredentialProvider()
        creds = provider.get_credentials("fonte_sem_cred")
        assert creds is None


# ─────────────────────────────────────────────────────────────────────────────
# DigitalSignatureService — stub
# ─────────────────────────────────────────────────────────────────────────────


class TestDigitalSignatureStub:
    def test_sign_stub_retorna_is_stub_true(self):
        from src.integrations.digital_signature import sign_payload

        result = sign_payload(b"payload de teste")
        assert result.is_stub is True
        assert result.algorithm == "RSA-PSS/SHA-256"
        assert result.subject_cn == "STUB-CERT-DEV"
        assert len(result.signature_b64) > 0

    def test_sign_diferente_payload(self):
        from src.integrations.digital_signature import sign_payload

        r1 = sign_payload(b"payload1")
        r2 = sign_payload(b"payload2")
        # Assinaturas diferentes (RSA-PSS com salt aleatório)
        assert r1.signature_b64 != r2.signature_b64

    def test_verify_sem_cert_retorna_false(self):
        from src.integrations.digital_signature import sign_payload, verify_payload

        result = sign_payload(b"teste")
        ok = verify_payload(b"teste", result.signature_b64)
        assert ok is False  # sem CERT_A1_PATH configurado

    def test_sign_payload_vazio(self):
        from src.integrations.digital_signature import sign_payload

        result = sign_payload(b"")
        assert result.is_stub is True


# ─────────────────────────────────────────────────────────────────────────────
# Vault request validation
# ─────────────────────────────────────────────────────────────────────────────


class TestVaultRequestValidation:
    def test_store_rejeita_cert_content_no_payload(self):
        from src.api.routes.vault import StoreRequest

        with pytest.raises(Exception, match="conteúdo de certificado"):
            StoreRequest(
                source="ecac",
                tenant_id="t1",
                payload={
                    "cert": "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----"
                },
            )

    def test_store_rejeita_cert_path_como_conteudo(self):
        from src.api.routes.vault import StoreRequest

        with pytest.raises(Exception):
            StoreRequest(
                source="ecac",
                tenant_id="t1",
                payload={"api_key": "k"},
                cert_path="-----BEGIN CERTIFICATE-----\nabc",
            )

    def test_store_aceita_payload_valido(self):
        from src.api.routes.vault import StoreRequest

        req = StoreRequest(
            source="ecac",
            tenant_id="t1",
            payload={"api_key": "chave", "client_id": "cid"},
            cert_path="/run/secrets/cert.p12",
        )
        assert req.source == "ecac"

    def test_source_normalizado_minusculo(self):
        from src.api.routes.vault import StoreRequest

        req = StoreRequest(source="ECAC", tenant_id="t1", payload={})
        assert req.source == "ecac"


# ─────────────────────────────────────────────────────────────────────────────
# HTTP endpoints
# ─────────────────────────────────────────────────────────────────────────────


def _make_client():
    from src.api.main import app

    return TestClient(app, raise_server_exceptions=False)


class TestVaultEndpoints:
    def setup_method(self):
        # Garante REQUIRED=False independente da ordem de execução dos testes
        from src.api.auth import AuthManager

        AuthManager.configure(required=False)
        self.client = _make_client()
        from src.integrations import vault as _vault_mod

        _vault_mod._vault = None  # reset vault entre testes

    def test_store_201(self):
        resp = self.client.post(
            "/api/v1/vault/store",
            json={"source": "ecac", "tenant_id": "t1", "payload": {"api_key": "k"}},
        )
        assert resp.status_code == 201
        assert "slot_id" in resp.json()

    def test_store_cert_conteudo_422(self):
        resp = self.client.post(
            "/api/v1/vault/store",
            json={
                "source": "ecac",
                "tenant_id": "t1",
                "payload": {"cert": "-----BEGIN CERTIFICATE-----\nxxx"},
            },
        )
        assert resp.status_code == 422

    def test_rotate_201(self):
        self.client.post(
            "/api/v1/vault/store",
            json={"source": "ecac", "tenant_id": "t1", "payload": {"api_key": "old"}},
        )
        resp = self.client.post(
            "/api/v1/vault/rotate",
            json={
                "source": "ecac",
                "tenant_id": "t1",
                "new_payload": {"api_key": "new"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["existed"] is True

    def test_metadata_200(self):
        self.client.post(
            "/api/v1/vault/store",
            json={"source": "ecac", "tenant_id": "t2", "payload": {"api_key": "k"}},
        )
        resp = self.client.get("/api/v1/vault/metadata?source=ecac&tenant_id=t2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "ecac"
        assert "encrypted_payload" not in data

    def test_metadata_404(self):
        resp = self.client.get(
            "/api/v1/vault/metadata?source=nao_existe&tenant_id=t999"
        )
        assert resp.status_code == 404

    def test_delete_200(self):
        self.client.post(
            "/api/v1/vault/store",
            json={"source": "ecac", "tenant_id": "t3", "payload": {"api_key": "k"}},
        )
        resp = self.client.delete("/api/v1/vault/delete?source=ecac&tenant_id=t3")
        assert resp.status_code == 200

    def test_delete_404(self):
        resp = self.client.delete("/api/v1/vault/delete?source=xxx&tenant_id=yyy")
        assert resp.status_code == 404

    def test_sign_200_is_stub(self):
        payload_b64 = base64.b64encode(b"payload de teste fiscal").decode()
        resp = self.client.post(
            "/api/v1/vault/sign",
            json={"payload_b64": payload_b64},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_stub"] is True
        assert data["algorithm"] == "RSA-PSS/SHA-256"
        assert len(data["signature_b64"]) > 0

    def test_sign_base64_invalido_422(self):
        resp = self.client.post(
            "/api/v1/vault/sign",
            json={"payload_b64": "isso não é base64!!!"},
        )
        assert resp.status_code == 422
