#!/usr/bin/env python3
"""CLI para ingestão de documentos jurídicos na base de conhecimento.

Uso:
    python scripts/ingest_kb.py --area trabalhista --file lei_clt.txt \\
        --id clt_1943 --tipo lei --data-vigencia 1943-05-01
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Garantir que src/ está no path quando executado diretamente
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.memory.knowledge_manager import KnowledgeManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão de documentos jurídicos no RAG")
    parser.add_argument("--area", required=True, help="Área jurídica (ex: trabalhista)")
    parser.add_argument("--file", required=True, help="Caminho do arquivo de texto")
    parser.add_argument("--id", required=True, dest="doc_id", help="ID único do documento")
    parser.add_argument(
        "--tipo",
        default="generico",
        choices=["lei", "decreto", "codigo", "consolidacao", "acordao", "parecer", "generico"],
        help="Tipo do documento (determina estratégia de chunking)",
    )
    parser.add_argument("--tribunal", default=None, help="Tribunal de origem (opcional)")
    parser.add_argument("--data-vigencia", default=None, dest="data_vigencia", help="Data de vigência (YYYY-MM-DD)")
    parser.add_argument("--ementa", default=None, help="Ementa do documento")

    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        logger.error("Arquivo não encontrado: %s", file_path)
        sys.exit(1)

    content = file_path.read_text(encoding="utf-8")
    if not content.strip():
        logger.error("Arquivo vazio: %s", file_path)
        sys.exit(1)

    metadata = {
        "tipo_documento": args.tipo,
        "source_file": str(file_path.name),
    }
    if args.tribunal:
        metadata["tribunal"] = args.tribunal
    if args.data_vigencia:
        metadata["data_vigencia"] = args.data_vigencia
    if args.ementa:
        metadata["ementa"] = args.ementa

    km = KnowledgeManager()
    km.ingest_document(
        area_key=args.area,
        doc_id=args.doc_id,
        content=content,
        metadata=metadata,
    )
    logger.info("Ingestão concluída: área=%s, doc_id=%s", args.area, args.doc_id)


if __name__ == "__main__":
    main()
