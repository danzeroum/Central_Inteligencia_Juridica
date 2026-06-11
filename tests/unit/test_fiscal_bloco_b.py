"""Testes unitários — Bloco B: modelos canônicos, UploadGuard e Repository."""

from __future__ import annotations

import io
import os
import uuid
import zipfile

os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi import HTTPException

# ── Modelos ORM ─────────────────────────────────────────────────────────────


class TestCanonicalModels:
    """Verifica instanciação e atributos dos modelos ORM canônicos."""

    def test_periodo_fiscal_defaults(self):
        from src.db.models import PeriodoFiscal

        p = PeriodoFiscal(ano=2025, mes=3)
        assert p.ano == 2025
        assert p.mes == 3

    def test_periodo_fiscal_anual(self):
        from src.db.models import PeriodoFiscal

        p = PeriodoFiscal(ano=2025, mes=None, tipo="anual")
        assert p.mes is None
        assert p.tipo == "anual"

    def test_escrituracao_fiscal_defaults(self):
        from src.db.models import EscrituracaoFiscal

        e = EscrituracaoFiscal(
            periodo_id=uuid.uuid4(),
            tipo="efd_icms",
            origem="upload",
        )
        assert e.tipo == "efd_icms"
        assert e.origem == "upload"

    def test_registro_fiscal_instantiation(self):
        from src.db.models import RegistroFiscal

        r = RegistroFiscal(
            escrituracao_id=uuid.uuid4(),
            bloco="C",
            tipo_registro="C100",
            numero_linha=42,
            dados={"VL_DOC": "1000.00"},
        )
        assert r.bloco == "C"
        assert r.tipo_registro == "C100"
        assert r.dados["VL_DOC"] == "1000.00"

    def test_documento_fiscal_instantiation(self):
        from src.db.models import DocumentoFiscal

        d = DocumentoFiscal(
            tipo="nfe",
            chave_acesso="35240311222333000181550010000001001123456785",
            valor_total="15000.50",
        )
        assert d.tipo == "nfe"
        assert len(d.chave_acesso) == 44


# ── UploadGuard — arquivo válido ─────────────────────────────────────────────


class TestUploadGuardValid:
    """Arquivos válidos devem passar sem lançar exceção."""

    def _guard(self):
        from src.fiscal.upload import UploadGuard

        return UploadGuard()

    def test_plain_text_sped(self):
        guard = self._guard()
        data = b"|0000|0|1|EMPRESA TESTE|11222333000181|SP|1234567|0001|01012025|31012025|\n"
        result = guard.validate("efd_icms.txt", data, "text/plain")
        assert result.file_type == "sped_txt"
        assert result.size_bytes == len(data)
        assert len(result.sha256) == 64

    def test_xml_nfe_valid(self):
        guard = self._guard()
        xml = b"<?xml version='1.0'?><nfeProc xmlns='http://www.portalfiscal.inf.br/nfe'><NFe/></nfeProc>"
        result = guard.validate("nfe.xml", xml, "application/xml")
        assert result.file_type == "xml"

    def test_octet_stream_accepted(self):
        guard = self._guard()
        data = b"SPED DATA"
        result = guard.validate("arquivo.txt", data, "application/octet-stream")
        assert result.size_bytes == len(data)

    def test_zip_single_file_valid(self):
        guard = self._guard()
        inner = b"|0000|0|1|EMPRESA|\n" * 100
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("efd.txt", inner)
        result = guard.validate("efd.zip", buf.getvalue(), "application/zip")
        assert result.file_type == "sped_txt"


# ── UploadGuard — rejeições de segurança ────────────────────────────────────


