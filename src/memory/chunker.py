"""Chunking estratégico de documentos jurídicos."""

from __future__ import annotations

import re
from typing import List


class LegalDocumentChunker:
    """Divide documentos jurídicos em chunks semânticos por tipo."""

    _ARTICLE_PATTERN = re.compile(r"(?=\bArt(?:igo)?\.?\s+\d+[\º°]?)", re.IGNORECASE)
    _SECTION_PATTERN = re.compile(
        r"(?=\b(?:TÍTULO|CAPÍTULO|SEÇÃO|SUBSEÇÃO)\b)", re.IGNORECASE
    )

    def __init__(self, max_chunk_size: int = 1024, overlap: int = 64) -> None:
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_by_article(self, text: str) -> List[dict]:
        """Divide leis e decretos por artigo (Art. X)."""
        parts = self._ARTICLE_PATTERN.split(text)
        chunks = []
        for idx, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            article_match = re.match(
                r"Art(?:igo)?\.?\s+(\d+[\º°]?)", part, re.IGNORECASE
            )
            article_num = article_match.group(1) if article_match else str(idx)
            for sub in self._split_large(part):
                chunks.append(
                    {
                        "text": sub,
                        "metadata": {"chunk_type": "article", "article": article_num},
                    }
                )
        return chunks or [{"text": text, "metadata": {"chunk_type": "article"}}]

    def chunk_by_section(self, text: str) -> List[dict]:
        """Divide códigos por TÍTULO/CAPÍTULO/SEÇÃO."""
        parts = self._SECTION_PATTERN.split(text)
        chunks = []
        for idx, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            header_match = re.match(
                r"(TÍTULO|CAPÍTULO|SEÇÃO|SUBSEÇÃO)\s+([IVXLCDM\d]+\.?\s*.{0,80})",
                part,
                re.IGNORECASE,
            )
            section_label = (
                header_match.group(0)[:80] if header_match else f"section_{idx}"
            )
            for sub in self._split_large(part):
                chunks.append(
                    {
                        "text": sub,
                        "metadata": {
                            "chunk_type": "section",
                            "section": section_label.strip(),
                        },
                    }
                )
        return chunks or [{"text": text, "metadata": {"chunk_type": "section"}}]

    def chunk_by_semantic(self, text: str) -> List[dict]:
        """Divide acordãos/pareceres por parágrafos com overlap."""
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        chunks: List[dict] = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 1 <= self.max_chunk_size:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(
                        {"text": current, "metadata": {"chunk_type": "semantic"}}
                    )
                # overlap: últimas `overlap` chars do chunk anterior
                tail = current[-self.overlap :] if current else ""
                current = (tail + "\n\n" + para).strip() if tail else para
        if current:
            chunks.append({"text": current, "metadata": {"chunk_type": "semantic"}})
        return chunks or [{"text": text, "metadata": {"chunk_type": "semantic"}}]

    def _split_large(self, text: str) -> List[str]:
        """Divide chunks maiores que max_chunk_size por parágrafos."""
        if len(text) <= self.max_chunk_size:
            return [text]
        parts = []
        for para in re.split(r"\n{2,}", text):
            if len(para) <= self.max_chunk_size:
                parts.append(para)
            else:
                for i in range(0, len(para), self.max_chunk_size):
                    parts.append(para[i : i + self.max_chunk_size])
        return [p for p in parts if p.strip()]


__all__ = ["LegalDocumentChunker"]
