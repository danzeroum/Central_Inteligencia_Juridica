"""DATASUS FTP fetcher for SIH-RD (Sistema de Informações Hospitalares).

Baixa arquivos RD<UF><AAMM>.dbc do servidor FTP público do DATASUS,
descomprime para .dbf e retorna um Polars LazyFrame com os campos mínimos
necessários para o indicador saude.resp.internacoes_j.

Caminho FTP confirmado:
  /dissemin/publicos/SIHSUS/200801_/Dados/RD<UF><AAMM>.dbc

Usage
-----
from src.datasus.fetcher import FetcherDatasusFTP

fetcher = FetcherDatasusFTP()
df = fetcher.fetch_competencia("SP", 2025, 1)   # LazyFrame
"""

from __future__ import annotations

import ftplib
import logging
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_FTP_HOST = "ftp.datasus.gov.br"
_FTP_BASE = "/dissemin/publicos/SIHSUS/200801_/Dados"

_UFS = [
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]

# Colunas mínimas do SIH-RD necessárias para o indicador respiratório.
# NASC, CPF_AUT, GESTOR_CPF etc. são omitidos (LGPD — quasi-identificadores).
_COLS_PRODUTO = [
    "MUNIC_RES",
    "MUNIC_MOV",
    "DIAG_PRINC",
    "DT_INTER",
    "ANO_CMPT",
    "MES_CMPT",
]


class FetcherDatasusFTP:
    """Fetcher para SIH-RD via FTP DATASUS.

    Args:
        tmp_dir: diretório temporário para DBC/DBF.  Se None, usa tempfile.mkdtemp().
        timeout: timeout FTP em segundos.
    """

    def __init__(
        self,
        tmp_dir: Optional[str | Path] = None,
        timeout: int = 120,
    ) -> None:
        self._tmp_dir = (
            Path(tmp_dir) if tmp_dir else Path(tempfile.mkdtemp(prefix="datasus_"))
        )
        self._timeout = timeout

    # ── Download ──────────────────────────────────────────────────────────────

    def _remote_path(self, uf: str, ano: int, mes: int) -> str:
        aamm = f"{ano % 100:02d}{mes:02d}"
        return f"{_FTP_BASE}/RD{uf.upper()}{aamm}.dbc"

    def _download_dbc(self, uf: str, ano: int, mes: int) -> Path:
        """Baixa o .dbc para o tmp_dir e retorna o caminho local."""
        remote = self._remote_path(uf, ano, mes)
        local_dbc = self._tmp_dir / Path(remote).name

        if local_dbc.exists():
            logger.debug("cache hit: %s", local_dbc.name)
            return local_dbc

        logger.info("FTP download: %s:%s", _FTP_HOST, remote)
        with ftplib.FTP(_FTP_HOST, timeout=self._timeout) as ftp:
            ftp.login()
            with local_dbc.open("wb") as f:
                ftp.retrbinary(f"RETR {remote}", f.write)
        logger.info("baixado: %s (%d bytes)", local_dbc.name, local_dbc.stat().st_size)
        return local_dbc

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_competencia(self, uf: str, ano: int, mes: int):
        """Baixa, descomprime e retorna LazyFrame com colunas mínimas.

        Returns:
            polars.LazyFrame com colunas de _COLS_PRODUTO.

        Raises:
            ImportError: se polars ou dbfread não estiverem instalados.
            ftplib.error_perm: se o arquivo não existir no FTP.
        """
        try:
            import polars as pl
            from dbfread import DBF
        except ImportError as e:
            raise ImportError(
                f"Dependência ausente ({e}). Instale: pip install polars dbfread"
            ) from e

        from src.datasus.decompress import expand_dbc_to_dbf

        dbc_path = self._download_dbc(uf, ano, mes)
        dbf_path = dbc_path.with_suffix(".dbf")
        expand_dbc_to_dbf(dbc_path, dbf_path)

        records = []
        for rec in DBF(str(dbf_path), encoding="latin-1"):
            row = {col: rec.get(col) for col in _COLS_PRODUTO if col in rec}
            records.append(row)

        df = pl.DataFrame(records, infer_schema_length=1000)
        return df.lazy()

    def fetch_nacional(self, ano: int, mes: int):
        """Baixa todas as 27 UFs e concatena em um único LazyFrame.

        Arquivos não encontrados no FTP são ignorados com warning.
        """
        try:
            import polars as pl
        except ImportError as e:
            raise ImportError("pip install polars") from e

        frames = []
        for uf in _UFS:
            try:
                lf = self.fetch_competencia(uf, ano, mes)
                frames.append(lf)
            except ftplib.error_perm:
                logger.warning(
                    "arquivo não encontrado no FTP: UF=%s AAMM=%d%02d", uf, ano, mes
                )
            except Exception as exc:
                logger.error("erro ao processar UF=%s: %s", uf, exc)

        if not frames:
            raise RuntimeError(f"Nenhum arquivo SIH-RD encontrado para {ano}/{mes:02d}")

        return pl.concat(frames)
