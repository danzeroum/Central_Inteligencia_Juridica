"""Parser de documentos fiscais em PDF.

Suporta extração de texto de:
- DANFE (Documento Auxiliar da Nota Fiscal Eletrônica)
- DACT (Documento Auxiliar do CT-e)
- Recibos / comprovantes fiscais genéricos

Usa pypdf para extração de texto. PDFs escaneados (sem camada de texto)
retornam texto vazio sem erro — o chamador deve checar pdf_result.texto.

Segurança: limites de tamanho aplicados na camada de upload (UploadGuard).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re

try:
    import pypdf

    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Resultado
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PdfParseResult:
    """Resultado do parse de um PDF fiscal."""

    tipo: str  # "danfe" | "dact" | "recibo" | "generico"
    texto: str = ""
    paginas: int = 0
    campos: Dict[str, Any] = field(default_factory=dict)
    erros: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de extração de padrões do texto
# ─────────────────────────────────────────────────────────────────────────────

_RE_CHAVE_NFE = re.compile(
    r"\b(\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4})\b"
)
_RE_CNPJ = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")
_RE_CPF = re.compile(r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b")
_RE_DATE_BR = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_RE_VALUE = re.compile(r"R\$\s*([\d.,]+)")
_RE_SERIE_NUMERO = re.compile(r"[Ss]érie[:\s]+(\d+).*?[Nn][ºÚo°\.]+\s*(\d+)", re.DOTALL)
_RE_NF_NUMERO = re.compile(r"N[ºÚo°\.]\s*(\d{1,9})")


def _extract_chave(texto: str) -> Optional[str]:
    match = _RE_CHAVE_NFE.search(texto)
    if match:
        return re.sub(r"\s+", "", match.group(1))
    return None


def _extract_cnpjs(texto: str) -> List[str]:
    return list(dict.fromkeys(_RE_CNPJ.findall(texto)))


def _extract_dates(texto: str) -> List[str]:
    return list(dict.fromkeys(_RE_DATE_BR.findall(texto)))


def _extract_values(texto: str) -> List[str]:
    return list(dict.fromkeys(_RE_VALUE.findall(texto)))


def _read_pdf(data: bytes) -> tuple[str, int, List[str]]:
    """Return (full_text, num_pages, erros)."""
    if not _PYPDF_AVAILABLE:
        return "", 0, ["pypdf não instalado"]
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages = len(reader.pages)
        parts: List[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                parts.append("")
        return "\n".join(parts), pages, []
    except Exception as exc:
        return "", 0, [f"Erro ao ler PDF: {exc}"]


# ─────────────────────────────────────────────────────────────────────────────
# DANFE Parser
# ─────────────────────────────────────────────────────────────────────────────


class DanfeParser:
    """Extrai campos do DANFE (Documento Auxiliar da NF-e) em PDF."""

    def parse(self, data: bytes) -> PdfParseResult:
        result = PdfParseResult(tipo="danfe")
        texto, paginas, erros = _read_pdf(data)
        result.texto = texto
        result.paginas = paginas
        result.erros.extend(erros)
        if erros:
            return result

        chave = _extract_chave(texto)
        if chave:
            result.campos["chave_nfe"] = chave

        cnpjs = _extract_cnpjs(texto)
        if cnpjs:
            result.campos["emit_cnpj"] = cnpjs[0]
            if len(cnpjs) > 1:
                result.campos["dest_cnpj"] = cnpjs[1]

        datas = _extract_dates(texto)
        if datas:
            result.campos["dt_emissao"] = datas[0]

        valores = _extract_values(texto)
        if valores:
            result.campos["vl_total"] = valores[-1]

        # Número da NF
        m = _RE_NF_NUMERO.search(texto)
        if m:
            result.campos["num_nf"] = m.group(1).lstrip("0") or m.group(1)

        return result


# ─────────────────────────────────────────────────────────────────────────────
# DACT Parser (CT-e)
# ─────────────────────────────────────────────────────────────────────────────

_RE_CHAVE_CTE = _RE_CHAVE_NFE  # mesmo formato de 44 dígitos


class DactParser:
    """Extrai campos do DACT (Documento Auxiliar do CT-e) em PDF."""

    def parse(self, data: bytes) -> PdfParseResult:
        result = PdfParseResult(tipo="dact")
        texto, paginas, erros = _read_pdf(data)
        result.texto = texto
        result.paginas = paginas
        result.erros.extend(erros)
        if erros:
            return result

        chave = _extract_chave(texto)
        if chave:
            result.campos["chave_cte"] = chave

        cnpjs = _extract_cnpjs(texto)
        if cnpjs:
            result.campos["emit_cnpj"] = cnpjs[0]
            if len(cnpjs) > 1:
                result.campos["rem_cnpj"] = cnpjs[1]
            if len(cnpjs) > 2:
                result.campos["dest_cnpj"] = cnpjs[2]

        datas = _extract_dates(texto)
        if datas:
            result.campos["dt_emissao"] = datas[0]

        valores = _extract_values(texto)
        if valores:
            result.campos["vl_total_prestacao"] = valores[-1]

        return result


# ─────────────────────────────────────────────────────────────────────────────
# Parser genérico
# ─────────────────────────────────────────────────────────────────────────────


class PdfFiscalParser:
    """Parser genérico para qualquer PDF fiscal — extrai texto e padrões básicos."""

    def parse(self, data: bytes) -> PdfParseResult:
        result = PdfParseResult(tipo="generico")
        texto, paginas, erros = _read_pdf(data)
        result.texto = texto
        result.paginas = paginas
        result.erros.extend(erros)
        if erros:
            return result

        chave = _extract_chave(texto)
        if chave:
            result.campos["chave"] = chave

        cnpjs = _extract_cnpjs(texto)
        if cnpjs:
            result.campos["cnpjs"] = cnpjs

        cpfs = _RE_CPF.findall(texto)
        if cpfs:
            result.campos["cpfs"] = list(dict.fromkeys(cpfs))

        datas = _extract_dates(texto)
        if datas:
            result.campos["datas"] = datas

        valores = _extract_values(texto)
        if valores:
            result.campos["valores"] = valores

        return result


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

_PDF_PARSERS: Dict[str, Any] = {
    "danfe": DanfeParser,
    "dact": DactParser,
    "generico": PdfFiscalParser,
}

_SUPPORTED_PDF = set(_PDF_PARSERS)


def get_pdf_parser(tipo: str) -> Any:
    """Return the appropriate PDF parser for the given document type.

    Args:
        tipo: One of ``"danfe"``, ``"dact"``, or ``"generico"``.

    Raises:
        ValueError: If no parser is registered for *tipo*.
    """
    cls = _PDF_PARSERS.get(tipo)
    if cls is None:
        raise ValueError(
            f"Parser PDF não disponível para tipo: {tipo!r}. "
            f"Tipos suportados: {sorted(_SUPPORTED_PDF)}"
        )
    return cls()
