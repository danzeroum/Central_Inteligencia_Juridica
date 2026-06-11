"""SIH-RD processor: LazyFrame → DataFrame agregado por MUNIC_RES × mes_internacao.

Transforma o LazyFrame bruto do FetcherDatasusFTP no grão analítico do indicador
saude.resp.internacoes_j:
  - Filtra DIAG_PRINC iniciando com 'J' (Cap. X CID-10 — doenças respiratórias)
  - Deriva mes_internacao de DT_INTER (AAAAMM, não competência de faturamento)
  - Agrega por (MUNIC_RES 6 dígitos, mes_internacao) → contagem de AIH
  - Marca competências recentes como parciais (defasagem de faturamento)
  - Aplica supressão k-anonimato (k configurável; padrão k=5 para dados de saúde)

CAVEAT: meses recentes ficam INCOMPLETOS por defasagem de faturamento.
        A coluna `parcial` sinaliza competências dentro da janela de defasagem
        (padrão: últimos 2 meses em relação à data de referência).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

_DEFAULT_K = 5
_DEFASAGEM_MESES = 2  # meses recentes marcados como parciais


def process(
    lazy_frame,
    *,
    k: int = _DEFAULT_K,
    ref_date: Optional[date] = None,
) -> "polars.DataFrame":
    """Processa LazyFrame SIH-RD e retorna agregado para o indicador respiratório.

    Args:
        lazy_frame: polars.LazyFrame com colunas mínimas do SIH-RD.
        k: limiar k-anonimato; contagens < k são suprimidas (NaN) e marcadas
           com suprimido=True.
        ref_date: data de referência para marcação de parciais.
                  Padrão: date.today().

    Returns:
        polars.DataFrame com colunas:
          munic_res_6   str   código IBGE 6 dígitos do município de residência
          mes_intern    str   AAAAMM de internação (de DT_INTER, não competência)
          internacoes   int   contagem de AIH (ou NaN se suprimido)
          suprimido     bool  True se contagem < k (k-anonimato)
          parcial       bool  True se mês dentro da janela de defasagem
    """
    try:
        import polars as pl
    except ImportError as e:
        raise ImportError("pip install polars") from e

    from src.saude.kanon import suppress_k
    from src.saude.munic_map import normalize_munic_6

    if ref_date is None:
        ref_date = date.today()

    # Mes de corte para marcação de parcial (ref_date - DEFASAGEM_MESES)
    ref_aamm = _date_to_aamm(ref_date)
    parcial_cutoff = _subtract_months(ref_aamm, _DEFASAGEM_MESES)

    lf = lazy_frame

    # 1. Filtrar respiratórias (Capítulo X CID-10: J00-J99)
    lf = lf.filter(pl.col("DIAG_PRINC").str.starts_with("J"))

    # 2. Derivar mes_internacao de DT_INTER (formato AAAAMMDD ou AAAAMM)
    #    DT_INTER vem como string "AAAAMMDD" ou já como date do dbfread
    lf = lf.with_columns(
        pl.col("DT_INTER").cast(pl.Utf8).str.slice(0, 6).alias("mes_intern")
    )

    # 3. Normalizar MUNIC_RES para 6 dígitos (pode vir com 7 dígitos no IBGE)
    lf = lf.with_columns(
        pl.col("MUNIC_RES").cast(pl.Utf8).str.slice(0, 6).alias("munic_res_6")
    )

    # 4. Agregar
    df = (
        lf.group_by(["munic_res_6", "mes_intern"])
        .agg(pl.len().alias("internacoes"))
        .collect()
    )

    # 5. Supressão k-anonimato
    df = suppress_k(df, col="internacoes", k=k)

    # 6. Marcar parciais
    df = df.with_columns((pl.col("mes_intern") >= parcial_cutoff).alias("parcial"))

    return df.sort(["munic_res_6", "mes_intern"])


# ── Helpers ──────────────────────────────────────────────────────────────────


def _date_to_aamm(d: date) -> str:
    return f"{d.year}{d.month:02d}"


def _subtract_months(aamm: str, n: int) -> str:
    ano, mes = int(aamm[:4]), int(aamm[4:6])
    total = ano * 12 + mes - 1 - n
    return f"{total // 12}{total % 12 + 1:02d}"
