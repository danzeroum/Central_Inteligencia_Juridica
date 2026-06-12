"""DATASUS DBC → DBF decompressor.

The .dbc format: the DBF header is stored uncompressed (first <hdr_size> bytes),
followed by PKWARE DCL Implode (Blast) compressed DBF records.

expand_dbc_to_dbf() is the canonical entry point (Trilho A — DT fix).
It tries:
  1. Pure-Python blast (self-contained, no external deps)
  2. subprocess blast binary (faster for large SP files, if installed)

Usage
-----
from src.datasus.decompress import expand_dbc_to_dbf

dbf_path = expand_dbc_to_dbf("/tmp/RDSP2501.dbc", "/tmp/RDSP2501.dbf")
"""

from __future__ import annotations

import logging
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

from src.datasus._blast import decompress as _blast_decompress

logger = logging.getLogger(__name__)

# First 2 bytes of a DATASUS DBC file = uint16-LE size of the uncompressed DBF header.
_HEADER_BYTES = 2


def expand_dbc_to_dbf(
    dbc_path: str | Path,
    dbf_path: str | Path | None = None,
) -> Path:
    """Decompress a DATASUS .dbc file to a .dbf file.

    Args:
        dbc_path: Path to the .dbc source file.
        dbf_path: Destination .dbf path.  Defaults to same name as dbc_path
                  but with .dbf extension.

    Returns:
        Path to the created .dbf file.

    Raises:
        FileNotFoundError: if dbc_path does not exist.
        ValueError: if the file is not a valid DATASUS DBC.
    """
    dbc_path = Path(dbc_path)
    if not dbc_path.exists():
        raise FileNotFoundError(f"DBC não encontrado: {dbc_path}")

    if dbf_path is None:
        dbf_path = dbc_path.with_suffix(".dbf")
    dbf_path = Path(dbf_path)
    dbf_path.parent.mkdir(parents=True, exist_ok=True)

    raw = dbc_path.read_bytes()
    if len(raw) < _HEADER_BYTES + 1:
        raise ValueError(f"Arquivo DBC muito curto: {dbc_path}")

    # The first 2 bytes give the uncompressed DBF header size.
    (hdr_size,) = struct.unpack_from("<H", raw, 0)
    if hdr_size < 32 or hdr_size > len(raw):
        raise ValueError(
            f"Cabeçalho DBC inválido: hdr_size={hdr_size}, file_len={len(raw)}"
        )

    dbf_header = raw[_HEADER_BYTES : _HEADER_BYTES + hdr_size]
    compressed_body = raw[_HEADER_BYTES + hdr_size :]

    # Try subprocess blast binary first (much faster for large files)
    blast_bin = shutil.which("blast")
    if blast_bin:
        try:
            decompressed = _blast_subprocess(blast_bin, compressed_body)
            dbf_path.write_bytes(dbf_header + decompressed)
            logger.debug(
                "expand_dbc_to_dbf: blast binary usado (%s → %s)",
                dbc_path.name,
                dbf_path.name,
            )
            return dbf_path
        except Exception as exc:
            logger.warning(
                "blast binary falhou (%s), tentando Python: %s", blast_bin, exc
            )

    # Fall back to pure-Python blast
    decompressed = _blast_decompress(compressed_body)
    dbf_path.write_bytes(dbf_header + decompressed)
    logger.debug(
        "expand_dbc_to_dbf: blast Python usado (%s → %s)", dbc_path.name, dbf_path.name
    )
    return dbf_path


def _blast_subprocess(blast_bin: str, compressed: bytes) -> bytes:
    """Decompress using the system blast binary via stdin/stdout."""
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        in_path = Path(f.name)
        in_path.write_bytes(compressed)

    out_path = in_path.with_suffix(".out")
    try:
        subprocess.run(
            [blast_bin, str(in_path), str(out_path)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return out_path.read_bytes()
    finally:
        in_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)
