"""Indicador saude.resp.internacoes_j.

Número de AIH com DIAG_PRINC iniciando em 'J' (Capítulo X CID-10 — doenças do
aparelho respiratório), agregado por MUNICÍPIO DE RESIDÊNCIA × MÊS DE INTERNAÇÃO.

Decisões de design (registradas aqui e no contrato SAUDE-01):

- **Município**: MUNIC_RES (residência do paciente), NÃO MUNIC_MOV (local de
  atendimento).  Usar MUNIC_MOV zeraria municípios sem hospital — não é o que
  um sentinela epidemiológico quer medir.

- **CID**: DIAG_PRINC LIKE 'J%'.  Refina:
    J09-J18  Influenza e pneumonia
    J40-J47  DPOC, asma
    J00-J06  IRA alta
    U07.1    COVID-19 → refinamento futuro (ADR SAUDE-ADR-001)

- **Mês**: derivado de DT_INTER (AAAAMM dos 6 primeiros chars), NÃO de
  ANO_CMPT/MES_CMPT que são de faturamento e misturam competências.

- **CAVEAT (exibir na tela)**: meses recentes ficam INCOMPLETOS por defasagem
  de faturamento (~2 meses).  A coluna `parcial=True` sinaliza esses meses.

- **Supressão k-anonimato**: contagens < k=5 → NaN + suprimido=True + badge 🔒.

- **Município 6 dígitos**: chave IBGE sem DV; mapa 6→7 em src/saude/munic_map.py.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

INDICADOR_ID = "saude.resp.internacoes_j"
DESCRICAO = (
    "Internações por doenças respiratórias (CID-10 Cap. X, J00-J99) "
    "por município de residência × mês de internação."
)
CAVEAT = (
    "⚠️ Meses recentes podem estar INCOMPLETOS: faturamento hospitalar tem "
    "defasagem de ~2 meses.  Colunas marcadas com parcial=True são provisórias."
)
BADGE_SUPRIMIDO = "🔒"

_DEFAULT_K = 5


def calcular(
    lazy_frame,
    *,
    k: int = _DEFAULT_K,
    ref_date: Optional[date] = None,
) -> "polars.DataFrame":
    """Calcula o indicador a partir de um LazyFrame SIH-RD.

    Args:
        lazy_frame: polars.LazyFrame com pelo menos as colunas:
                    MUNIC_RES, DIAG_PRINC, DT_INTER.
        k: limiar k-anonimato (≥5 para dados de saúde).
        ref_date: data de referência para marcação de parciais (default: hoje).

    Returns:
        polars.DataFrame com colunas:
            munic_res_6   str   código IBGE 6 dígitos (residência)
            mes_intern    str   AAAAMM de internação
            internacoes   int?  contagem (None se suprimida)
            suprimido     bool  True se k-anonimato suprimiu
            parcial       bool  True se mês dentro da janela de defasagem
    """
    from src.datasus.sih_rd import process

    return process(lazy_frame, k=k, ref_date=ref_date)


def resumo(df) -> dict:
    """Retorna um resumo estatístico do indicador calculado.

    Args:
        df: polars.DataFrame retornado por calcular().

    Returns:
        dict com chaves: total_aih, municipios, meses, celulas_suprimidas,
        celulas_parciais, min_internacoes, max_internacoes.
    """
    try:
        import polars as pl
    except ImportError as e:
        raise ImportError("pip install polars") from e

    validas = df.filter(~pl.col("suprimido"))
    return {
        "indicador": INDICADOR_ID,
        "total_aih": int(validas["internacoes"].sum() or 0),
        "municipios": df["munic_res_6"].n_unique(),
        "meses": df["mes_intern"].n_unique(),
        "celulas_suprimidas": int(df["suprimido"].sum()),
        "celulas_parciais": int(df["parcial"].sum()),
        "min_internacoes": (
            int(validas["internacoes"].min()) if len(validas) else None
        ),
        "max_internacoes": (
            int(validas["internacoes"].max()) if len(validas) else None
        ),
    }