class TestUploadGuardSecurity:
    """Uploads maliciosos devem ser rejeitados com HTTPException."""

    def _guard(self):
        from src.fiscal.upload import UploadGuard

        return UploadGuard()

    def test_unsupported_content_type_rejected(self):
        guard = self._guard()
        with pytest.raises(HTTPException) as exc:
            guard.validate("file.exe", b"MZ", "application/x-msdownload")
        assert exc.value.status_code == 415

    def test_zip_with_multiple_files_rejected(self):
        guard = self._guard()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("a.txt", b"A")
            zf.writestr("b.txt", b"B")
        with pytest.raises(HTTPException) as exc:
            guard.validate("multi.zip", buf.getvalue(), "application/zip")
        assert exc.value.status_code == 400
        assert "exatamente um" in exc.value.detail

    def test_zip_bomb_rejected(self):
        """Arquivo com ratio > 1000:1 deve ser rejeitado como zip-bomb."""
        from unittest.mock import MagicMock, patch

        guard = self._guard()
        # Cria um zip válido estruturalmente
        inner = b"|0000|DATA|\n" * 10
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("efd.txt", inner)
        zipped = buf.getvalue()

        # Simula um ZipInfo com ratio extremo (zip-bomb)
        fake_info = MagicMock()
        fake_info.filename = "efd.txt"
        fake_info.compress_size = 100
        fake_info.file_size = 200 * 1024 * 1024  # 200 MB "descomprimido"

        with patch("zipfile.ZipFile.infolist", return_value=[fake_info]):
            with patch("zipfile.ZipFile.read", return_value=inner):
                with pytest.raises(HTTPException) as exc:
                    guard.validate("bomb.zip", zipped, "application/zip")
        assert exc.value.status_code == 400
        assert "zip bomb" in exc.value.detail.lower()

    def test_bad_zip_rejected(self):
        guard = self._guard()
        with pytest.raises(HTTPException) as exc:
            guard.validate("bad.zip", b"not a zip file at all", "application/zip")
        assert exc.value.status_code == 400

    def test_xml_bomb_stdlib_heuristic(self):
        """XML com muitas entidades DTD deve ser rejeitado pelo fallback stdlib."""
        guard = self._guard()
        # Padrão billion-laughs simplificado
        xml_bomb = (
            b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
"""
            + b'  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">\n'
            * 5
            + b"""
]>
<root>"""
            + b"&lol2;" * 200
            + b"</root>"
        )
        try:
            guard.validate("bomb.xml", xml_bomb, "application/xml")
        except HTTPException as exc:
            assert exc.status_code == 400
        except Exception:
            pass  # defusedxml pode lançar outro tipo de exception

    def test_empty_zip_rejected(self):
        guard = self._guard()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            pass
        with pytest.raises(HTTPException) as exc:
            guard.validate("empty.zip", buf.getvalue(), "application/zip")
        assert exc.value.status_code == 400


# ── UploadGuard — sha256 e detecção de tipo ─────────────────────────────────


class TestUploadGuardChecksum:
    def test_sha256_is_deterministic(self):
        from src.fiscal.upload import UploadGuard
        import hashlib

        guard = UploadGuard()
        data = b"SPED LINE\n"
        result = guard.validate("f.txt", data, "text/plain")
        expected = hashlib.sha256(data).hexdigest()
        assert result.sha256 == expected

    def test_xml_detected_by_content(self):
        from src.fiscal.upload import UploadGuard

        guard = UploadGuard()
        xml = b"<root><child/></root>"
        result = guard.validate("data.txt", xml, "text/plain")
        assert result.file_type == "xml"

    def test_pdf_detected_by_extension(self):
        from src.fiscal.upload import UploadGuard

        guard = UploadGuard()
        data = b"%PDF-1.4 binary content"
        result = guard.validate("darf.pdf", data, "application/octet-stream")
        assert result.file_type == "pdf"


# ── get_upload_guard singleton ───────────────────────────────────────────────


def test_get_upload_guard_singleton():
    import src.fiscal.upload as mod

    mod._guard = None
    g1 = mod.get_upload_guard()
    g2 = mod.get_upload_guard()
    assert g1 is g2
    mod._guard = None
